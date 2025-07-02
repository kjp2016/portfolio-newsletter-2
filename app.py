#app.py
import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple, Optional, Any
import re
from io import BytesIO

# Document processing imports
import PyPDF2
import docx
import openpyxl
from openai import OpenAI
import yfinance as yf

# Import company_name from portfolio_analysis
from portfolio_analysis import company_name

# Import Google Sheets functions
from google_sheets_storage import (
    init_google_sheet,
    save_user_portfolio_to_sheets,
    get_user_portfolio_from_sheets,
    get_all_users_from_sheets
)

# ---------- Configuration ----------
OPENAI_MODEL = "gpt-4o-mini"

# Initialize OpenAI client
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S"
)

# ---------- Document Processing Functions ----------
def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF file."""
    try:
        pdf_reader = PyPDF2.PdfReader(BytesIO(file_bytes))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logging.error(f"Error extracting text from PDF: {e}")
        return ""

def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from Word document."""
    try:
        doc = docx.Document(BytesIO(file_bytes))
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    text += cell.text + "\t"
                text += "\n"
        return text
    except Exception as e:
        logging.error(f"Error extracting text from DOCX: {e}")
        return ""

def extract_data_from_excel(file_bytes: bytes) -> pd.DataFrame:
    """Extract data from Excel file."""
    try:
        excel_file = pd.ExcelFile(BytesIO(file_bytes))
        all_data = []
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(BytesIO(file_bytes), sheet_name=sheet_name)
            all_data.append(df)
        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
    except Exception as e:
        logging.error(f"Error extracting data from Excel: {e}")
        return pd.DataFrame()

def extract_portfolio_with_ai(content: str, file_type: str) -> Dict[str, float]:
    """Use GPT to extract portfolio holdings from document content."""
    prompt = f"""
    Analyze the following {file_type} content and extract stock portfolio information.
    
    Extract all stock tickers and the number of shares held. Look for:
    - Stock symbols (like AAPL, MSFT, GOOGL, etc.)
    - Company names that can be mapped to tickers
    - Number of shares, quantities, or positions
    - Portfolio values that can be converted to share counts
    
    Content:
    {content[:4000]}  # Limit to avoid token limits
    
    Return the data as a JSON object with this exact format:
    {{
        "holdings": [
            {{"ticker": "AAPL", "shares": 100}},
            {{"ticker": "MSFT", "shares": 50}},
            ...
        ]
    }}
    
    Rules:
    - Use standard ticker symbols (e.g., AAPL for Apple Inc.)
    - If only dollar values are shown, estimate shares using current prices
    - If no share count is found, use 100 as default
    - Only include stocks, not bonds or other assets
    - Ensure all tickers are valid US stock symbols
    """
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a financial analyst expert at extracting portfolio data from documents."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        holdings = {}
        for item in result.get("holdings", []):
            ticker = item.get("ticker", "").upper()
            shares = float(item.get("shares", 100))
            if ticker and validate_ticker(ticker):
                holdings[ticker] = shares
        return holdings
    except Exception as e:
        logging.error(f"Error extracting portfolio with AI: {e}")
        return {}

