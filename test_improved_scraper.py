#!/usr/bin/env python3
"""
Test the improved web scraper service.
"""

import pandas as pd
from datetime import datetime, timedelta
import os
import sys
import toml

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from web_scraper_service import WebScraperService
from openai import OpenAI

def test_improved_scraper():
    """Test the improved web scraper with AMZN and other tickers."""
    
    # Read API key from Streamlit secrets
    try:
        secrets = toml.load(".streamlit/secrets.toml")
        api_key = secrets.get("OPENAI_API_KEY")
    except Exception as e:
        print(f"Could not read secrets file: {e}")
        return
    
    if not api_key:
        print("No OpenAI API key found in secrets file")
        return
    
    client = OpenAI(api_key=api_key)
    scraper = WebScraperService(client)
    
    # Test tickers
    test_tickers = ["AMZN", "MSFT", "GOOGL"]
    
    # Set up date range (7 days ago to today)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    print(f"Testing historical data extraction for {test_tickers}")
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print("=" * 60)
    
    # Test historical data extraction
    historical_data = scraper.get_historical_prices(
        tuple(test_tickers), 
        pd.Timestamp(start_date), 
        pd.Timestamp(end_date)
    )
    
    print("\nResults:")
    print("=" * 60)
    
    for ticker in test_tickers:
        if ticker in historical_data:
            data = historical_data[ticker]
            if "error" in data:
                print(f"{ticker}: {data['error']}")
            else:
                print(f"{ticker}: ${data['first_close']} → ${data['last_close']} ({data['pct_change']:.2f}%) [Source: {data['source']}]")
        else:
            print(f"{ticker}: No data found")
    
    # Test current prices too
    print("\n" + "=" * 60)
    print("Testing current price extraction:")
    print("=" * 60)
    
    current_data = scraper.get_current_prices(tuple(test_tickers))
    
    for ticker in test_tickers:
        if ticker in current_data:
            data = current_data[ticker]
            if data.get('current_price'):
                print(f"{ticker}: ${data['current_price']} [Source: {data['source']}]")
            else:
                print(f"{ticker}: No current price found")
        else:
            print(f"{ticker}: No data found")

if __name__ == "__main__":
    test_improved_scraper() 