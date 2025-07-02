import logging
import traceback
import os
import pandas as pd
import yfinance as yf
from openai import OpenAI
from typing import Dict, Any, Tuple, List
import time
import streamlit as st
import requests
import random

# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
# -----------------------------

# ---------- CONFIG (for standalone testing of this module) ----------
TICKERS_STANDALONE_TEST = [
    "AMZN", "AVGO", "BMY", "NVDA",
    "MSFT", "AAPL"
]

# Rate limiting configuration - MORE AGGRESSIVE
YAHOO_DELAY_BETWEEN_REQUESTS = 3.0  # Increased to 3 seconds
YAHOO_DELAY_AFTER_429 = 30.0  # Wait 30 seconds after a 429 error
YAHOO_MAX_RETRIES = 3
# -----------------------------

def yahoo_friendly(tkr: str) -> str:
    """Converts a ticker to a yfinance-compatible format."""
    return tkr.replace("/", "-").replace(".", "-")

# ---------- SINGLE TICKER DATA FETCHING ----------
@st.cache_data(ttl=3600)  # Cache for 1 hour instead of 15 minutes
def get_single_stock_data(ticker: str, attempt: int = 0) -> Dict[str, Any]:
    """Fetch and cache data for a single ticker with exponential backoff."""
    yf_ticker = yahoo_friendly(ticker)
    
    # Add jitter to avoid synchronized requests
    if attempt > 0:
        wait_time = YAHOO_DELAY_AFTER_429 * (2 ** (attempt - 1)) + random.uniform(0, 5)
        logging.warning(f"Waiting {wait_time:.1f}s before retry attempt {attempt} for {ticker}")
        time.sleep(wait_time)
    
    try:
        ticker_obj = yf.Ticker(yf_ticker)
        info = ticker_obj.info
        
        if not info or 'symbol' not in info:
            # Try fast_info as fallback
            fast_info = ticker_obj.fast_info
            if fast_info and 'lastPrice' in fast_info:
                return {
                    'company_name': ticker,
                    'current_price': fast_info.get('lastPrice')
                }
            raise ValueError("Info is empty or invalid")
            
        return {
            'company_name': info.get('longName') or info.get('shortName', ticker),
            'current_price': info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
        }
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429 and attempt < YAHOO_MAX_RETRIES:
            logging.error(f"429 Too Many Requests for {ticker}. Attempt {attempt + 1}/{YAHOO_MAX_RETRIES}")
            return get_single_stock_data(ticker, attempt + 1)
        else:
            logging.error(f"HTTP error for {ticker} after {attempt} attempts: {e}")
            return {'company_name': ticker, 'current_price': None}
            
    except Exception as e:
        if "429" in str(e) and attempt < YAHOO_MAX_RETRIES:
            logging.error(f"429 error in exception for {ticker}. Attempt {attempt + 1}/{YAHOO_MAX_RETRIES}")
            return get_single_stock_data(ticker, attempt + 1)
        else:
            logging.error(f"Could not fetch data for {ticker}: {e}")
            return {'company_name': ticker, 'current_price': None}

# ---------- BATCH DATA FETCHING ----------
def get_batch_stock_data(tickers: Tuple[str, ...]) -> Dict[str, Dict[str, Any]]:
    """Fetch data for multiple tickers with aggressive rate limiting."""
    if not tickers:
        return {}
    
    batch_data = {}
    
    # Check if we have cached data first
    cached_count = 0
    for ticker in tickers:
        # This checks if data is already in cache without making a request
        cache_key = f"get_single_stock_data-{(ticker, 0)}"
        if cache_key in st.session_state:
            cached_count += 1
    
    logging.info(f"Processing {len(tickers)} tickers ({cached_count} potentially cached)")
    
    for i, ticker in enumerate(tickers):
        # Always add delay between requests to avoid rate limits
        if i > 0:
            delay = YAHOO_DELAY_BETWEEN_REQUESTS + random.uniform(0, 1)
            logging.info(f"Waiting {delay:.1f}s before fetching {ticker} ({i+1}/{len(tickers)})")
            time.sleep(delay)
        
        batch_data[ticker] = get_single_stock_data(ticker)
    
    return batch_data

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_batch_price_performance(tickers: Tuple[str, ...], start_date: pd.Timestamp, end_date: pd.Timestamp, period_name: str = "period") -> Dict[str, Dict[str, Any]]:
    """
    Fetches historical price performance for multiple tickers.
    Uses batch download which is less prone to rate limiting.
    """
    if not tickers:
        return {}

    yf_tickers = [yahoo_friendly(t) for t in tickers]
    
    # Try to download with retries
    df = None
    for attempt in range(YAHOO_MAX_RETRIES):
        try:
            if attempt > 0:
                wait_time = YAHOO_DELAY_AFTER_429 * (2 ** (attempt - 1))
                logging.warning(f"Waiting {wait_time}s before retry attempt {attempt + 1} for batch download")
                time.sleep(wait_time)
            
            df = yf.download(
                yf_tickers,
                start=start_date - pd.Timedelta(days=7),
                end=end_date + pd.Timedelta(days=1),
                progress=False,
                auto_adjust=True,
                group_by='ticker',
                threads=False  # Disable multi-threading
            )
            
            if df is not None and not df.empty:
                break
                
        except Exception as e:
            if "429" in str(e) or "Too Many Requests" in str(e):
                logging.error(f"Rate limited on batch download attempt {attempt + 1}")
                if attempt == YAHOO_MAX_RETRIES - 1:
                    logging.error("Max retries reached for batch download")
                    return {}
            else:
                logging.error(f"Error in batch download: {e}")
                return {}

    if df is None or df.empty:
        logging.error("yfinance download returned empty DataFrame for all tickers")
        return {}

    performance_data = {}
    for i, ticker in enumerate(tickers):
        try:
            yf_ticker = yf_tickers[i]
            
            # Handle multi-ticker DataFrames
            if len(tickers) > 1:
                if yf_ticker in df.columns.levels[0]:
                    ticker_df = df[yf_ticker]
                else:
                    logging.warning(f"{yf_ticker} not in downloaded data")
                    continue
            else:
                ticker_df = df
            
            if ticker_df.empty:
                raise ValueError(f"No data available for {ticker}")
            
            # Timezone handling
            if ticker_df.index.tz is None:
                ticker_df.index = ticker_df.index.tz_localize('UTC', ambiguous='infer', nonexistent='shift_forward')
            elif ticker_df.index.tz.zone != 'UTC':
                ticker_df.index = ticker_df.index.tz_convert('UTC')

            # Get data within date range
            df_after_start = ticker_df[ticker_df.index >= start_date.normalize()].dropna()
            if df_after_start.empty:
                raise ValueError(f"No data on or after start date")
            
            first_row = df_after_start.iloc[0]
            first_close = float(first_row["Close"])
            actual_start_date_ts = first_row.name

            df_before_end = ticker_df[ticker_df.index <= end_date].dropna()
            if df_before_end.empty:
                last_row = first_row
            else:
                last_row = df_before_end.iloc[-1]

            last_close = float(last_row["Close"])
            actual_end_date_ts = last_row.name

            if pd.isna(first_close) or pd.isna(last_close):
                raise ValueError("NaN price found")

            abs_change = last_close - first_close
            pct_change = (abs_change / first_close) * 100 if first_close != 0 else 0.0

            performance_data[ticker] = {
                "ticker": ticker.upper(),
                "period_name": period_name,
                "first_date": actual_start_date_ts.date().isoformat(),
                "last_date": actual_end_date_ts.date().isoformat(),
                "first_close": round(first_close, 2),
                "last_close": round(last_close, 2),
                "abs_change": round(abs_change, 2),
                "pct_change": round(pct_change, 2),
            }
            
        except Exception as e:
            logging.warning(f"Could not calculate performance for {ticker}: {e}")
            performance_data[ticker] = {"error": str(e)}
            
    return performance_data

