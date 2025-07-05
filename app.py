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

# --- Corrected Imports ---
# Imports the necessary functions from your other project files
from portfolio_analysis import get_batch_stock_data
from google_sheets_storage import (
    init_google_sheet,
    save_user_portfolio_to_sheets,
    get_user_portfolio_from_sheets,
    get_all_users_from_sheets
)
# This now correctly imports the newsletter function from main.py
from main import generate_newsletter_for_user


# ---------- Configuration ----------
OPENAI_MODEL = "gpt-4o-mini"
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
        logging.info("Starting Excel file extraction...")
        excel_file = pd.ExcelFile(BytesIO(file_bytes))
        logging.info(f"Excel file sheets: {excel_file.sheet_names}")
        
        all_data = []
        for sheet_name in excel_file.sheet_names:
            logging.info(f"Processing sheet: {sheet_name}")
            df = pd.read_excel(BytesIO(file_bytes), sheet_name=sheet_name)
            logging.info(f"Sheet {sheet_name} shape: {df.shape}")
            logging.info(f"Sheet {sheet_name} columns: {list(df.columns)}")
            all_data.append(df)
        
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            logging.info(f"Combined data shape: {combined_df.shape}")
            return combined_df
        else:
            logging.warning("No data found in Excel file")
            return pd.DataFrame()
    except Exception as e:
        logging.error(f"Error extracting data from Excel: {e}", exc_info=True)
        return pd.DataFrame()

def extract_portfolio_with_ai(content: str, file_type: str) -> Dict[str, float]:
    """Use GPT to extract portfolio holdings and validate tickers in a batch."""
    logging.info(f"Starting AI portfolio extraction for {file_type} file...")
    
    # Enhanced prompt for better CSV parsing
    if file_type == 'csv':
        prompt = f"""
        Analyze this CSV portfolio data and extract stock holdings. Look for:
        - Stock ticker symbols (like AAPL, MSFT, GOOGL, etc.)
        - Number of shares, quantities, or positions
        - Common column names: Ticker, Symbol, Stock, Shares, Quantity, Position, Amount
        
        CSV Content:
        {content[:4000]}
        
        Return ONLY a JSON object with this exact format:
        {{
            "holdings": [
                {{"ticker": "AAPL", "shares": 100}},
                {{"ticker": "MSFT", "shares": 50}}
            ]
        }}
        
        Important:
        - Extract ALL stock tickers found in the data
        - Use the number of shares/quantity from the data
        - If no shares found, use 100 as default
        - Convert tickers to uppercase
        - Only include valid stock symbols (3-5 letters)
        """
    else:
        prompt = f"""
        Analyze the following {file_type} content and extract stock portfolio information.
        Extract all stock tickers and the number of shares held. Look for:
        - Stock symbols (like AAPL, MSFT, GOOGL, etc.)
        - Company names that can be mapped to tickers
        - Number of shares, quantities, or positions
        Content:
        {content[:4000]}
        Return the data as a JSON object with this exact format:
        {{
            "holdings": [
                {{"ticker": "AAPL", "shares": 100}},
                {{"ticker": "MSFT", "shares": 50}}
            ]
        }}
        """
    
    try:
        logging.info("Sending request to OpenAI for portfolio analysis...")
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a financial analyst expert at extracting portfolio data from documents. Always return valid JSON with stock tickers and share quantities."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        logging.info("Received response from OpenAI, parsing JSON...")
        content = response.choices[0].message.content
        if content is None:
            logging.error("OpenAI returned None content")
            return {}
        result = json.loads(content)  # type: ignore
        logging.info(f"OpenAI extracted result: {result}")
        
        potential_holdings = {
            item.get("ticker", "").upper(): float(item.get("shares", 100))
            for item in result.get("holdings", []) if item.get("ticker")
        }
        
        logging.info(f"Parsed potential holdings: {potential_holdings}")
        
        if not potential_holdings:
            logging.warning("No potential holdings found in AI response")
            return {}

        logging.info("Validating tickers with stock price data...")
        valid_tickers_data = get_batch_stock_data(tuple(potential_holdings.keys()))
        logging.info(f"Stock price validation results: {valid_tickers_data}")
        
        final_holdings = {
            ticker: shares for ticker, shares in potential_holdings.items()
            if ticker in valid_tickers_data and valid_tickers_data[ticker].get('current_price') is not None
        }
        
        logging.info(f"Final validated holdings: {final_holdings}")
        return final_holdings
        
    except Exception as e:
        logging.error(f"Error extracting portfolio with AI: {e}", exc_info=True)
        return {}