def validate_ticker(ticker: str) -> bool:
    """Validate if a ticker symbol exists."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return 'symbol' in info or 'shortName' in info
    except:
        return False

# ---------- Newsletter Generation ----------
def generate_newsletter_for_user(email: str, holdings: Dict[str, float]) -> bool:
    """Generate and send newsletter for a specific user."""
    if not holdings:
        return False
    try:
        from main import (
            generate_market_recap_with_search,
            get_overall_portfolio_performance,
            generate_holdings_blocks,
            render_email,
            send_gmail
        )
        tickers = list(holdings.keys())
        logging.info(f"Generating newsletter for {email} with tickers: {tickers}")
        
        weekly_perf = get_overall_portfolio_performance(tickers, "weekly")
        ytd_perf = get_overall_portfolio_performance(tickers, "ytd")
        
        overall_weekly_change_pct = weekly_perf.get('overall_change_pct', 0.0)
        major_movers = weekly_perf.get('major_movers', [])
        overall_ytd_change_pct = ytd_perf.get('overall_change_pct', 0.0)
        
        market_block_md = generate_market_recap_with_search(tickers)
        
        weekly_direction = "increased" if overall_weekly_change_pct >= 0 else "decreased"
        ytd_direction = "up" if overall_ytd_change_pct >= 0 else "down"
        
        major_movers_str = "key positions"
        if major_movers:
            if len(major_movers) == 1:
                major_movers_str = f"a key movement in {major_movers[0]}"
            else:
                major_movers_str = "movements in positions like " + " and ".join(major_movers)
        
        intro_summary_text = (
            f"This week your portfolio {weekly_direction} by {abs(overall_weekly_change_pct):.2f}%.\n"
            f"This was influenced by {major_movers_str}.\n"
            f"The broader market conditions and specific news affecting your holdings are detailed in the Market Recap below.\n"
            f"Year to date, your portfolio is {ytd_direction} {abs(overall_ytd_change_pct):.2f}%.\n\n"
            f"For more details about your specific holdings or questions on what to do next in your portfolio, "
            f"please feel free to contact an advisor here."
        )
        
        import markdown2
        intro_summary_html = markdown2.markdown(intro_summary_text.replace('\n', '<br>'))
        
        holdings_blocks = generate_holdings_blocks(tickers)
        
        html_body, txt_body = render_email(intro_summary_html, intro_summary_text, market_block_md, holdings_blocks)
        
        from main import SENDER, SUBJECT
        recipients = [email]
        
        send_gmail(html_body, txt_body, recipients=recipients)
        
        return True
    except Exception as e:
        logging.error(f"Error generating newsletter for {email}: {e}")
        return False

# ---------- Streamlit UI ----------
def main():
    # Set page config as the FIRST Streamlit command
    st.set_page_config(
        page_title="Stephen Financial - Portfolio Newsletter",
        page_icon="📊",
        layout="wide"
    )
    
    # Initialize Google Sheet after page config
    if 'google_sheet_initialized' not in st.session_state:
        st.session_state['google_sheet_initialized'] = init_google_sheet()
    
    # Check initialization success
    if not st.session_state['google_sheet_initialized']:
        st.error("Failed to initialize Google Sheet. Please check the logs for details.")
        return
    
    # Custom CSS
    st.markdown("""
    <style>
    .main-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(135deg, #1a365d 0%, #2563eb 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .upload-section {
        background-color: #f8fafc;
        padding: 2rem;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
    }
    .portfolio-display {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-top: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>Stephen Financial</h1>
        <h3>Weekly Portfolio Newsletter Service</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar for admin functions
    with st.sidebar:
        st.header("Admin Panel")
        if st.button("📧 Send All Newsletters"):
            users = get_all_users_from_sheets()
            if users:
                with st.spinner(f"Sending newsletters to {len(users)} users..."):
                    success_count = 0
                    for user in users:
                        if user['holdings']:
                            if generate_newsletter_for_user(user['email'], user['holdings']):
                                success_count += 1
                    st.success(f"Sent {success_count} newsletters successfully!")
            else:
                st.warning("No users found in database")
        
        st.divider()
        st.subheader("Registered Users")
        users = get_all_users_from_sheets()
        for user in users:
            with st.expander(f"📧 {user['email']}"):
                st.write(f"Last Updated: {user['last_updated']}")
                st.write("Holdings:")
                for ticker, shares in user['holdings'].items():
                    st.write(f"- {ticker}: {shares} shares")
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown('<div class="upload-section">', unsafe_allow_html=True)
        st.header("📤 Upload Your Portfolio")
        email = st.text_input("Your Email Address", placeholder="you@example.com")
        uploaded_file = st.file_uploader(
            "Upload your portfolio document",
            type=['pdf', 'docx', 'xlsx', 'xls', 'csv'],
            help="Upload a PDF, Word document, or Excel file containing your stock holdings"
        )
        if uploaded_file and email:
            if st.button("🔍 Process Portfolio", type="primary"):
                with st.spinner("Analyzing your portfolio..."):
                    file_bytes = uploaded_file.read()
                    file_type = uploaded_file.name.split('.')[-1].lower()
                    content = ""
                    if file_type == 'pdf':
                        content = extract_text_from_pdf(file_bytes)
                    elif file_type == 'docx':
                        content = extract_text_from_docx(file_bytes)
                    elif file_type in ['xlsx', 'xls']:
                        df = extract_data_from_excel(file_bytes)
                        content = df.to_string()
                    elif file_type == 'csv':
                        df = pd.read_csv(BytesIO(file_bytes))
                        content = df.to_string()
                    holdings = extract_portfolio_with_ai(content, file_type)
                    if holdings:
                        if save_user_portfolio_to_sheets(email, holdings):
                            st.success("✅ Portfolio saved successfully!")
                            st.session_state['current_holdings'] = holdings
                            st.session_state['current_email'] = email
                        else:
                            st.error("Failed to save portfolio to Google Sheets.")
                    else:
                        st.error("Could not extract any valid stock holdings.")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.header("📊 Your Portfolio")
        if 'current_holdings' in st.session_state:
            holdings = st.session_state['current_holdings']
            email = st.session_state.get('current_email', '')
            st.markdown('<div class="portfolio-display">', unsafe_allow_html=True)
            st.subheader(f"Portfolio for: {email}")
            portfolio_data = []
            total_value = 0
            for ticker, shares in holdings.items():
                try:
                    stock = yf.Ticker(ticker)
                    current_price = stock.info.get('currentPrice', 0)
                    value = current_price * shares
                    total_value += value
                    portfolio_data.append({
                        'Ticker': ticker,
                        'Company': company_name(ticker),
                        'Shares': shares,
                        'Current Price': f"${current_price:.2f}",
                        'Value': f"${value:,.2f}"
                    })
                except:
                    portfolio_data.append({
                        'Ticker': ticker,
                        'Company': ticker,
                        'Shares': shares,
                        'Current Price': "N/A",
                        'Value': "N/A"
                    })
            df = pd.DataFrame(portfolio_data)
            st.dataframe(df, use_container_width=True)
            st.metric("Total Portfolio Value", f"${total_value:,.2f}")
            if st.button("📬 Send Test Newsletter Now"):
                with st.spinner("Generating and sending your newsletter..."):
                    if generate_newsletter_for_user(email, holdings):
                        st.success(f"Newsletter sent to {email}!")
                    else:
                        st.error("Failed to send newsletter")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            email_check = st.text_input("Check existing portfolio", placeholder="your@email.com")
            if email_check and st.button("Load Portfolio"):
                holdings = get_user_portfolio_from_sheets(email_check)
                if holdings:
                    st.session_state['current_holdings'] = holdings
                    st.session_state['current_email'] = email_check
                    st.rerun()
                else:
                    st.info("No portfolio found for this email")
    
    # Instructions
    with st.expander("ℹ️ How it works"):
        st.markdown("""
        1. **Upload your portfolio document** - We accept PDF, Word, Excel, or CSV files
        2. **Our AI analyzes your holdings** - We extract stock tickers and share counts
        3. **Weekly newsletters** - Receive personalized market analysis every week
        4. **Secure storage** - Your portfolio is safely stored for future newsletters
        
        ### Supported formats:
        - **PDF**: Brokerage statements, portfolio summaries
        - **Excel/CSV**: Portfolio spreadsheets with tickers and quantities
        - **Word**: Investment reports or portfolio documents
        
        ### What we look for:
        - Stock symbols (AAPL, MSFT, etc.)
        - Number of shares or units
        - Company names (we'll convert to tickers)
        """)

if __name__ == "__main__":
    main()