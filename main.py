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
import time
import re

# --- Local Modules ---
from portfolio_analysis import gpt_paragraph_for_holding
from market_recap import generate_market_recap_with_search

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S"
)

# --- Configurations ---
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    GMAIL_APP_PASSWORD = st.secrets["GMAIL_APP_PASSWORD"]
except (AttributeError, KeyError):
    from dotenv import load_dotenv
    load_dotenv()
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

client = OpenAI(api_key=OPENAI_API_KEY)
OPENAI_MODEL = "gpt-4o-mini"
SENDER_EMAIL = "keanejpalmer@gmail.com"
TEMPLATE_DIR = "./templates"


class OptimizedNewsletterGenerator:
    """
    Optimized newsletter generator that eliminates duplicate API calls and ensures accurate AI analysis.
    """
    
    def __init__(self):
        self.openai_client = client
        self.model = OPENAI_MODEL
        
        # Import Alpha Vantage service
        from alpha_vantage_service import get_alpha_vantage_service
        self.av_service = get_alpha_vantage_service()
    
    def get_portfolio_data_efficiently(self, tickers: Tuple[str, ...], holdings: Dict[str, float]) -> Dict[str, Any]:
        """
        Fetch all portfolio data efficiently in one pass, with bulletproof error handling.
        Returns both performance and company data to avoid duplicate API calls.
        """
        if not tickers:
            return {"performance_data": {}, "company_data": {}, "success_rate": 0.0}
        
        logging.info(f"=== Fetching portfolio data for {len(tickers)} tickers efficiently ===")
        start_time = time.time()
        
        # Step 1: Fetch historical performance data (this includes current prices)
        logging.info("Step 1: Fetching historical performance data...")
        today = pd.Timestamp.now()
        week_ago = today - pd.Timedelta(days=7)
        
        performance_data = {}
        successful_tickers = []
        failed_tickers = []
        
        # Process in batches of 5 to respect rate limits
        batch_size = 5
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i+batch_size]
            logging.info(f"Processing batch {i//batch_size + 1}: {batch}")
            
            try:
                batch_perf = self.av_service.get_batch_price_performance(batch, week_ago, today, "weekly")
                
                for ticker in batch:
                    data = batch_perf.get(ticker, {})
                    if 'error' not in data:
                        performance_data[ticker] = data
                        successful_tickers.append(ticker)
                        logging.info(f"✅ {ticker}: {data.get('pct_change', 0):.2f}%")
                    else:
                        failed_tickers.append(ticker)
                        logging.warning(f"❌ {ticker}: {data.get('error', 'Unknown error')}")
                        
            except Exception as e:
                logging.error(f"Batch error: {e}")
                for ticker in batch:
                    failed_tickers.append(ticker)
        
        # Step 2: Extract current prices from performance data to avoid duplicate API calls
        logging.info("Step 2: Extracting current prices from performance data...")
        company_data = {}
        
        for ticker, perf_data in performance_data.items():
            if 'last_close' in perf_data:
                company_data[ticker] = {
                    'current_price': perf_data['last_close'],
                    'company_name': self._get_company_name(ticker),
                    'last_updated': perf_data.get('last_date', 'Unknown')
                }
        
        # Calculate success rate
        success_rate = (len(successful_tickers) / len(tickers)) * 100 if tickers else 0.0
        
        # Calculate portfolio performance
        portfolio_performance = self._calculate_portfolio_performance(performance_data, holdings)
        
        duration = time.time() - start_time
        logging.info(f"=== Portfolio data fetch complete ===")
        logging.info(f"✅ Successful: {len(successful_tickers)}/{len(tickers)} ({success_rate:.1f}%)")
        logging.info(f"❌ Failed: {len(failed_tickers)} tickers")
        logging.info(f"💰 Portfolio change: {portfolio_performance['overall_change_pct']:.2f}%")
        logging.info(f"⏱️ Total time: {duration:.1f} seconds")
        
        if failed_tickers:
            logging.warning(f"Failed tickers: {', '.join(failed_tickers)}")
        
        return {
            "performance_data": performance_data,
            "company_data": company_data,
            "success_rate": success_rate,
            "failed_tickers": failed_tickers,
            "portfolio_performance": portfolio_performance
        }
    
    def _get_company_name(self, ticker: str) -> str:
        """Get company name from ticker - simplified to avoid extra API calls"""
        company_names = {
            'GOOGL': 'Alphabet Inc.',
            'MO': 'Altria Group Inc.',
            'AMZN': 'Amazon.com Inc.',
            'BRK-B': 'Berkshire Hathaway Inc.',
            'AVGO': 'Broadcom Inc.',
            'CAT': 'Caterpillar Inc.',
            'CRWD': 'CrowdStrike Holdings Inc.',
            'DE': 'Deere & Company',
            'EMR': 'Emerson Electric Co.',
            'GE': 'General Electric Company',
            'GEV': 'GE Vernova Inc.',
            'GD': 'General Dynamics Corporation',
            'HON': 'Honeywell International Inc.',
            'MSFT': 'Microsoft Corporation',
            'NVDA': 'NVIDIA Corporation',
            'PFE': 'Pfizer Inc.',
            'PM': 'Philip Morris International Inc.',
            'RTX': 'Raytheon Technologies Corporation',
            'NOW': 'ServiceNow Inc.',
            'SHEL': 'Shell plc',
            'XLE': 'Energy Select Sector SPDR Fund',
            'GLD': 'SPDR Gold Shares',
        }
        return company_names.get(ticker, ticker)
    
    def _calculate_portfolio_performance(self, performance_data: Dict[str, Any], holdings: Dict[str, float]) -> Dict[str, Any]:
        """Calculate portfolio performance with bulletproof error handling"""
        if not performance_data or not holdings:
            return {"overall_change_pct": 0.0, "major_movers": []}
        
        total_value_start = 0
        total_value_end = 0
        valid_holdings = 0
        
        for ticker, perf_data in performance_data.items():
            if 'error' not in perf_data and ticker in holdings:
                shares = holdings[ticker]
                if shares > 0 and 'first_close' in perf_data and 'last_close' in perf_data:
                    total_value_start += perf_data['first_close'] * shares
                    total_value_end += perf_data['last_close'] * shares
                    valid_holdings += 1
        
        if total_value_start > 0:
            overall_change_pct = ((total_value_end - total_value_start) / total_value_start) * 100
        else:
            overall_change_pct = 0.0
        
        # Get major movers (top 2 by absolute percentage change)
        major_movers = []
        sorted_by_impact = sorted(
            [(t, d) for t, d in performance_data.items() if 'error' not in d],
            key=lambda x: abs(x[1].get('pct_change', 0)),
            reverse=True
        )
        
        for ticker, data in sorted_by_impact[:2]:
            major_movers.append(f"{ticker} ({data['pct_change']:.2f}%)")
        
        return {
            "overall_change_pct": overall_change_pct,
            "major_movers": major_movers,
            "valid_holdings": valid_holdings
        }
    
    def generate_ai_analysis_with_correct_data(self, ticker: str, price_data: Dict[str, Any], company_name: str) -> str:
        """
        Generate AI analysis that MUST use the provided price data correctly.
        Uses a more restrictive prompt and validation.
        """
        try:
            # Extract exact values for the prompt
            start_price = price_data.get('first_close', 0)
            end_price = price_data.get('last_close', 0)
            abs_change = price_data.get('abs_change', 0)
            pct_change = price_data.get('pct_change', 0)
            direction = "UP" if pct_change >= 0 else "DOWN"
            
            # Create a very explicit prompt that forces the AI to use the provided data
            prompt = f"""
You are a financial analyst creating a brief analysis for a client newsletter.

**CRITICAL INSTRUCTIONS - READ CAREFULLY:**
1. You MUST use ONLY the exact price data provided below
2. Do NOT search for or use any other price information
3. The percentage change is EXACTLY {pct_change:.2f}% ({direction})
4. If the percentage is negative, the stock went DOWN
5. If the percentage is positive, the stock went UP
6. Return EXACTLY 4 bullet points - no more, no less
7. Do NOT include any market data, current prices, or extra information

EXACT PRICE DATA FOR {ticker} ({company_name}):
- Start Price: ${start_price:.2f}
- End Price: ${end_price:.2f}
- Price Change: ${abs_change:.2f}
- Percentage Change: {pct_change:.2f}% ({direction})
- Period: {price_data.get('period_name', 'weekly')}

Create EXACTLY 4 bullet points using this EXACT format (copy this structure exactly):

• **Performance**: {company_name} ({ticker}) moved {pct_change:.2f}% this week, from ${start_price:.2f} to ${end_price:.2f}.

• **Key Driver**: [Use web search to find the main news/factor that explains this {pct_change:.2f}% {direction.lower()} movement]

• **Additional Context**: [Use web search to find secondary factors or analyst opinions about {company_name}]

• **Outlook**: [Brief forward-looking sentiment based on recent developments]

**ABSOLUTE REQUIREMENTS:**
- Use EXACTLY {pct_change:.2f}% in your analysis
- Use web search only for news/context, not for price data
- Keep each bullet to 1-2 sentences
- Include source URLs for news
- Return ONLY the 4 bullet points above - nothing else
- Do NOT include any market data, current prices, or extra information
- If {pct_change:.2f}% is negative, say the stock went DOWN
- If {pct_change:.2f}% is positive, say the stock went UP
- Start with "• **Performance**:" and end with "• **Outlook**:"
"""
            
            logging.info(f"[AI] Generating analysis for {ticker} with {pct_change:.2f}% change ({direction})")
            
            response = self.openai_client.responses.create(
                model=self.model,
                tools=[{"type": "web_search_preview"}],
                input=prompt
            )
            
            analysis = response.output_text.strip()
            if not analysis:
                raise ValueError("Empty response from AI")
            
            # Validate that the response contains exactly 4 bullet points
            bullet_points = analysis.count('•')
            if bullet_points != 4:
                logging.error(f"[AI] {ticker}: Expected 4 bullet points, found {bullet_points}")
                # Try to extract only the bullet points if there are extras
                lines = analysis.split('\n')
                bullet_lines = [line.strip() for line in lines if line.strip().startswith('•')]
                if len(bullet_lines) >= 4:
                    analysis = '\n'.join(bullet_lines[:4])
                    logging.info(f"[AI] {ticker}: Extracted first 4 bullet points")
                else:
                    logging.error(f"[AI] {ticker}: Cannot extract 4 bullet points from response")
            
            # Check for unwanted market data
            unwanted_phrases = [
                'Stock market information',
                'The price is',
                'The latest open price',
                'The intraday',
                'The latest trade time',
                'currently with a change',
                'USD currently'
            ]
            
            for phrase in unwanted_phrases:
                if phrase in analysis:
                    logging.warning(f"[AI] {ticker}: Response contains unwanted market data: '{phrase}'")
                    # Remove lines containing unwanted market data
                    lines = analysis.split('\n')
                    clean_lines = [line for line in lines if not any(unwanted in line for unwanted in unwanted_phrases)]
                    analysis = '\n'.join(clean_lines)
                    logging.info(f"[AI] {ticker}: Cleaned unwanted market data from response")
                    break
            
            # Enhanced validation that the AI used the correct percentage
            expected_pct = pct_change
            pct_pattern = r'(\d+\.?\d*)%'
            pct_matches = re.findall(pct_pattern, analysis)
            
            if pct_matches:
                found_pct = float(pct_matches[0])
                if abs(found_pct - expected_pct) > 0.1:
                    logging.error(f"[AI] {ticker}: AI used wrong percentage! Expected {expected_pct:.2f}%, found {found_pct:.2f}%")
                    # Force the correct percentage into the analysis
                    analysis = analysis.replace(f"{found_pct:.2f}%", f"{expected_pct:.2f}%")
                    logging.info(f"[AI] {ticker}: Corrected percentage in analysis")
            
            # Enhanced direction validation
            expected_direction = "up" if expected_pct >= 0 else "down"
            analysis_lower = analysis.lower()
            
            # Check for direction mismatches
            if expected_direction == "up":
                if "down" in analysis_lower and "up" not in analysis_lower:
                    logging.error(f"[AI] {ticker}: AI said 'down' when stock went up {expected_pct:.2f}%")
                    # Try to fix the direction
                    analysis = analysis.replace("down", "up").replace("DOWN", "UP").replace("Down", "Up")
                    logging.info(f"[AI] {ticker}: Corrected direction in analysis")
            elif expected_direction == "down":
                if "up" in analysis_lower and "down" not in analysis_lower:
                    logging.error(f"[AI] {ticker}: AI said 'up' when stock went down {expected_pct:.2f}%")
                    # Try to fix the direction
                    analysis = analysis.replace("up", "down").replace("UP", "DOWN").replace("Up", "Down")
                    logging.info(f"[AI] {ticker}: Corrected direction in analysis")
            
            # Final validation - ensure the correct percentage appears in the analysis
            if f"{expected_pct:.2f}%" not in analysis:
                logging.warning(f"[AI] {ticker}: Correct percentage {expected_pct:.2f}% not found in analysis")
            
            logging.info(f"[AI] {ticker}: Analysis generated successfully")
            return analysis
            
        except Exception as e:
            logging.error(f"[AI] {ticker}: Analysis generation failed: {e}")
            return f"⚠️ Unable to generate analysis for {ticker}: {str(e)}"


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


