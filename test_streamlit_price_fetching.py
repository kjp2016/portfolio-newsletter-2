#!/usr/bin/env python3
"""
Test script to verify price fetching functionality and identify errors
"""

import logging
import sys
import os
from datetime import datetime, timedelta
import pandas as pd

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

def test_alpha_vantage_service():
    """Test the Alpha Vantage service directly"""
    print("\n=== Testing Alpha Vantage Service ===")
    
    try:
        from alpha_vantage_service import get_alpha_vantage_service
        service = get_alpha_vantage_service()
        
        # Test tickers that might have issues
        test_tickers = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",  # Common stocks
            "BRK.B", "BRK-A", "BRKB",  # Berkshire variations
            "NVDA", "META", "NFLX",  # Tech stocks
            "SPY", "QQQ", "IWM",  # ETFs
            "INVALID", "FAKE",  # Invalid tickers
        ]
        
        print(f"Testing {len(test_tickers)} tickers...")
        
        for ticker in test_tickers:
            print(f"\n--- Testing {ticker} ---")
            try:
                price = service.get_current_price(ticker)
                if price:
                    print(f"✅ {ticker}: ${price:.2f}")
                else:
                    print(f"❌ {ticker}: No price available")
            except Exception as e:
                print(f"❌ {ticker}: Error - {e}")
        
        # Test batch fetching
        print(f"\n--- Testing Batch Fetching ---")
        valid_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        batch_results = service.get_current_prices(tuple(valid_tickers))
        
        print("Batch Results:")
        for ticker, data in batch_results.items():
            if data.get('current_price'):
                print(f"✅ {ticker}: ${data['current_price']:.2f}")
            else:
                print(f"❌ {ticker}: {data.get('error', 'No data')}")
                
    except Exception as e:
        print(f"❌ Error initializing Alpha Vantage service: {e}")
        logging.error(f"Service initialization error: {e}", exc_info=True)

def test_portfolio_analysis():
    """Test the portfolio analysis module"""
    print("\n=== Testing Portfolio Analysis ===")
    
    try:
        from portfolio_analysis import get_batch_stock_data, get_batch_price_performance
        
        # Test current prices
        test_tickers = ("AAPL", "MSFT", "GOOGL", "AMZN", "TSLA")
        print(f"Testing batch stock data for {test_tickers}...")
        
        stock_data = get_batch_stock_data(test_tickers)
        print("Results:")
        for ticker, data in stock_data.items():
            if data.get('current_price'):
                print(f"✅ {ticker}: ${data['current_price']:.2f}")
            else:
                print(f"❌ {ticker}: {data.get('error', 'No data')}")
        
        # Test historical performance
        print(f"\nTesting historical performance...")
        end_date = pd.Timestamp.now()
        start_date = end_date - pd.Timedelta(days=7)
        
        perf_data = get_batch_price_performance(test_tickers, start_date, end_date, "weekly")
        print("Performance Results:")
        for ticker, perf in perf_data.items():
            if 'error' not in perf:
                print(f"✅ {ticker}: {perf['pct_change']:.2f}%")
            else:
                print(f"❌ {ticker}: {perf['error']}")
                
    except Exception as e:
        print(f"❌ Error in portfolio analysis: {e}")
        logging.error(f"Portfolio analysis error: {e}", exc_info=True)

def test_hybrid_service():
    """Test the hybrid finance service"""
    print("\n=== Testing Hybrid Finance Service ===")
    
    try:
        from hybrid_finance_service import get_hybrid_finance_service
        
        service = get_hybrid_finance_service()
        test_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        
        print(f"Testing hybrid service with {test_tickers}...")
        
        for ticker in test_tickers:
            print(f"\n--- Testing {ticker} ---")
            try:
                price = service.get_current_price(ticker)
                if price:
                    print(f"✅ {ticker}: ${price:.2f}")
                else:
                    print(f"❌ {ticker}: No price available")
            except Exception as e:
                print(f"❌ {ticker}: Error - {e}")
                
    except Exception as e:
        print(f"❌ Error in hybrid service: {e}")
        logging.error(f"Hybrid service error: {e}", exc_info=True)

def test_api_quota():
    """Test API quota and rate limiting"""
    print("\n=== Testing API Quota ===")
    
    try:
        from alpha_vantage_service import get_alpha_vantage_service
        service = get_alpha_vantage_service()
        
        # Test multiple rapid requests to see rate limiting
        print("Testing rate limiting with rapid requests...")
        
        for i in range(10):
            ticker = f"TEST{i}"
            print(f"Request {i+1}: Testing {ticker}")
            try:
                price = service.get_current_price("AAPL")  # Use a real ticker
                if price:
                    print(f"  ✅ AAPL: ${price:.2f}")
                else:
                    print(f"  ❌ AAPL: No price")
            except Exception as e:
                print(f"  ❌ Error: {e}")
                
    except Exception as e:
        print(f"❌ Error testing API quota: {e}")
        logging.error(f"API quota test error: {e}", exc_info=True)

def main():
    """Run all tests"""
    print("🚀 Starting Streamlit Price Fetching Tests")
    print("=" * 50)
    
    # Test each component
    test_alpha_vantage_service()
    test_portfolio_analysis()
    test_hybrid_service()
    test_api_quota()
    
    print("\n" + "=" * 50)
    print("✅ All tests completed!")

if __name__ == "__main__":
    main() 