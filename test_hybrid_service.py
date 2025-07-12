#!/usr/bin/env python3
"""
Test the hybrid finance service.
"""

import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hybrid_finance_service import HybridFinanceService

def test_hybrid_service():
    """Test the hybrid finance service."""
    
    service = HybridFinanceService()
    
    # Test tickers
    test_tickers = ["AMZN", "MSFT", "GOOGL"]
    
    print(f"Testing Hybrid Finance Service")
    print("=" * 60)
    
    # Test current prices
    print("\nTesting Current Prices (Yahoo Finance):")
    print("-" * 40)
    
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
    
    # Test historical data (estimated)
    print("\nTesting Historical Data (Estimated):")
    print("-" * 40)
    
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
    
    # Test batch performance
    print("\nTesting Batch Performance:")
    print("-" * 30)
    
    batch_data = service.get_batch_price_performance(
        tuple(test_tickers), 
        pd.Timestamp(start_date), 
        pd.Timestamp(end_date),
        "7-day"
    )
    
    for ticker in test_tickers:
        if ticker in batch_data:
            data = batch_data[ticker]
            if "error" not in data:
                print(f"{ticker}: {data['period_name']} - {data['pct_change']:.2f}%")
            else:
                print(f"{ticker}: {data['error']}")

if __name__ == "__main__":
    test_hybrid_service() 