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

# ---------- Local Modules ----------
from market_recap import generate_market_recap_with_search
from portfolio_analysis import (
    get_batch_price_performance,
    get_batch_stock_data,
    gpt_paragraph_for_holding
)

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S"
)

# ---------- OpenAI Configuration ----------
OPENAI_MODEL = "gpt-4o-mini"
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ---------- Config ----------
TEMPLATE_DIR = "./templates"
HTML_TEMPLATE = "weekly_pulse.html"
PLAINTEXT_TEMPLATE = "weekly_pulse.txt"
SENDER = "keanejpalmer@gmail.com"
RECIPIENTS = ["keanejpalmer@gmail.com"]
SUBJECT = f"Weekly Market Pulse – {datetime.utcnow():%b %d, %Y}"

TICKERS = ["AMZN", "AVGO", "BMY", "NVDA", "MSFT", "AAPL"]

def get_overall_portfolio_performance(portfolio_tickers: Tuple[str, ...], period: str, holdings: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """Calculate overall portfolio performance using batch data."""
    today = pd.Timestamp.utcnow()
    start_date = today - timedelta(days=7) if period == "weekly" else today.replace(month=1, day=1).normalize()

    # Fetch all performance data in one batch
    all_perf_data = get_batch_price_performance(portfolio_tickers, start_date, today)
    
    valid_performances = [p for p in all_perf_data.values() if 'error' not in p]
    if not valid_performances:
        return {"overall_change_pct": 0.0, "major_movers": [], "error": "No performance data."}

    # Calculate weighted performance if holdings are provided
    if holdings:
        total_value_start, total_value_end = 0, 0
        for perf in valid_performances:
            shares = holdings.get(perf['ticker'], 0)
            total_value_start += perf['first_close'] * shares
            total_value_end += perf['last_close'] * shares
        
        overall_change_pct = ((total_value_end - total_value_start) / total_value_start) * 100 if total_value_start > 0 else 0.0
    else:
        # Simple average if no holdings
        total_pct_change = sum(p['pct_change'] for p in valid_performances)
        overall_change_pct = total_pct_change / len(valid_performances) if valid_performances else 0.0

    # Determine major movers
    major_movers_details = []
    if period == "weekly":
        sorted_by_impact = sorted(valid_performances, key=lambda x: abs(x.get('pct_change', 0.0)), reverse=True)
        for mover in sorted_by_impact[:2]: # Get top 2 movers by absolute impact
             major_movers_details.append(f"{mover['ticker']} ({mover['pct_change']:.2f}%)")
    
    return {"overall_change_pct": overall_change_pct, "major_movers": major_movers_details}

def generate_holdings_blocks(portfolio_tickers: Tuple[str, ...]) -> List[dict]:
    """Generate holdings analysis blocks using batch data."""
    today = pd.Timestamp.utcnow()
    start_mtd = today.replace(day=1).normalize()

    # BATCH 1: Get all company names and current data
    company_data = get_batch_stock_data(portfolio_tickers)
    
    # BATCH 2: Get all month-to-date performance data
    price_data_mtd = get_batch_price_performance(portfolio_tickers, start_mtd, today, period_name="month-to-date")

    holdings_blocks = []
    for ticker in portfolio_tickers:
        try:
            price_data = price_data_mtd.get(ticker)
            company_name = company_data.get(ticker, {}).get('company_name', ticker)
            
            if not price_data or 'error' in price_data:
                raise ValueError(f"No valid price data for {ticker}")

            para = gpt_paragraph_for_holding(price_data, company_name, client, OPENAI_MODEL)
            holdings_blocks.append({"ticker": ticker, "para": para})
            logging.info(f"Generated analysis for {ticker}.")

        except Exception as e:
            logging.warning(f"[{ticker}] skipped for holdings block: {e}")
            holdings_blocks.append({"ticker": ticker, "para": f"⚠️ Unable to generate detailed analysis for {ticker}."})
            
    return holdings_blocks

def render_email(intro_summary_html: str, intro_summary_text: str, market_md: str, holdings: List[dict]) -> tuple[str, str]:
    """Render email templates."""
    market_html = markdown2.markdown(market_md)
    enriched_holdings = [{"ticker": h["ticker"], "para_html": markdown2.markdown(h["para"])} for h in holdings]
    
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=select_autoescape(["html", "xml"]))
    current_date_str = datetime.utcnow().strftime("%B %d, %Y")
    
    template_vars = {
        "subject": SUBJECT, "date": current_date_str,
        "intro_summary_html": intro_summary_html, "intro_summary_text": intro_summary_text,
        "market_block_html": market_html, "market_block": market_md,
        "holdings": enriched_holdings
    }
    
    html = env.get_template(HTML_TEMPLATE).render(template_vars)
    text = env.get_template(PLAINTEXT_TEMPLATE).render(template_vars)
    return html, text

def send_gmail(html_body: str, txt_body: str, recipients: Optional[List[str]] = None):
    """Send email via Gmail."""
    try:
        to_addresses = recipients or RECIPIENTS
        if not st.secrets.get("GMAIL_APP_PASSWORD"):
            logging.error("GMAIL_APP_PASSWORD not set. Email not sent.")
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"], msg["From"], msg["To"] = SUBJECT, SENDER, ", ".join(to_addresses)
        msg.attach(MIMEText(txt_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER, st.secrets["GMAIL_APP_PASSWORD"])
            server.sendmail(SENDER, to_addresses, msg.as_string())
            logging.info(f"Email sent successfully to {', '.join(to_addresses)}.")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

def main():
    """Standalone newsletter generation."""
    logging.info("Starting enhanced weekly newsletter generation...")
    tickers_tuple = tuple(TICKERS)
    
    weekly_perf = get_overall_portfolio_performance(tickers_tuple, "weekly")
    ytd_perf = get_overall_portfolio_performance(tickers_tuple, "ytd")
    
    overall_weekly_change_pct = weekly_perf.get('overall_change_pct', 0.0)
    major_movers = weekly_perf.get('major_movers', [])
    overall_ytd_change_pct = ytd_perf.get('overall_change_pct', 0.0)
    
    market_block_md = generate_market_recap_with_search(TICKERS)
    
    weekly_direction = "increased" if overall_weekly_change_pct >= 0 else "decreased"
    ytd_direction = "up" if overall_ytd_change_pct >= 0 else "down"
    major_movers_str = "movements in positions like " + " and ".join(major_movers) if major_movers else "key positions"
    
    intro_summary_text = (
        f"This week your portfolio {weekly_direction} by {abs(overall_weekly_change_pct):.2f}%.\n"
        f"This was influenced by {major_movers_str}.\n"
        f"The broader market conditions and specific news affecting your holdings are detailed in the Market Recap below.\n"
        f"Year to date, your portfolio is {ytd_direction} {abs(overall_ytd_change_pct):.2f}%.\n\n"
        f"For more details about your specific holdings or questions on what to do next in your portfolio, "
        f"please feel free to contact an advisor here."
    )
    intro_summary_html = markdown2.markdown(intro_summary_text.replace('\n', '<br>'))
    
    holdings_blocks = generate_holdings_blocks(tickers_tuple)
    html_body, txt_body = render_email(intro_summary_html, intro_summary_text, market_block_md, holdings_blocks)
    
    send_gmail(html_body, txt_body)
    logging.info("Newsletter generation complete.")

if __name__ == "__main__":
    main()