import logging
import os
import pandas as pd
<<<<<<< HEAD
=======
import yfinance as yf
>>>>>>> 9aaf0de4fbf5218bdb4f517057009637e1fbd103
from openai import OpenAI
from typing import Dict, Any, Tuple, List
import streamlit as st
import re
<<<<<<< HEAD
from datetime import datetime, timedelta
import json
from stock_data_service import get_stock_data_service
=======
from datetime import datetime
import json
>>>>>>> 9aaf0de4fbf5218bdb4f517057009637e1fbd103

# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

# ---------- CONFIG ----------
TICKERS_STANDALONE_TEST = [
    "AMZN", "AVGO", "BMY", "NVDA",
    "MSFT", "AAPL"
]

# Initialize OpenAI client
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

<<<<<<< HEAD
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_batch_stock_data(tickers: Tuple[str, ...]) -> Dict[str, Dict[str, Any]]:
    """
    Fetch current stock prices and company names using the stock data service.
=======
def yahoo_friendly(tkr: str) -> str:
    """Converts a ticker to a yfinance-compatible format."""
    return tkr.replace("/", "-").replace(".", "-")

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_batch_stock_data(tickers: Tuple[str, ...]) -> Dict[str, Dict[str, Any]]:
    """
    Fetch current stock prices and company names using OpenAI search.
>>>>>>> 9aaf0de4fbf5218bdb4f517057009637e1fbd103
    """
    if not tickers:
        return {}
    
<<<<<<< HEAD
    service = get_stock_data_service()
    return service.get_current_prices(tickers)
=======
    tickers_str = ", ".join(tickers)
    today = datetime.now().strftime("%B %d, %Y")
    
    query = f"""Search for the most recent closing stock prices as of {today} for these companies: {tickers_str}

Return a JSON object with the ticker symbol, company name, and current price:
{{
    "AAPL": {{"company_name": "Apple Inc.", "current_price": 212.44}},
    "MSFT": {{"company_name": "Microsoft Corporation", "current_price": 420.50}}
}}

Include all requested tickers. Use the most recent closing price available."""
    
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-search-preview",
            web_search_options={
                "search_context_size": "low"
            },
            messages=[{"role": "user", "content": query}]
        )
        
        content = completion.choices[0].message.content
        logging.info(f"OpenAI response: {content[:200]}...")
        
        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            stock_data = json.loads(json_match.group())
            # Ensure all tickers are present
            for ticker in tickers:
                if ticker not in stock_data:
                    stock_data[ticker] = {'company_name': ticker, 'current_price': None}
                else:
                    # Ensure company_name is present
                    if 'company_name' not in stock_data[ticker]:
                        stock_data[ticker]['company_name'] = ticker
            return stock_data
        else:
            logging.error("No JSON found in OpenAI response")
            return {ticker: {'company_name': ticker, 'current_price': None} for ticker in tickers}
    
    except Exception as e:
        logging.error(f"Failed to fetch stock data from OpenAI: {e}")
        return {ticker: {'company_name': ticker, 'current_price': None} for ticker in tickers}
>>>>>>> 9aaf0de4fbf5218bdb4f517057009637e1fbd103

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_batch_price_performance(tickers: Tuple[str, ...], start_date: pd.Timestamp, end_date: pd.Timestamp, period_name: str = "period") -> Dict[str, Dict[str, Any]]:
    """
<<<<<<< HEAD
    Fetches historical price performance for multiple tickers using the stock data service.
    Replaces the Yahoo Finance implementation to avoid rate limiting issues.
=======
    Fetches historical price performance for multiple tickers using Yahoo Finance.
>>>>>>> 9aaf0de4fbf5218bdb4f517057009637e1fbd103
    """
    if not tickers:
        return {}

<<<<<<< HEAD
    service = get_stock_data_service()
    return service.get_batch_price_performance(tickers, start_date, end_date, period_name)
=======
    yf_tickers = [yahoo_friendly(t) for t in tickers]
    
    try:
        df = yf.download(
            yf_tickers,
            start=start_date - pd.Timedelta(days=7),
            end=end_date + pd.Timedelta(days=1),
            progress=False,
            auto_adjust=True,
            group_by='ticker' if len(tickers) > 1 else None,
            threads=False
        )
        
        if df.empty:
            logging.error("Historical download returned empty DataFrame")
            return {}

        performance_data = {}
        for i, ticker in enumerate(tickers):
            try:
                yf_ticker = yf_tickers[i]
                
                if len(tickers) > 1:
                    if yf_ticker in df.columns.levels[0]:
                        ticker_df = df[yf_ticker]
                    else:
                        logging.warning(f"{yf_ticker} not found in historical data")
                        performance_data[ticker] = {"error": "Ticker not found in download"}
                        continue
                else:
                    ticker_df = df
                
                if ticker_df.empty or ticker_df['Close'].dropna().empty:
                    performance_data[ticker] = {"error": "No price data available"}
                    continue
                
                # Timezone handling
                if ticker_df.index.tz is None:
                    ticker_df.index = ticker_df.index.tz_localize('UTC', ambiguous='infer', nonexistent='shift_forward')
                elif ticker_df.index.tz.zone != 'UTC':
                    ticker_df.index = ticker_df.index.tz_convert('UTC')

                # Get data within date range
                df_after_start = ticker_df[ticker_df.index >= start_date.normalize()].dropna()
                if df_after_start.empty:
                    performance_data[ticker] = {"error": "No data after start date"}
                    continue
                
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
                    performance_data[ticker] = {"error": "Invalid price data"}
                    continue

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
                
    except Exception as e:
        logging.error(f"Historical bulk download failed: {e}")
        return {}
            
    return performance_data
>>>>>>> 9aaf0de4fbf5218bdb4f517057009637e1fbd103

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

def main():
    """Test the bulk download approach"""
    print("\n=== Testing Bulk Download Approach ===")
    
    test_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NFLX", "TSLA"]
    print(f"\nFetching current prices for {test_tickers} using OpenAI search...")
    
    stock_data = get_batch_stock_data(tuple(test_tickers))
    print("\nResults:")
    for ticker, data in stock_data.items():
        price = data.get('current_price')
        if price:
            print(f"  {ticker}: ${price:.2f}")
        else:
            print(f"  {ticker}: Price unavailable")
    
    # Test historical data
    today = pd.Timestamp.utcnow()
    week_ago = today - pd.Timedelta(days=7)
    
    print(f"\nFetching weekly performance...")
    perf_data = get_batch_price_performance(tuple(test_tickers[:3]), week_ago, today, "weekly")
    
    print("\nWeekly Performance:")
    for ticker, perf in perf_data.items():
        if 'error' not in perf:
            print(f"  {ticker}: {perf['pct_change']:.2f}% ({perf['first_date']} to {perf['last_date']})")
        else:
            print(f"  {ticker}: {perf['error']}")

if __name__ == "__main__":
    main()