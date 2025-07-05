#!/usr/bin/env python3
"""
Debug script to trace historical price retrieval issues.
This will show us exactly what prompts are being sent and what responses we get.
"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from openai import OpenAI
import json
import re
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

# Initialize OpenAI client
try:
    import streamlit as st
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except (AttributeError, KeyError):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def debug_historical_prices():
    """Debug the historical price retrieval process step by step."""
    
    print("=== DEBUGGING HISTORICAL PRICE RETRIEVAL ===\n")
    
    # Test tickers
    tickers = ("AMZN", "MSFT", "GOOGL")
    
    # Calculate dates
    today = pd.Timestamp.utcnow()
    week_ago = today - timedelta(days=7)
    
    print(f"Date calculations:")
    print(f"  Today: {today}")
    print(f"  Week ago: {week_ago}")
    print(f"  Week ago formatted: {week_ago.strftime('%B %d, %Y')}")
    print()
    
    # First, get current prices
    print("1. Getting current prices...")
    current_query = f"""You are a financial data researcher. Your task is to find the CURRENT stock prices for these companies: {', '.join(tickers)}

Return ONLY a JSON object with the current prices:

{{
    "AMZN": {{"company_name": "Amazon.com Inc.", "current_price": 223.41}},
    "MSFT": {{"company_name": "Microsoft Corporation", "current_price": 498.84}},
    "GOOGL": {{"company_name": "Alphabet Inc.", "current_price": 179.53}}
}}

Requirements:
- Use web search to find current market prices
- Return realistic stock prices
- Include company names
- Return ONLY the JSON object"""

    print(f"CURRENT PRICES PROMPT:")
    print(f"{'='*50}")
    print(current_query)
    print(f"{'='*50}")
    
    try:
        current_response = client.responses.create(
            model="gpt-4o-mini",
            tools=[{"type": "web_search_preview"}],
            input=current_query
        )
        
        print(f"CURRENT PRICES RESPONSE:")
        print(f"{'='*50}")
        print(current_response.output_text)
        print(f"{'='*50}")
        
        # Parse current prices (handle triple backticks)
        output_text = current_response.output_text
        json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', output_text)
        if not json_match:
            json_match = re.search(r'\{[\s\S]*\}', output_text)
        if json_match:
            json_str = json_match.group(1) if json_match.groups() else json_match.group(0)
            current_data = json.loads(json_str)
            print(f"Parsed current prices: {current_data}")
        else:
            print("No JSON found in current prices response!")
            return
        print()
        
    except Exception as e:
        print(f"Error getting current prices: {e}")
        return
    
    # Now get historical prices
    print("2. Getting historical prices...")
    start_date_str = week_ago.strftime("%B %d, %Y")
    tickers_str = ", ".join(tickers)
    
    historical_query = f"""You are a financial data researcher. Your task is to find the ACTUAL historical closing stock prices for these companies on {start_date_str}: {tickers_str}

STEP-BY-STEP INSTRUCTIONS:
1. For each ticker, search the web for "historical stock price [TICKER] {start_date_str}"
2. Look for financial websites like Yahoo Finance, MarketWatch, Alpha Vantage, or similar
3. Find the CLOSING PRICE for the specified date
4. If {start_date_str} was a weekend/holiday, find the closing price from the most recent trading day before that date
5. Do NOT use current prices - only use historical closing prices from the specified date
6. IMPORTANT: The prices you return must be DIFFERENT from current market prices

Return ONLY a JSON object with the historical closing prices:

{{
    "AMZN": {{"historical_price": 185.92}},
    "MSFT": {{"historical_price": 388.47}},
    "GOOGL": {{"historical_price": 165.23}}
}}

CRITICAL REQUIREMENTS:
- Search for ACTUAL historical data, not current prices
- Use web search to find real historical closing prices
- If the date was a weekend/holiday, use the previous trading day's closing price
- All prices must be realistic stock prices (typically $1-$1000 for most stocks)
- Do NOT return current market prices under any circumstances
- Search multiple financial websites to verify accuracy
- The historical prices MUST be different from current prices to be valid"""

    print(f"HISTORICAL PRICES PROMPT:")
    print(f"{'='*50}")
    print(historical_query)
    print(f"{'='*50}")
    
    try:
        historical_response = client.responses.create(
            model="gpt-4o-mini",
            tools=[{"type": "web_search_preview"}],
            input=historical_query
        )
        
        print(f"HISTORICAL PRICES RESPONSE:")
        print(f"{'='*50}")
        print(historical_response.output_text)
        print(f"{'='*50}")
        
        # Try to extract JSON
        output_text = historical_response.output_text
        json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', output_text)
        if not json_match:
            json_match = re.search(r'\{[\s\S]*\}', output_text)
        
        if json_match:
            json_str = json_match.group(1) if json_match.groups() else json_match.group(0)
            historical_data = json.loads(json_str)
            print(f"Parsed historical data: {historical_data}")
        else:
            print("No JSON found in response!")
            
    except Exception as e:
        print(f"Error getting historical prices: {e}")
        return
    
    print("\n3. Comparing prices...")
    for ticker in tickers:
        if ticker in current_data and ticker in historical_data:
            current_price = current_data[ticker].get('current_price')
            historical_price = historical_data[ticker].get('historical_price')
            
            print(f"  {ticker}:")
            print(f"    Current: ${current_price}")
            print(f"    Historical ({start_date_str}): ${historical_price}")
            
            if current_price and historical_price:
                diff = abs(current_price - historical_price)
                pct_diff = (diff / historical_price) * 100 if historical_price != 0 else 0
                print(f"    Difference: ${diff:.2f} ({pct_diff:.2f}%)")
                
                if abs(current_price - historical_price) < 0.01:
                    print(f"    ⚠️  WARNING: Prices are nearly identical!")
                else:
                    print(f"    ✅ Prices are different")
            print()

if __name__ == "__main__":
    debug_historical_prices() 