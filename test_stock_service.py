#!/usr/bin/env python3
"""
Test script for the updated stock data service with separate API calls
"""

import pandas as pd
from datetime import datetime, timedelta
from stock_data_service import get_stock_data_service
import streamlit as st

def test_stock_service():
    """Test the updated stock data service"""
    print("=== Testing Updated Stock Data Service ===")
    
    # Test tickers
    test_tickers = ("AMZN", "MSFT", "GOOGL", "NVDA", "AAPL")
    print(f"\nTesting with tickers: {test_tickers}")
    
    # Get the service
    service = get_stock_data_service()
    
    # Test 1: Current prices
    print("\n1. Testing current prices...")
    current_prices = service.get_current_prices(test_tickers)
    print("Current prices results:")
    for ticker, data in current_prices.items():
        price = data.get('current_price')
        company = data.get('company_name', 'Unknown')
        if price:
            print(f"  {ticker}: ${price:.2f} ({company})")
        else:
            print(f"  {ticker}: Price unavailable")
    
    # Test 2: Historical prices (7 days ago vs current)
    print("\n2. Testing historical prices (7 days ago vs current)...")
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.Timedelta(days=7)
    
    # Validate timestamps
    if start_date is pd.NaT or end_date is pd.NaT:
        print("Error: Invalid timestamps generated")
        return
    
    if isinstance(start_date, pd.Timestamp) and isinstance(end_date, pd.Timestamp):
        print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        historical_data = service.get_historical_prices(test_tickers, start_date, end_date)
        print("Historical data results:")
        for ticker, data in historical_data.items():
            if 'error' not in data:
                print(f"  {ticker}: {data['first_close']:.2f} → {data['last_close']:.2f} ({data['pct_change']:+.2f}%)")
            else:
                print(f"  {ticker}: {data['error']}")
        
        # Test 3: Batch performance (this is what the app actually uses)
        print("\n3. Testing batch performance...")
        batch_data = service.get_batch_price_performance(test_tickers, start_date, end_date, "weekly")
    else:
        print("Error: Invalid timestamp types")
        return
    print("Batch performance results:")
    for ticker, data in batch_data.items():
        if 'error' not in data:
            print(f"  {ticker}: {data['first_close']:.2f} → {data['last_close']:.2f} ({data['pct_change']:+.2f}%)")
        else:
            print(f"  {ticker}: {data['error']}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_stock_service() 