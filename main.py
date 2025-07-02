import os
import logging
import smtplib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import traceback
from openai import OpenAI
import markdown2
import pandas as pd

# ---------- Local Modules ----------
from market_recap import generate_market_recap_with_search
from portfolio_analysis import (
    get_price_performance,
    company_name,
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

def get_overall_portfolio_performance(portfolio_tickers: List[str], period: str, holdings: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """Calculate overall portfolio performance."""
    today = pd.Timestamp.utcnow()
    if period == "weekly":
        start_date = today - timedelta(days=7)
    elif period == "ytd":
        start_date = today.replace(month=1, day=1).normalize()
    else:
        raise ValueError("Period must be 'weekly' or 'ytd'")

    individual_performances = []
    total_value_start = 0
    total_value_end = 0
    
    for ticker in portfolio_tickers:
        try:
            perf = get_price_performance(ticker, start_date, today)
            if holdings and ticker in holdings:
                shares = holdings[ticker]
                value_start = perf['first_close'] * shares
                value_end = perf['last_close'] * shares
                total_value_start += value_start
                total_value_end += value_end
                perf['value_change'] = value_end - value_start
                perf['shares'] = shares
            individual_performances.append(perf)
        except Exception as e:
            logging.warning(f"Could not fetch {period} performance for {ticker}: {e}")
            individual_performances.append({"ticker": ticker, "pct_change": 0.0, "abs_change": 0.0, "error": str(e)})

    if not individual_performances:
        return {"overall_change_pct": 0.0, "major_movers": [], "error": "No performance data for any ticker."}

    valid_performances = [p for p in individual_performances if 'error' not in p]
    if not valid_performances:
        return {"overall_change_pct": 0.0, "major_movers": [], "error": "All tickers failed to fetch performance data."}

    if holdings and total_value_start > 0:
        overall_change_pct = ((total_value_end - total_value_start) / total_value_start) * 100
    else:
        total_pct_change = sum(p['pct_change'] for p in valid_performances)
        overall_change_pct = total_pct_change / len(valid_performances) if valid_performances else 0.0

    major_movers_details = []
    if period == "weekly" and valid_performances:
        sorted_by_impact = sorted(valid_performances, key=lambda x: abs(x.get('pct_change', 0.0)), reverse=True)
        positive_movers = sorted([p for p in sorted_by_impact if p.get('pct_change', 0) > 0], key=lambda x: x.get('pct_change', 0), reverse=True)
        negative_movers = sorted([p for p in sorted_by_impact if p.get('pct_change', 0) < 0], key=lambda x: x.get('pct_change', 0))
        unique_movers_set = set()
        if positive_movers:
            mover = positive_movers[0]
            major_movers_details.append(f"{mover['ticker']} ({mover['pct_change']:.2f}%)")
            unique_movers_set.add(mover['ticker'])
        if negative_movers:
            mover = negative_movers[0]
            if mover['ticker'] not in unique_movers_set:
                major_movers_details.append(f"{mover['ticker']} ({mover['pct_change']:.2f}%)")
                unique_movers_set.add(mover['ticker'])
        if len(major_movers_details) < 2 and len(sorted_by_impact) > len(major_movers_details):
            for p_impact in sorted_by_impact:
                if p_impact['ticker'] not in unique_movers_set:
                    major_movers_details.append(f"{p_impact['ticker']} ({p_impact['pct_change']:.2f}%)")
                    unique_movers_set.add(p_impact['ticker'])
                    if len(major_movers_details) >= 2:
                        break
    
    return {"overall_change_pct": overall_change_pct, "major_movers": major_movers_details}

def generate_holdings_blocks(portfolio_tickers: List[str]) -> List[dict]:
    """Generate holdings analysis blocks."""
    holdings = []
    today = pd.Timestamp.utcnow()
    start_mtd = today.replace(day=1).normalize()
    for ticker in portfolio_tickers:
        try:
            price_data = get_price_performance(ticker, start_mtd, today, period_name="month-to-date")
            name = company_name(ticker)
            para = gpt_paragraph_for_holding(price_data, name, client, OPENAI_MODEL)
            holdings.append({"ticker": ticker, "para": para})
            logging.info(f"Generated analysis for {ticker}.")
        except Exception as e:
            logging.warning(f"[{ticker}] skipped for holdings block: {e}")
            holdings.append({"ticker": ticker, "para": f"⚠️ Unable to fetch or generate detailed data for {ticker}."})
    return holdings

def render_email(intro_summary_html: str, intro_summary_text: str, market_md: str, holdings: List[dict]) -> tuple[str, str]:
    """Render email templates."""
    market_html = markdown2.markdown(market_md)
    enriched_holdings = []
    for h in holdings:
        h_copy = h.copy()
        h_copy["para_html"] = markdown2.markdown(h["para"])
        enriched_holdings.append(h_copy)
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"])
    )
    current_date_str = datetime.utcnow().strftime("%B %d, %Y")
    html = env.get_template(HTML_TEMPLATE).render(
        subject=SUBJECT,
        date=current_date_str,
        intro_summary_html=intro_summary_html,
        market_block_html=market_html,
        holdings=enriched_holdings
    )
    text = env.get_template(PLAINTEXT_TEMPLATE).render(
        subject=SUBJECT,
        date=current_date_str,
        intro_summary_text=intro_summary_text,
        market_block=market_md,
        holdings=holdings
    )
    return html, text

def send_gmail(html_body: str, txt_body: str, recipients: Optional[List[str]] = None):
    """Send email via Gmail with optional custom recipients."""
    try:
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        sender_email = SENDER
        sender_password = st.secrets["GMAIL_APP_PASSWORD"]
        to_addresses = recipients if recipients else RECIPIENTS
        if not sender_password:
            logging.error("GMAIL_APP_PASSWORD environment variable not set or empty. Email not sent.")
            return
        msg = MIMEMultipart("alternative")
        msg["Subject"] = SUBJECT
        msg["From"] = sender_email
        msg["To"] = ", ".join(to_addresses)
        msg.attach(MIMEText(txt_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_addresses, msg.as_string())
            logging.info(f"Email sent successfully to {', '.join(to_addresses)} via Gmail.")
    except Exception as e:
        logging.error(f"Failed to send email via Gmail: {e}")

def main():
    """Standalone newsletter generation."""
    logging.info("Starting enhanced weekly newsletter generation...")
    weekly_perf = get_overall_portfolio_performance(TICKERS, "weekly")
    ytd_perf = get_overall_portfolio_performance(TICKERS, "ytd")
    overall_weekly_change_pct = weekly_perf.get('overall_change_pct', 0.0)
    major_movers = weekly_perf.get('major_movers', [])
    overall_ytd_change_pct = ytd_perf.get('overall_change_pct', 0.0)
    market_block_md = generate_market_recap_with_search(TICKERS)
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
    intro_summary_html = markdown2.markdown(intro_summary_text.replace('\n', '<br>'))
    holdings_blocks = generate_holdings_blocks(TICKERS)
    html_body, txt_body = render_email(intro_summary_html, intro_summary_text, market_block_md, holdings_blocks)
    send_gmail(html_body, txt_body)
    logging.info("Newsletter generation complete.")

if __name__ == "__main__":
    main()