# ---------- Streamlit UI ----------
def main():
    st.set_page_config(
        page_title="Stephen Financial - Portfolio Newsletter",
        page_icon="📊",
        layout="wide"
    )

    if 'google_sheet_initialized' not in st.session_state:
        st.session_state['google_sheet_initialized'] = init_google_sheet()

    if not st.session_state['google_sheet_initialized']:
        st.error("Failed to initialize Google Sheet. Please check credentials and Sheet ID.")
        return

    st.markdown("""
    <style>
    /* Professional styling for the entire app */
    .main-header { 
        text-align: center; 
        padding: 2.5rem 0; 
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 50%, #1e40af 100%); 
        color: white; 
        border-radius: 15px; 
        margin-bottom: 2rem; 
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        border: 1px solid rgba(255,255,255,0.1);
    }
    
    .main-header h1 {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }
    
    .main-header h3 {
        font-size: 1.2rem;
        font-weight: 400;
        opacity: 0.9;
        margin: 0;
    }
    
    .upload-section { 
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        padding: 2.5rem; 
        border-radius: 15px; 
        border: 1px solid #cbd5e1;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 2rem;
    }
    
    .portfolio-display { 
        background: linear-gradient(135deg, #ffffff 0%, #f1f5f9 100%);
        padding: 2rem; 
        border-radius: 15px; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.1); 
        margin-top: 1rem;
        border: 1px solid #e2e8f0;
    }
    
    .sidebar-section {
        background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #cbd5e1;
        margin-bottom: 1rem;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .success-message {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #047857;
    }
    
    .info-message {
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #1e40af;
    }
    
    .warning-message {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #b45309;
    }
    
    .error-message {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #b91c1c;
    }
    
    /* Custom button styling */
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #1d4ed8 0%, #1e3a8a 100%);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        transform: translateY(-1px);
    }
    
    /* File uploader styling */
    .stFileUploader > div {
        border: 2px dashed #cbd5e1;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        background: rgba(248, 250, 252, 0.5);
        transition: all 0.3s ease;
    }
    
    .stFileUploader > div:hover {
        border-color: #3b82f6;
        background: rgba(59, 130, 246, 0.05);
    }
    
    /* Progress bar styling */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #3b82f6 0%, #1d4ed8 100%);
    }
    
    /* Dataframe styling */
    .dataframe {
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Hide Streamlit default elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f5f9;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #94a3b8;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="main-header"><h1>📈 Stephen Financial</h1><h3>Professional Portfolio Newsletter Service</h3></div>', unsafe_allow_html=True)
    
    # Contact Advisor button at the top
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("📞 Contact an Advisor", use_container_width=True, type="primary"):
            st.info("📧 Please contact us at: keanejpalmer@gmail.com")
            st.info("📱 Or call us at: (555) 123-4567")
    
    st.markdown("---")

    # Sidebar for admin functions
    with st.sidebar:
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.header("🔧 Admin Panel")
        if st.button("📧 Send All Newsletters", use_container_width=True):
            users = get_all_users_from_sheets()
            if users:
                with st.spinner(f"Sending newsletters to {len(users)} users..."):
                    success_count = 0
                    for user in users:
                        if user.get('holdings'):
                            if generate_newsletter_for_user(user['email'], user['holdings']):
                                success_count += 1
                    st.success(f"✅ Sent {success_count} newsletters successfully!")
            else:
                st.warning("⚠️ No users found in database")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.subheader("👥 Registered Users")
        users = get_all_users_from_sheets()
        if users:
            for user in users:
                with st.expander(f"📧 {user['email']}"):
                    st.write(f"**Last Updated:** {user.get('last_updated', 'N/A')}")
                    st.write("**Holdings:**", user.get('holdings', {}))
        else:
            st.info("No users registered yet")
        st.markdown('</div>', unsafe_allow_html=True)

    # Main content
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown('<div class="upload-section">', unsafe_allow_html=True)
        st.header("📤 Portfolio Upload")
        st.markdown("Upload your portfolio document to receive personalized newsletters with market analysis and performance insights.")
        
        email = st.text_input("📧 Your Email Address", placeholder="you@example.com")
        
        # File uploader with better feedback
        uploaded_file = st.file_uploader(
            "📁 Upload your portfolio document (PDF, DOCX, XLSX, CSV)",
            type=['pdf', 'docx', 'xlsx', 'xls', 'csv'],
            help="Select a file containing your portfolio holdings. Supported formats: PDF, Word, Excel, CSV",
            accept_multiple_files=False,
            key="portfolio_uploader"
        )
        
        # Show file upload status with error handling
        if uploaded_file is not None:
            try:
                st.success(f"✅ File uploaded: {uploaded_file.name}")
                st.info(f"📁 File size: {uploaded_file.size} bytes")
                st.info(f"📋 File type: {uploaded_file.type}")
                
                # Test file reading
                try:
                    file_bytes = uploaded_file.read()
                    st.info(f"📄 File read successfully: {len(file_bytes)} bytes")
                    # Reset file pointer for later use
                    uploaded_file.seek(0)
                except Exception as e:
                    st.error(f"❌ Error reading file: {e}")
                    st.error("This might be a file permission or format issue.")
                    
            except Exception as e:
                st.error(f"❌ Error processing uploaded file: {e}")
                st.error("Please try uploading a different file or check file permissions.")
        else:
            st.info("📤 Please select a file to upload")
        
        # --- FIX: Restored the processing logic here ---
        if uploaded_file and email:
            if st.button("🔍 Process Portfolio", type="primary"):
                try:
                    # Create a progress container
                    progress_container = st.container()
                    status_container = st.container()
                    
                    with progress_container:
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                    
                    with status_container:
                        log_container = st.container()
                        
                        def update_progress(step, total_steps, message):
                            progress = step / total_steps  # This gives a value between 0.0 and 1.0
                            progress_bar.progress(progress)
                            status_text.text(f"Step {step}/{total_steps}: {message}")
                            with log_container:
                                st.info(f"🔄 {message}")
                    
                    # Step 1: File Processing
                    update_progress(1, 6, "Reading uploaded file...")
                    
                    try:
                        file_bytes = uploaded_file.read()
                        file_type = uploaded_file.name.split('.')[-1].lower()
                        with log_container:
                            st.info(f"📁 File: {uploaded_file.name} ({uploaded_file.size} bytes)")
                            st.info(f"📋 Type: {file_type}")
                            st.info(f"📄 Bytes read: {len(file_bytes)}")
                    except Exception as e:
                        st.error(f"❌ Error reading file: {e}")
                        logging.error(f"File read error: {e}", exc_info=True)
                        return
                    
                    # Step 2: Content Extraction
                    update_progress(2, 6, "Extracting content from file...")
                    content = ""
                    if file_type == 'pdf':
                        content = extract_text_from_pdf(file_bytes)
                        with log_container:
                            st.info(f"📄 PDF content extracted: {len(content)} characters")
                    elif file_type == 'docx':
                        content = extract_text_from_docx(file_bytes)
                        with log_container:
                            st.info(f"📄 DOCX content extracted: {len(content)} characters")
                    elif file_type == 'csv':
                        # Handle CSV files directly
                        df = pd.read_csv(BytesIO(file_bytes))
                        content = df.to_string()
                        with log_container:
                            st.info(f"📊 CSV data extracted: {df.shape[0]} rows, {df.shape[1]} columns")
                            st.info(f"📄 Content length: {len(content)} characters")
                    elif file_type in ['xlsx', 'xls']:
                        df = extract_data_from_excel(file_bytes)
                        content = df.to_string()
                        with log_container:
                            st.info(f"📊 Excel data extracted: {df.shape[0]} rows, {df.shape[1]} columns")
                            st.info(f"📄 Content length: {len(content)} characters")
                    
                    if not content:
                        st.error("❌ Could not read content from the uploaded file.")
                        st.error("Please check that the file contains readable data.")
                        return
                    
                    # Step 3: AI Analysis
                    update_progress(3, 6, "Analyzing portfolio with AI...")
                    with log_container:
                        st.info("🤖 Sending content to OpenAI for analysis...")
                    
                    holdings = extract_portfolio_with_ai(content, file_type)
                    
                    with log_container:
                        if holdings:
                            st.success(f"✅ AI analysis complete! Found {len(holdings)} holdings:")
                            for ticker, shares in holdings.items():
                                st.info(f"   • {ticker}: {shares} shares")
                        else:
                            st.warning("⚠️ AI analysis found no valid holdings")
                    
                    if not holdings:
                        st.error("❌ Could not extract any valid stock holdings from the document.")
                        st.info("This might be because:")
                        st.info("   • No stock tickers were found in the document")
                        st.info("   • The tickers found were not valid")
                        st.info("   • The document format is not supported")
                        return
                    
                    # Step 4: Stock Price Validation
                    update_progress(4, 6, "Validating stock tickers and fetching prices...")
                    with log_container:
                        st.info("💰 Fetching current stock prices to validate tickers...")
                    
                    ticker_list = tuple(holdings.keys())
                    stock_data = get_batch_stock_data(ticker_list)
                    valid_holdings = {}
                    
                    for ticker, shares in holdings.items():
                        if ticker in stock_data and stock_data[ticker].get('current_price') is not None:
                            valid_holdings[ticker] = shares
                            with log_container:
                                st.info(f"✅ {ticker}: ${stock_data[ticker]['current_price']:.2f}")
                        else:
                            with log_container:
                                st.warning(f"⚠️ {ticker}: Invalid ticker or price unavailable")
                    
                    if not valid_holdings:
                        st.error("❌ No valid stock tickers found after price validation.")
                        return
                    
                    # Step 5: Google Sheets Save
                    update_progress(5, 6, "Saving portfolio to database...")
                    with log_container:
                        st.info("💾 Saving portfolio data to Google Sheets...")
                    
                    if save_user_portfolio_to_sheets(email, valid_holdings):
                        # Step 6: Complete
                        update_progress(6, 6, "Portfolio processing complete!")
                        with log_container:
                            st.success("🎉 Portfolio saved successfully!")
                        
                        # Store in session state and refresh
                        st.session_state['current_holdings'] = valid_holdings
                        st.session_state['current_email'] = email
                        
                        # Show success message
                        st.success("✅ Portfolio processed and saved successfully!")
                        st.info("You can now view your portfolio on the right side and send a test newsletter.")
                        
                        # Auto-refresh after a short delay
                        import time
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("❌ Failed to save portfolio to database.")
                        st.error("Please check the terminal logs for detailed error information.")
                        
                except Exception as e:
                    st.error(f"❌ An error occurred during processing: {str(e)}")
                    st.error("Please check the terminal for detailed error logs.")
                    logging.error(f"Portfolio processing error: {e}", exc_info=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.header("📊 Portfolio Overview")
        if 'current_holdings' in st.session_state:
            holdings = st.session_state['current_holdings']
            email = st.session_state.get('current_email', '')
            st.markdown('<div class="portfolio-display">', unsafe_allow_html=True)
            st.subheader(f"📈 Portfolio for: {email}")

            ticker_list = tuple(holdings.keys())
            if ticker_list:
                portfolio_details = get_batch_stock_data(ticker_list)
                portfolio_data = []
                total_value = 0
                for ticker, shares in holdings.items():
                    details = portfolio_details.get(ticker)
                    if details and details.get('current_price') is not None:
                        current_price = details.get('current_price', 0)
                        value = current_price * shares
                        total_value += value
                        portfolio_data.append({
                            'Ticker': ticker,
                            'Company': details.get('company_name', ticker),
                            'Shares': shares,
                            'Current Price': f"${current_price:.2f}",
                            'Value': f"${value:,.2f}"
                        })
                
                df = pd.DataFrame(portfolio_data)
                st.dataframe(df, use_container_width=True)
                
                # Enhanced total value display
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("💰 Total Portfolio Value", f"${total_value:,.2f}")
                st.markdown('</div>', unsafe_allow_html=True)

            if st.button("📬 Send Test Newsletter", use_container_width=True):
                with st.spinner("Generating and sending your newsletter..."):
                    if generate_newsletter_for_user(email, holdings):
                        st.success(f"✅ Newsletter sent to {email}!")
                    else:
                        st.error("❌ Failed to send newsletter. Check logs for details.")
            
            # Contact Advisor button at the bottom
            st.markdown("---")
            if st.button("📞 Contact an Advisor", use_container_width=True, type="primary"):
                st.info("📧 Please contact us at: keanejpalmer@gmail.com")
                st.info("📱 Or call us at: (555) 123-4567")
            
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="portfolio-display">', unsafe_allow_html=True)
            st.info("📤 Upload a portfolio to see your holdings and send newsletters")
            st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()