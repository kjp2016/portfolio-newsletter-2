import logging
import os
import pandas as pd
from openai import OpenAI
from typing import Dict, Any, Tuple, List
import streamlit as st
import re
from datetime import datetime, timedelta
import json
from stock_data_service import get_stock_data_service

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
    Fetch current stock prices and company names using the stock data service.
    """
    if not tickers:
        return {}
    
    service = get_stock_data_service()
    return service.get_current_prices(tickers)

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_batch_price_performance(tickers: Tuple[str, ...], start_date: pd.Timestamp, end_date: pd.Timestamp, period_name: str = "period") -> Dict[str, Dict[str, Any]]:
    """
    Fetches historical price performance for multiple tickers using the stock data service.
    Replaces the Yahoo Finance implementation to avoid rate limiting issues.
    """
    if not tickers:
        return {}

    service = get_stock_data_service()
    return service.get_batch_price_performance(tickers, start_date, end_date, period_name)

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