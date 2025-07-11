#!/usr/bin/env python3
"""
Test script to verify Alpha Vantage integration with the newsletter system.
"""

import os
import sys
from datetime import datetime, timedelta
import pandas as pd
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from alpha_vantage_service import AlphaVantageService
from hybrid_finance_service import HybridFinanceService

def test_alpha_vantage_service():
    """Test the Alpha Vantage service directly."""
    print("\n=== Testing Alpha Vantage Service Directly ===")
    
    service = AlphaVantageService()
    
    # Test symbols from your working script
    test_symbols = ["AAPL", "RTX", "NOW", "SHEL", "XLE", "GLD"]
    
    print(f"\nTesting current prices for {test_symbols}...")
    current_prices = service.get_current_prices(tuple(test_symbols))
    
    for symbol, data in current_prices.items():
        price = data.get('current_price')
        if price:
            print(f"  {symbol}: ${price:.2f}")
        else:
            print(f"  {symbol}: Price unavailable")
    
    # Test historical performance
    print(f"\nTesting historical performance...")
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    
    # Convert to pandas Timestamps
    start_date = pd.Timestamp(week_ago)
    end_date = pd.Timestamp(today)
    
    historical_data = service.get_historical_prices(tuple(test_symbols[:3]), start_date, end_date)
    
    for symbol, data in historical_data.items():
        if 'error' not in data:
            print(f"  {symbol}: {data['pct_change']:.2f}% ({data['first_date']} to {data['last_date']})")
        else:
            print(f"  {symbol}: {data['error']}")

def test_hybrid_finance_service():
    """Test the hybrid finance service that uses Alpha Vantage."""
    print("\n=== Testing Hybrid Finance Service ===")
    
    service = HybridFinanceService()
    
    # Test symbols
    test_symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NFLX"]
    
    print(f"\nTesting current prices for {test_symbols}...")
    current_prices = service.get_current_prices(tuple(test_symbols))
    
    for symbol, data in current_prices.items():
        price = data.get('current_price')
        if price:
            print(f"  {symbol}: ${price:.2f}")
        else:
            print(f"  {symbol}: Price unavailable")
    
    # Test historical performance
    print(f"\nTesting historical performance...")
    today = pd.Timestamp.now()
    week_ago = today - pd.Timedelta(days=7)
    
    historical_data = service.get_historical_prices(tuple(test_symbols[:3]), week_ago, today)
    
    for symbol, data in historical_data.items():
        if 'error' not in data:
            print(f"  {symbol}: {data['pct_change']:.2f}% ({data['first_date']} to {data['last_date']})")
        else:
            print(f"  {symbol}: {data['error']}")

def test_portfolio_analysis_integration():
    """Test the portfolio analysis module with Alpha Vantage."""
    print("\n=== Testing Portfolio Analysis Integration ===")
    
    try:
        from portfolio_analysis import get_batch_stock_data, get_batch_price_performance
        
        test_symbols = ["AAPL", "MSFT", "GOOGL"]
        
        print(f"\nTesting batch stock data for {test_symbols}...")
        stock_data = get_batch_stock_data(tuple(test_symbols))
        
        for symbol, data in stock_data.items():
            price = data.get('current_price')
            if price:
                print(f"  {symbol}: ${price:.2f}")
            else:
                print(f"  {symbol}: Price unavailable")
        
        # Test batch price performance
        print(f"\nTesting batch price performance...")
        today = pd.Timestamp.now()
        week_ago = today - pd.Timedelta(days=7)
        
        perf_data = get_batch_price_performance(tuple(test_symbols), week_ago, today, "weekly")
        
        for symbol, data in perf_data.items():
            if 'error' not in data:
                print(f"  {symbol}: {data['pct_change']:.2f}% ({data['first_date']} to {data['last_date']})")
            else:
                print(f"  {symbol}: {data['error']}")
                
    except ImportError as e:
        print(f"Could not import portfolio_analysis: {e}")

def main():
    """Run all tests."""
    print("Starting Alpha Vantage Integration Tests...")
    
    # Test 1: Direct Alpha Vantage service
    test_alpha_vantage_service()
    
    # Test 2: Hybrid finance service
    test_hybrid_finance_service()
    
    # Test 3: Portfolio analysis integration
    test_portfolio_analysis_integration()
    
    print("\n=== All Tests Complete ===")

if __name__ == "__main__":
    main() 