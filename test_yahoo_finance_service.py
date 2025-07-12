#!/usr/bin/env python3
"""
Test the new Yahoo Finance service with fin-streamer tags.
"""

import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from yahoo_finance_service import YahooFinanceService

def test_yahoo_finance_service():
    """Test the Yahoo Finance service."""
    
    service = YahooFinanceService()
    
    # Test tickers
    test_tickers = ["AMZN", "MSFT", "GOOGL"]
    
    print(f"Testing Yahoo Finance Service with fin-streamer tags")
    print("=" * 60)
    
    # Test current prices
    print("\nTesting Current Prices:")
    print("-" * 30)
    
    current_data = service.get_current_prices(tuple(test_tickers))
    
    for ticker in test_tickers:
        if ticker in current_data:
            data = current_data[ticker]
            if data.get('current_price'):
                print(f"{ticker}: ${data['current_price']} [Source: {data['source']}]")
            else:
                print(f"{ticker}: No current price found")
        else:
            print(f"{ticker}: No data found")
    
    # Test historical data
    print("\nTesting Historical Data:")
    print("-" * 30)
    
    # Set up date range (7 days ago to today)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    historical_data = service.get_historical_prices(
        tuple(test_tickers), 
        pd.Timestamp(start_date), 
        pd.Timestamp(end_date)
    )
    
    for ticker in test_tickers:
        if ticker in historical_data:
            data = historical_data[ticker]
            if "error" in data:
                print(f"{ticker}: {data['error']}")
            else:
                print(f"{ticker}: ${data['first_close']} → ${data['last_close']} ({data['pct_change']:.2f}%) [Source: {data['source']}]")
        else:
            print(f"{ticker}: No data found")
    
    # Test individual current price function
    print("\nTesting Individual Current Price Function:")
    print("-" * 40)
    
    for ticker in test_tickers:
        price = service.get_current_price(ticker)
        if price:
            print(f"{ticker}: ${price}")
        else:
            print(f"{ticker}: No price found")

if __name__ == "__main__":
    test_yahoo_finance_service() 