def generate_newsletter_for_user(email: str, holdings: Dict[str, float]) -> bool:
    """
    Optimized newsletter generation using the new system.
    Eliminates duplicate API calls and ensures accurate AI analysis.
    """
    if not holdings:
        logging.warning(f"No holdings found for {email}. Skipping newsletter.")
        return False

    tickers_tuple = tuple(holdings.keys())
    subject = f"Your Weekly Portfolio Pulse – {datetime.utcnow():%b %d, %Y}"

    # Initialize optimized generator
    generator = OptimizedNewsletterGenerator()
    
    logging.info(f"=== Starting OPTIMIZED newsletter generation for {email} ===")
    logging.info(f"Portfolio: {len(tickers_tuple)} tickers")
    
    # Step 1: Fetch all data efficiently (one pass)
    portfolio_data = generator.get_portfolio_data_efficiently(tickers_tuple, holdings)
    
    performance_data = portfolio_data["performance_data"]
    company_data = portfolio_data["company_data"]
    success_rate = portfolio_data["success_rate"]
    portfolio_performance = portfolio_data["portfolio_performance"]
    
    # Step 2: Check if we have enough data
    if success_rate < 50.0:
        logging.error(f"Insufficient data for {email}: {success_rate:.1f}% success rate")
        return False
    
    overall_weekly_change_pct = portfolio_performance["overall_change_pct"]
    major_movers = portfolio_performance["major_movers"]
    
    # Check for data quality issues
    failed_tickers = portfolio_data.get('failed_tickers', [])
    
    if success_rate < 80.0:
        logging.warning(f"Low data quality for {email}: {success_rate:.1f}% success rate")
        logging.warning(f"Failed tickers: {', '.join(failed_tickers)}")

    # --- SKIP EMAIL IF PORTFOLIO DROPS MORE THAN 5% ---
    if overall_weekly_change_pct < -5.0:
        logging.warning(f"Portfolio for {email} dropped {overall_weekly_change_pct:.2f}% this week. Skipping email send.")
        return False

    # Step 3: Generate market recap
    logging.info("Step 3: Generating market recap...")
    market_block_md = generate_market_recap_with_search(list(tickers_tuple))
    logging.info("Step 3 complete: Market recap generated")
    
    # Step 4: Generate AI analysis for top movers
    logging.info("Step 4: Generating AI analysis for top movers...")
    
    # Get top 5 movers by absolute percentage change
    valid_performances = [(t, d) for t, d in performance_data.items() if 'error' not in d]
    valid_performances.sort(key=lambda x: abs(x[1].get('pct_change', 0)), reverse=True)
    top_movers = valid_performances[:5]
    
    holdings_blocks = []
    for ticker, price_data in top_movers:
        company_name = company_data.get(ticker, {}).get('company_name', ticker)
        analysis = generator.generate_ai_analysis_with_correct_data(ticker, price_data, company_name)
        
        if not analysis.startswith("⚠️"):
            holdings_blocks.append({
                "ticker": ticker,
                "para": analysis
            })
    
    logging.info(f"Step 4 complete: Generated analysis for {len(holdings_blocks)} holdings")

    # Step 5: Build email content
    weekly_direction = "increased" if overall_weekly_change_pct >= 0 else "decreased"
    major_movers_str = "movements in positions like " + " and ".join(major_movers) if major_movers else "key positions"

    intro_summary_text = (
        f"This week your portfolio {weekly_direction} by {abs(overall_weekly_change_pct):.2f}%.\n"
        f"This was influenced by {major_movers_str}.\n"
        f"The broader market conditions and specific news affecting your holdings are detailed in the Market Recap below."
    )

    intro_summary_html = markdown2.markdown(intro_summary_text.replace('\n', '<br>'))

    # Step 6: Render and send email
    logging.info("Step 5: Rendering and sending email...")
    html_body, txt_body = render_email(subject, intro_summary_html, intro_summary_text, market_block_md, holdings_blocks)
    send_gmail(subject, html_body, txt_body, recipients=[email])
    
    logging.info(f"=== OPTIMIZED newsletter generation complete for {email} ===")
    return True


# This block allows the script to be run directly for testing purposes
if __name__ == "__main__":
    logging.info("Running standalone test for optimized main.py...")
    # Example test case
    test_holdings = {"AAPL": 10.0, "MSFT": 20.0, "GOOGL": 5.0}
    test_email = "keanejpalmer@gmail.com"  # A test recipient
    
    if not all([OPENAI_API_KEY, GMAIL_APP_PASSWORD]):
         logging.error("Missing API keys (OPENAI_API_KEY, GMAIL_APP_PASSWORD). Aborting test.")
    else:
        generate_newsletter_for_user(test_email, test_holdings)

    logging.info("Standalone test finished.")