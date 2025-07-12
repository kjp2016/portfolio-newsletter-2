import logging
import os
import pandas as pd
from openai import OpenAI
from typing import Dict, Any, Tuple, List
import streamlit as st
import re
from datetime import datetime, timedelta
import json
from hybrid_finance_service import get_hybrid_finance_service

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

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_batch_stock_data(tickers: Tuple[str, ...]) -> Dict[str, Dict[str, Any]]:
    """
    Fetch current stock prices using Alpha Vantage API directly.
    """
    if not tickers:
        return {}
    
    from alpha_vantage_service import get_alpha_vantage_service
    service = get_alpha_vantage_service()
    return service.get_current_prices(tickers)

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_batch_price_performance(tickers: Tuple[str, ...], start_date: pd.Timestamp, end_date: pd.Timestamp, period_name: str = "period") -> Dict[str, Dict[str, Any]]:
    """
    Fetches historical price performance for multiple tickers using Alpha Vantage API directly.
    """
    if not tickers:
        return {}

    from alpha_vantage_service import get_alpha_vantage_service
    service = get_alpha_vantage_service()
    return service.get_batch_price_performance(tickers, start_date, end_date, period_name)

def build_prompt_for_holding(price_block: dict, long_name: str) -> str:
    period_desc = price_block.get('period_name', 'recent performance')
    direction = "up" if price_block['pct_change'] >= 0 else "down"
    
    # Add debugging to ensure we're using the correct price data
    logging.info(f"[DEBUG] Building prompt for {price_block['ticker']}: pct_change={price_block['pct_change']:.2f}%, abs_change=${price_block['abs_change']:.2f}")
    
    return (
        f"Create a bullet-point analysis for a client newsletter about {long_name} ({price_block['ticker']}).\n"
        f"The stock is {direction} ${abs(price_block['abs_change'])} ({price_block['pct_change']:.2f}%) for the {period_desc}.\n\n"
        f"Format your response as exactly 4 bullet points using this structure:\n"
        f"• **Performance**: [One sentence about the price movement and percentage change]\n"
        f"• **Key Driver**: [Main factor or news that influenced this performance, with cited source]\n"
        f"• **Additional Context**: [Secondary factor, analyst opinion, or sector trend, with cited source]\n"
        f"• **Outlook**: [Brief forward-looking sentiment or upcoming catalyst]\n\n"
        f"Requirements:\n- Use **credible, cited news sources** found via web search\n"
        f"- Include inline URL citations (e.g., [Source URL]) for any news mentioned\n"
        f"- Keep each bullet point to 1-2 sentences maximum\n"
        f"- Use clear, professional language without jargon\n"
        f"- Focus on information from the past month\n"
        f"- Do NOT include raw market data, stock quotes, or technical indicators\n"
        f"- Return ONLY the 4 bullet points in the exact format specified above\n\n"
        f"Return ONLY the bullet points, no introduction, conclusion, or other text."
    )

def gpt_paragraph_for_holding(price_block: dict, long_name: str, openai_client: OpenAI, model_name: str) -> str:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            prompt = build_prompt_for_holding(price_block, long_name)
            logging.info(f"[GPT - {price_block['ticker']}] Generating holding analysis (attempt {attempt + 1})...")
            
            # Use the Responses API with web search tools
            response = openai_client.responses.create(
                model="gpt-4o-mini",
                tools=[{"type": "web_search_preview"}],
                input=prompt
            )
            
            # Extract the output text from the response
            output_text = response.output_text
            if output_text is None:
                raise ValueError("OpenAI returned None content")
            
            analysis = output_text.strip()
            if not analysis:
                raise ValueError("OpenAI returned an empty response")
            
            # Validate the format - ensure it contains bullet points and key sections
            has_bullets = any(char in analysis for char in ['•', '*', '-'])
            has_performance = any(phrase in analysis for phrase in ['Performance', 'performance'])
            has_key_driver = any(phrase in analysis for phrase in ['Key Driver', 'key driver'])
            has_additional_context = any(phrase in analysis for phrase in ['Additional Context', 'additional context'])
            has_outlook = any(phrase in analysis for phrase in ['Outlook', 'outlook'])
            
            if not has_bullets or not (has_performance and has_key_driver and has_additional_context and has_outlook):
                raise ValueError("Response does not contain expected bullet-point format")
            
            logging.info(f"[GPT - {price_block['ticker']}] Successfully generated analysis (attempt {attempt + 1})")
            return analysis
            
        except Exception as e:
            logging.error(f"[GPT - {price_block['ticker']}] Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                # Last attempt failed, return error message
                return f"⚠️ Unable to generate analysis for {price_block['ticker']} after {max_retries} attempts: {str(e)}"
            # Wait before retrying
            import time
            time.sleep(2 ** attempt)  # Exponential backoff
    
    return f"⚠️ Unable to generate analysis for {price_block['ticker']} after all attempts."

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
    
    # Test historical data with proper timestamp validation
    today = pd.Timestamp.now()
    week_ago = today - pd.Timedelta(days=7)
    
    # Ensure timestamps are valid before passing to function
    if week_ago is pd.NaT or today is pd.NaT:
        print("Error: Invalid timestamps generated")
        return
    
    # Convert to proper Timestamp objects
    week_ago_ts = week_ago
    today_ts = today
    
    print(f"\nFetching weekly performance...")
    if isinstance(week_ago_ts, pd.Timestamp) and isinstance(today_ts, pd.Timestamp):
        perf_data = get_batch_price_performance(tuple(test_tickers[:3]), week_ago_ts, today_ts, "weekly")
    else:
        print("Error: Invalid timestamps")
        return
    
    print("\nWeekly Performance:")
    for ticker, perf in perf_data.items():
        if 'error' not in perf:
            print(f"  {ticker}: {perf['pct_change']:.2f}% ({perf['first_date']} to {perf['last_date']})")
        else:
            print(f"  {ticker}: {perf['error']}")

if __name__ == "__main__":
    main()