def build_prompt_for_holding(price_block: dict, long_name: str) -> str:
    period_desc = price_block.get('period_name', 'recent performance')
    direction = "up" if price_block['pct_change'] >= 0 else "down"
    return (
        f"Create a bullet-point analysis for a client newsletter about {long_name} ({price_block['ticker']}).\n"
        f"The stock is {direction} ${abs(price_block['abs_change'])} ({price_block['pct_change']}%) for the {period_desc}.\n\n"
        f"Format your response as exactly 3-4 bullet points using this structure:\n"
        f"• **Performance**: [One sentence about the price movement and percentage change]\n"
        f"• **Key Driver**: [Main factor or news that influenced this performance, with cited source]\n"
        f"• **Additional Context**: [Secondary factor, analyst opinion, or sector trend, with cited source]\n"
        f"• **Outlook**: [Brief forward-looking sentiment or upcoming catalyst]\n\n"
        f"Requirements:\n- Use **credible, cited news sources** found via web search\n"
        f"- Include inline URL citations (e.g., [Source URL]) for any news mentioned\n"
        f"- Keep each bullet point to 1-2 sentences maximum\n"
        f"- Use clear, professional language without jargon\n"
        f"- Focus on information from the past month\n\n"
        f"Return ONLY the bullet points, no introduction or conclusion."
    )

def gpt_paragraph_for_holding(price_block: dict, long_name: str, openai_client: OpenAI, model_name: str) -> str:
    try:
        prompt = build_prompt_for_holding(price_block, long_name)
        logging.info(f"[GPT - {price_block['ticker']}] Generating holding analysis...")
        response = openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a financial news analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        analysis = response.choices[0].message.content.strip()
        if not analysis:
            raise ValueError("API call returned an empty response.")
        return analysis
    except Exception as e:
        logging.error(f"[GPT - {price_block['ticker']}] API call for holding analysis failed: {e}")
        return f"⚠️ GPT call failed for {price_block['ticker']}: {e}"

def main():  # For standalone testing
    test_api_key = os.environ.get("OPENAI_API_KEY")
    if not test_api_key:
        logging.error("OPENAI_API_KEY env var not set. Aborting test.")
        return
        
    test_client = OpenAI(api_key=test_api_key)
    test_model = "gpt-4o-mini"
    today = pd.Timestamp.utcnow()
    
    print("\n--- Testing Rate-Limited Stock Data Fetching ---")
    test_tickers = ["AAPL", "MSFT", "GOOGL"]
    print(f"Fetching data for {test_tickers} with {YAHOO_DELAY_BETWEEN_REQUESTS}s delays...")
    
    stock_data = get_batch_stock_data(tuple(test_tickers))
    for ticker, data in stock_data.items():
        print(f"{ticker}: {data.get('company_name')} - ${data.get('current_price')}")
    
    print("\n--- Batch Historical Performance Test (YTD) ---")
    ytd_start = today.replace(month=1, day=1).normalize()
    ytd_perfs = get_batch_price_performance(tuple(TICKERS_STANDALONE_TEST), ytd_start, today, period_name="year-to-date")
    for tkr, perf in ytd_perfs.items():
        if 'error' not in perf:
            logging.info(f"[{tkr}] YTD: {perf['first_date']} (${perf['first_close']}) -> {perf['last_date']} (${perf['last_close']}) | Δ {perf['pct_change']:.2f}%")
        else:
            logging.error(f"[{tkr}] YTD Test Error: {perf['error']}")

if __name__ == "__main__":
    main()