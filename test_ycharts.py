#!/usr/bin/env python3
"""
Test script for YCharts integration
"""

import pandas as pd
from datetime import datetime, timedelta
from stock_data_service import StockDataService

def test_ycharts_integration():
    """Test the YCharts integration with a few sample tickers."""
    
    print("Testing YCharts Integration...")
    print("=" * 50)
    
    # Initialize the service
    service = StockDataService()
    
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
    
    # Type assertion to ensure we have valid timestamps
    start_ts = start_date
    end_ts = end_date
    
    historical_data = service.get_historical_prices(test_tickers, start_ts, end_ts)
    
    for ticker, data in historical_data.items():
        if 'pct_change' in data:
            print(f"  {ticker}: {data['pct_change']:.2f}% ({data['first_date']} to {data['last_date']})")
            print(f"    Start: ${data['first_close']:.2f}, End: ${data['last_close']:.2f}")
        else:
            print(f"  {ticker}: No historical data available")
    
    print(f"\n3. Testing ticker validation...")
    test_validation = ["AAPL", "MSFT", "INVALID_TICKER", "GOOGL"]
    valid_tickers = service.validate_tickers(test_validation)
    print(f"  Valid tickers: {valid_tickers}")
    
    print("\nYCharts integration test completed!")

if __name__ == "__main__":
    test_ycharts_integration() 