import os
import logging
import smtplib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from jinja2 import Environment, FileSystemLoader, select_autoescape
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import markdown2
import pandas as pd
import streamlit as st
from openai import OpenAI

# --- Local Modules ---
# These imports assume portfolio_analysis.py and market_recap.py are in the same directory
from portfolio_analysis import (
    get_batch_price_performance,
    get_batch_stock_data,
    gpt_paragraph_for_holding
)
from market_recap import generate_market_recap_with_search
from hybrid_finance_service import get_hybrid_finance_service

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S"
)

# --- Configurations ---
# Ensure secrets are loaded for all environments
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    GMAIL_APP_PASSWORD = st.secrets["GMAIL_APP_PASSWORD"]
except (AttributeError, KeyError):
    # Fallback for local execution outside of Streamlit
    from dotenv import load_dotenv
    load_dotenv()
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

client = OpenAI(api_key=OPENAI_API_KEY)
OPENAI_MODEL = "gpt-4o-mini"
SENDER_EMAIL = "keanejpalmer@gmail.com"  # Your sending email address
TEMPLATE_DIR = "./templates"


def get_overall_portfolio_performance(
    portfolio_tickers: Tuple[str, ...],
    period: str,
    holdings: Optional[Dict[str, float]] = None,
    existing_perf_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Calculates overall portfolio performance using batch data with failure handling."""
    today = pd.Timestamp.utcnow()
    start_date = today - timedelta(days=7) if period == "weekly" else today.replace(month=1, day=1).normalize()

    # Use existing performance data if provided, otherwise fetch new data
    if existing_perf_data:
        all_perf_data = existing_perf_data
        logging.info(f"REUSING existing performance data for {period} calculation ({len(existing_perf_data)} tickers)")
    else:
        # Use Alpha Vantage directly for efficiency
        logging.info(f"FETCHING NEW performance data for {period} calculation ({len(portfolio_tickers)} tickers)")
        from alpha_vantage_service import get_alpha_vantage_service
        service = get_alpha_vantage_service()
        if hasattr(service, 'get_portfolio_performance_with_failures'):
            result = service.get_portfolio_performance_with_failures(
                portfolio_tickers, start_date, today, period_name=period
            )
            all_perf_data = result["performance_data"]
            failed_tickers = result["failed_tickers"]
            success_rate = result["success_rate"]
        else:
            # Fallback to batch method
            all_perf_data = get_batch_price_performance(portfolio_tickers, start_date, today, period_name=period)
            failed_tickers = []
            success_rate = 100.0

    # Calculate failed tickers and success rate
    failed_tickers = [ticker for ticker, data in all_perf_data.items() if 'error' in data]
    success_rate = ((len(portfolio_tickers) - len(failed_tickers)) / len(portfolio_tickers)) * 100 if portfolio_tickers else 0.0

    valid_performances = [p for p in all_perf_data.values() if 'error' not in p]

    if not valid_performances:
        logging.error("No valid performance data available for portfolio calculation")
        return {"overall_change_pct": 0.0, "major_movers": [], "failed_tickers": failed_tickers, "success_rate": 0.0}

    # Use weighted average if holdings are provided, otherwise use a simple average
    if holdings:
        total_value_start, total_value_end = 0, 0
        valid_holdings = 0
        for perf in valid_performances:
            shares = holdings.get(perf['ticker'], 0)
            if shares > 0:
                total_value_start += perf['first_close'] * shares
                total_value_end += perf['last_close'] * shares
                valid_holdings += 1
        
        if total_value_start > 0:
            overall_change_pct = ((total_value_end - total_value_start) / total_value_start) * 100
            logging.info(f"Portfolio calculation: {valid_holdings} holdings with valid data, total value change: {overall_change_pct:.2f}%")
        else:
            overall_change_pct = 0.0
            logging.warning("No valid holdings with shares > 0 for portfolio calculation")
    else:
        total_pct_change = sum(p['pct_change'] for p in valid_performances)
        overall_change_pct = total_pct_change / len(valid_performances) if valid_performances else 0.0

    # Determine major movers based on weekly performance
    major_movers = []
    if period == "weekly":
        sorted_by_impact = sorted(valid_performances, key=lambda x: abs(x.get('pct_change', 0.0)), reverse=True)
        for mover in sorted_by_impact[:2]:
            major_movers.append(f"{mover['ticker']} ({mover['pct_change']:.2f}%)")

    # Log failure summary
    if failed_tickers:
        logging.warning(f"Portfolio calculation: {len(failed_tickers)} tickers failed ({success_rate:.1f}% success rate)")
        logging.warning(f"Failed tickers: {', '.join(failed_tickers)}")
        
        # If too many failures, warn about accuracy
        if success_rate < 80.0:
            logging.warning(f"Low success rate ({success_rate:.1f}%) - portfolio performance may be inaccurate")

    return {
        "overall_change_pct": overall_change_pct, 
        "major_movers": major_movers,
        "failed_tickers": failed_tickers,
        "success_rate": success_rate,
        "valid_holdings_count": len(valid_performances),
        "performance_data": all_perf_data  # Include the raw performance data for reuse
    }


def generate_holdings_blocks(portfolio_tickers: Tuple[str, ...], existing_perf_data: Optional[Dict[str, Any]] = None, existing_company_data: Optional[Dict[str, Any]] = None) -> List[dict]:
    """Generates analysis paragraphs for each holding using existing data or fetching new data, limited to top 5 movers."""
    today = pd.Timestamp.utcnow()
    week_ago = today - timedelta(days=7)  # Use weekly period for individual stock analysis

    # Use existing performance data if provided, otherwise fetch new data
    if existing_perf_data:
        price_data_weekly = existing_perf_data
        logging.info(f"REUSING existing performance data for {len(existing_perf_data)} tickers")
    else:
        # Fetch all data in batches first
        logging.info(f"FETCHING NEW performance data for {len(portfolio_tickers)} tickers")
        price_data_weekly = get_batch_price_performance(portfolio_tickers, week_ago, today, period_name="weekly")

    # Use existing company data if provided, otherwise fetch new data
    if existing_company_data:
        company_data = existing_company_data
        logging.info(f"REUSING existing company data for {len(existing_company_data)} tickers")
    else:
        # Fetch company data (this is separate and needed for company names)
        logging.info(f"FETCHING NEW company data for {len(portfolio_tickers)} tickers")
        company_data = get_batch_stock_data(portfolio_tickers)

    # Filter and sort by absolute percentage change to get top 5 movers
    valid_price_data = []
    for ticker in portfolio_tickers:
        price_data = price_data_weekly.get(ticker)
        if price_data and 'error' not in price_data:
            valid_price_data.append((ticker, price_data))
    
    # Sort by absolute percentage change (biggest movers first)
    valid_price_data.sort(key=lambda x: abs(x[1].get('pct_change', 0)), reverse=True)
    
    # Take only the top 5 movers
    top_5_movers = valid_price_data[:5]

    holdings_blocks = []
    for ticker, price_data in top_5_movers:
        try:
            name = company_data.get(ticker, {}).get('company_name', ticker)
            para = gpt_paragraph_for_holding(price_data, name, client, OPENAI_MODEL)
            
            # Validate the analysis format
            if para.startswith("⚠️") or "Unable to generate" in para:
                logging.warning(f"Skipping {ticker}: Analysis generation failed")
                continue  # Skip this ticker entirely
            
            holdings_blocks.append({"ticker": ticker, "para": para})
        except Exception as e:
            logging.warning(f"Skipping {ticker}: {e}")
            continue  # Skip this ticker entirely

    return holdings_blocks


def render_email(subject: str, intro_summary_html: str, intro_summary_text: str, market_md: str, holdings: List[dict]) -> Tuple[str, str]:
    """Renders the HTML and plain text versions of the email."""
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=select_autoescape(["html"]))
    template_vars = {
        "subject": subject,
        "date": datetime.utcnow().strftime("%B %d, %Y"),
        "intro_summary_html": intro_summary_html,
        "market_block_html": markdown2.markdown(market_md),
        "holdings": [{"ticker": h["ticker"], "para_html": markdown2.markdown(h["para"])} for h in holdings]
    }
    html = env.get_template("weekly_pulse.html").render(template_vars)
    text = f"{subject}\n\n{intro_summary_text}\n\nMarket Recap\n{market_md}"
    return html, text


def send_gmail(subject: str, html_body: str, txt_body: str, recipients: List[str]):
    """Connects to Gmail and sends the email."""
    if not GMAIL_APP_PASSWORD:
        logging.error("Gmail App Password not found. Cannot send email.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(txt_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipients, msg.as_string())
            logging.info(f"Email sent successfully to {', '.join(recipients)}.")
    except Exception as e:
        logging.error(f"Failed to send email via Gmail: {e}")

# --- Main Function to be Called by app.py ---
def generate_newsletter_for_user(email: str, holdings: Dict[str, float]) -> bool:
    """
    This is the main orchestrator function. It generates and sends a single newsletter.
    Optimized to fetch data once and reuse it throughout the process.
    """
    if not holdings:
        logging.warning(f"No holdings found for {email}. Skipping newsletter.")
        return False

    tickers_tuple = tuple(holdings.keys())
    subject = f"Your Weekly Portfolio Pulse – {datetime.utcnow():%b %d, %Y}"

    # --- 1. Fetch All Data Once ---
    logging.info(f"=== Starting newsletter generation for {email} ===")
    logging.info(f"Fetching all data for {len(tickers_tuple)} tickers...")
    
    # Fetch weekly performance data once
    logging.info("Step 1: Fetching weekly performance data...")
    weekly_perf = get_overall_portfolio_performance(tickers_tuple, "weekly", holdings)
    weekly_perf_data = weekly_perf.get('performance_data', {})
    logging.info(f"Step 1 complete: Got performance data for {len([k for k, v in weekly_perf_data.items() if 'error' not in v])}/{len(tickers_tuple)} tickers")
    
    # Fetch YTD performance data (reuse weekly data if possible, otherwise fetch separately)
    logging.info("Step 2: Fetching YTD performance data...")
    ytd_perf = get_overall_portfolio_performance(tickers_tuple, "ytd", holdings, existing_perf_data=weekly_perf_data)
    logging.info(f"Step 2 complete: YTD calculation done")
    
    # Fetch company data once for reuse
    logging.info("Step 3: Fetching company data...")
    company_data = get_batch_stock_data(tickers_tuple)
    logging.info(f"Step 3 complete: Got company data for {len([k for k, v in company_data.items() if v.get('current_price')])}/{len(tickers_tuple)} tickers")
    
    overall_weekly_change_pct = weekly_perf.get('overall_change_pct', 0.0)
    major_movers = weekly_perf.get('major_movers', [])
    overall_ytd_change_pct = ytd_perf.get('overall_change_pct', 0.0)
    
    # Check for data quality issues
    weekly_failed_tickers = weekly_perf.get('failed_tickers', [])
    weekly_success_rate = weekly_perf.get('success_rate', 100.0)
    
    if weekly_success_rate < 80.0:
        logging.warning(f"Low data quality for {email}: {weekly_success_rate:.1f}% success rate")
        logging.warning(f"Failed tickers: {', '.join(weekly_failed_tickers)}")

    # --- SKIP EMAIL IF PORTFOLIO DROPS MORE THAN 5% ---
    if overall_weekly_change_pct < -5.0:
        logging.warning(f"Portfolio for {email} dropped {overall_weekly_change_pct:.2f}% this week. Skipping email send.")
        return False

    # --- 2. Generate AI Content ---
    logging.info("Step 4: Generating market recap...")
    market_block_md = generate_market_recap_with_search(list(tickers_tuple))
    logging.info("Step 4 complete: Market recap generated")
    
    # Generate holdings blocks using existing data to avoid duplicate API calls
    logging.info("Step 5: Generating holdings analysis using existing data...")
    holdings_blocks = generate_holdings_blocks(tickers_tuple, weekly_perf_data, company_data)
    logging.info(f"Step 5 complete: Generated analysis for {len(holdings_blocks)} holdings")

    # --- 3. Build Email Text ---
    weekly_direction = "increased" if overall_weekly_change_pct >= 0 else "decreased"
    ytd_direction = "up" if overall_ytd_change_pct >= 0 else "down"
    major_movers_str = "movements in positions like " + " and ".join(major_movers) if major_movers else "key positions"

    intro_summary_text = (
        f"This week your portfolio {weekly_direction} by {abs(overall_weekly_change_pct):.2f}%.\n"
        f"This was influenced by {major_movers_str}.\n"
        f"The broader market conditions and specific news affecting your holdings are detailed in the Market Recap below.\n"
        f"Year to date, your portfolio is {ytd_direction} {abs(overall_ytd_change_pct):.2f}%."
    )

    intro_summary_html = markdown2.markdown(intro_summary_text.replace('\n', '<br>'))

    # --- 4. Render and Send Email ---
    logging.info("Step 6: Rendering and sending email...")
    html_body, txt_body = render_email(subject, intro_summary_html, intro_summary_text, market_block_md, holdings_blocks)
    send_gmail(subject, html_body, txt_body, recipients=[email])
    
    logging.info(f"=== Newsletter generation complete for {email} ===")
    return True


# This block allows the script to be run directly for testing purposes
if __name__ == "__main__":
    logging.info("Running standalone test for main.py...")
    # Example test case
    test_holdings = {"AAPL": 10.0, "MSFT": 20.0, "GOOGL": 5.0}
    test_email = "keanejpalmer@gmail.com"  # A test recipient
    
    if not all([OPENAI_API_KEY, GMAIL_APP_PASSWORD]):
         logging.error("Missing API keys (OPENAI_API_KEY, GMAIL_APP_PASSWORD). Aborting test.")
    else:
        generate_newsletter_for_user(test_email, test_holdings)

    logging.info("Standalone test finished.")