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
    """Use GPT to extract portfolio holdings and validate tickers in a batch."""
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
        potential_holdings = {
            item.get("ticker", "").upper(): float(item.get("shares", 100))
            for item in result.get("holdings", []) if item.get("ticker")
        }
        if not potential_holdings:
            return {}

        valid_tickers_data = get_batch_stock_data(tuple(potential_holdings.keys()))
        final_holdings = {
            ticker: shares for ticker, shares in potential_holdings.items()
            if ticker in valid_tickers_data and valid_tickers_data[ticker].get('current_price') is not None
        }
        return final_holdings
    except Exception as e:
        logging.error(f"Error extracting portfolio with AI: {e}")
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
    .main-header { text-align: center; padding: 2rem 0; background: linear-gradient(135deg, #1a365d 0%, #2563eb 100%); color: white; border-radius: 10px; margin-bottom: 2rem; }
    .upload-section { background-color: #f8fafc; padding: 2rem; border-radius: 10px; border: 1px solid #e2e8f0; }
    .portfolio-display { background-color: #ffffff; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-top: 1rem; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="main-header"><h1>Stephen Financial</h1><h3>Weekly Portfolio Newsletter Service</h3></div>', unsafe_allow_html=True)

    # Sidebar for admin functions
    with st.sidebar:
        st.header("Admin Panel")
        if st.button("📧 Send All Newsletters"):
            users = get_all_users_from_sheets()
            if users:
                with st.spinner(f"Sending newsletters to {len(users)} users..."):
                    success_count = 0
                    for user in users:
                        if user.get('holdings'):
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
                st.write(f"Last Updated: {user.get('last_updated', 'N/A')}")
                st.write("Holdings:", user.get('holdings', {}))

    # Main content
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown('<div class="upload-section">', unsafe_allow_html=True)
        st.header("📤 Upload Your Portfolio")
        email = st.text_input("Your Email Address", placeholder="you@example.com")
        uploaded_file = st.file_uploader(
            "Upload your portfolio document (PDF, DOCX, XLSX, CSV)",
            type=['pdf', 'docx', 'xlsx', 'xls', 'csv'],
        )
        
        # --- FIX: Restored the processing logic here ---
        if uploaded_file and email:
            if st.button("🔍 Process Portfolio", type="primary"):
                with st.spinner("Analyzing your portfolio... This may take a moment."):
                    file_bytes = uploaded_file.read()
                    file_type = uploaded_file.name.split('.')[-1].lower()
                    content = ""
                    if file_type == 'pdf':
                        content = extract_text_from_pdf(file_bytes)
                    elif file_type == 'docx':
                        content = extract_text_from_docx(file_bytes)
                    elif file_type in ['xlsx', 'xls', 'csv']:
                        content = extract_data_from_excel(file_bytes).to_string()

                    if not content:
                        st.error("Could not read content from the uploaded file.")
                    else:
                        holdings = extract_portfolio_with_ai(content, file_type)
                        if holdings:
                            if save_user_portfolio_to_sheets(email, holdings):
                                st.success("✅ Portfolio saved successfully!")
                                st.session_state['current_holdings'] = holdings
                                st.session_state['current_email'] = email
                                st.rerun()
                            else:
                                st.error("Failed to save portfolio to Google Sheets.")
                        else:
                            st.error("Could not extract any valid stock holdings from the document.")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.header("📊 Your Portfolio")
        if 'current_holdings' in st.session_state:
            holdings = st.session_state['current_holdings']
            email = st.session_state.get('current_email', '')
            st.markdown('<div class="portfolio-display">', unsafe_allow_html=True)
            st.subheader(f"Portfolio for: {email}")

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
                st.metric("Total Portfolio Value", f"${total_value:,.2f}")

            if st.button("📬 Send Test Newsletter Now"):
                with st.spinner("Generating and sending your newsletter..."):
                    if generate_newsletter_for_user(email, holdings):
                        st.success(f"Newsletter sent to {email}!")
                    else:
                        st.error("Failed to send newsletter. Check logs for details.")
            st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()