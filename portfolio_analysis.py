import logging
import os
import pandas as pd
import yfinance as yf
from openai import OpenAI
from typing import Dict, Any, Tuple, List
import streamlit as st

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

def yahoo_friendly(tkr: str) -> str:
    """Converts a ticker to a yfinance-compatible format."""
    return tkr.replace("/", "-").replace(".", "-")

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_batch_stock_data(tickers: Tuple[str, ...]) -> Dict[str, Dict[str, Any]]:
    """
    Fetch current prices using bulk download ONLY - no .info calls!
    This completely avoids the rate-limited quoteSummary endpoint.
    """
    if not tickers:
        return {}
    
    logging.info(f"Fetching current prices for {len(tickers)} tickers using bulk download (no .info calls)")
    
    yf_tickers = [yahoo_friendly(t) for t in tickers]
    batch_data = {}
    
    try:
        # Download last 5 days of data for all tickers at once
        # This uses a different Yahoo endpoint that's not rate-limited like .info
        df = yf.download(
            yf_tickers,
            period="5d",
            interval="1d",
            progress=False,
            auto_adjust=True,
            group_by='ticker' if len(tickers) > 1 else None,
            threads=False
        )
        
        if df.empty:
            logging.error("Bulk download returned empty DataFrame")
            # Return with None prices instead of trying .info
            return {ticker: {'company_name': ticker, 'current_price': None} for ticker in tickers}
        
        # Extract the latest closing price for each ticker
        for i, ticker in enumerate(tickers):
            yf_ticker = yf_tickers[i]
            try:
                if len(tickers) > 1:
                    # Multi-ticker download creates multi-level columns
                    if yf_ticker in df.columns.levels[0]:
                        ticker_close = df[yf_ticker]['Close'].dropna()
                        if not ticker_close.empty:
                            last_close = ticker_close.iloc[-1]
                        else:
                            last_close = None
                    else:
                        logging.warning(f"{yf_ticker} not found in download results")
                        last_close = None
                else:
                    # Single ticker download has simple columns
                    ticker_close = df['Close'].dropna()
                    if not ticker_close.empty:
                        last_close = ticker_close.iloc[-1]
                    else:
                        last_close = None
                
                batch_data[ticker] = {
                    'company_name': ticker,  # Just use ticker as name - no .info calls!
                    'current_price': float(last_close) if last_close is not None else None
                }
                
            except Exception as e:
                logging.warning(f"Could not extract price for {ticker}: {e}")
                batch_data[ticker] = {'company_name': ticker, 'current_price': None}
        
        return batch_data
        
    except Exception as e:
        logging.error(f"Bulk download failed: {e}")
        # Return with None prices instead of retrying with .info
        return {ticker: {'company_name': ticker, 'current_price': None} for ticker in tickers}

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_batch_price_performance(tickers: Tuple[str, ...], start_date: pd.Timestamp, end_date: pd.Timestamp, period_name: str = "period") -> Dict[str, Dict[str, Any]]:
    """
    Fetches historical price performance for multiple tickers.
    This already uses bulk download which is not rate-limited like .info
    """
    if not tickers:
        return {}

    yf_tickers = [yahoo_friendly(t) for t in tickers]
    
    try:
        # This endpoint is much less rate-limited than .info
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

# Keep the GPT functions unchanged
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
    print("\n=== Testing Bulk Download Approach (No .info calls) ===")
    
    test_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NFLX", "TSLA"]
    print(f"\nFetching current prices for {test_tickers} using bulk download...")
    
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