#!/usr/bin/env python3
"""
Test script for Twelve Data API integration
"""

import pandas as pd
from datetime import datetime, timedelta
from stock_data_service import StockDataService
from openai import OpenAI
import os

def test_twelve_data_integration():
    """Test the Twelve Data integration with a few sample tickers."""
    
    print("Testing Twelve Data API Integration...")
    print("=" * 50)
    
    # Initialize OpenAI client (you'll need to set OPENAI_API_KEY in your environment)
    try:
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            print("Warning: OPENAI_API_KEY not found in environment. Fallback methods may not work.")
            openai_api_key = "dummy_key"  # Will be used for initialization but won't work for fallbacks
        
        client = OpenAI(api_key=openai_api_key)
    except Exception as e:
        print(f"Warning: Could not initialize OpenAI client: {e}")
        client = None
    
    # Initialize the service with your Twelve Data API key
    service = StockDataService(client, "2ddacad0dbdb4673bd92aff99988248c")
    
    # Test tickers
    test_tickers = ("AAPL", "MSFT", "GOOGL")
    
    print(f"\n1. Testing current prices for {test_tickers}...")
    current_prices = service.get_current_prices(test_tickers)
    
    for ticker, data in current_prices.items():
        price = data.get('current_price')
        name = data.get('company_name', ticker)
        if price:
            print(f"  {ticker} ({name}): ${price:.2f}")
        else:
            print(f"  {ticker}: Price unavailable")
    
    print(f"\n2. Testing historical prices for {test_tickers}...")
    
    # Test historical data for the last week
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.Timedelta(days=7)
    
    # Ensure timestamps are valid
    if start_date is pd.NaT or end_date is pd.NaT:
        print("Error: Invalid timestamps generated")
        return
    
    historical_data = service.get_historical_prices(test_tickers, start_date, end_date)
    
    for ticker, data in historical_data.items():
        if 'pct_change' in data:
            print(f"  {ticker}: {data['pct_change']:.2f}% ({data['first_date']} to {data['last_date']})")
            print(f"    Start: ${data['first_close']:.2f}, End: ${data['last_close']:.2f}")
        else:
            print(f"  {ticker}: {data.get('error', 'No historical data available')}")
    
    print(f"\n3. Testing ticker validation...")
    test_validation = ["AAPL", "MSFT", "INVALID_TICKER", "GOOGL"]
    valid_tickers = service.validate_tickers(test_validation)
    print(f"  Valid tickers: {valid_tickers}")
    
    print("\nTwelve Data integration test completed!")

if __name__ == "__main__":
    test_twelve_data_integration() 