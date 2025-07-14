#!/usr/bin/env python3
"""
Test script to verify price fetching functionality with user's specific portfolio
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

# User's portfolio data
PORTFOLIO_DATA = {
    # Stocks
    "GOOGL": 125,
    "MO": 225,
    "AMZN": 150,
    "BRK-B": 60,
    "AVGO": 75,
    "CAT": 33,
    "CRWD": 75,
    "DE": 18,
    "EMR": 70,
    "GE": 225,
    "GEV": 40,
    "GD": 75,
    "HON": 105,
    "MSFT": 75,
    "NVDA": 200,
    "PFE": 225,
    "PM": 65,
    "RTX": 151,
    "NOW": 23,
    "SHEL": 180,
    "XLE": 90,
    "GLD": 100,
    
    # Mutual Funds
    "DHEIX": 4091,
    "LSYIX": 1198,
    "PHYZX": 1015,
    "DRGVX": 512,
    "CTSIX": 263,
    "FEGIX": 380,
    "GSIMX": 483,
    "VSMIX": 834,
    "PCBIX": 662,
    "RMLPX": 871,
}

def test_alpha_vantage_service():
    """Test the Alpha Vantage service with user's portfolio"""
    print("\n=== Testing Alpha Vantage Service with Portfolio ===")
    
    try:
        from alpha_vantage_service import get_alpha_vantage_service
        service = get_alpha_vantage_service()
        
        # Test individual tickers
        print(f"Testing {len(PORTFOLIO_DATA)} portfolio tickers individually...")
        
        successful_tickers = []
        failed_tickers = []
        
        for ticker, shares in PORTFOLIO_DATA.items():
            print(f"\n--- Testing {ticker} ({shares} shares) ---")
            try:
                price = service.get_current_price(ticker)
                if price:
                    value = price * shares
                    print(f"✅ {ticker}: ${price:.2f} | Value: ${value:,.2f}")
                    successful_tickers.append((ticker, price, shares, value))
                else:
                    print(f"❌ {ticker}: No price available")
                    failed_tickers.append((ticker, "No price available"))
            except Exception as e:
                print(f"❌ {ticker}: Error - {e}")
                failed_tickers.append((ticker, str(e)))
        
        # Summary
        print(f"\n=== SUMMARY ===")
        print(f"✅ Successful: {len(successful_tickers)} tickers")
        print(f"❌ Failed: {len(failed_tickers)} tickers")
        
        if successful_tickers:
            total_value = sum(value for _, _, _, value in successful_tickers)
            print(f"💰 Total Portfolio Value: ${total_value:,.2f}")
        
        if failed_tickers:
            print(f"\nFailed Tickers:")
            for ticker, error in failed_tickers:
                print(f"  • {ticker}: {error}")
                
    except Exception as e:
        print(f"❌ Error initializing Alpha Vantage service: {e}")
        logging.error(f"Service initialization error: {e}", exc_info=True)

def test_batch_fetching():
    """Test batch fetching with user's portfolio"""
    print("\n=== Testing Batch Fetching ===")
    
    try:
        from alpha_vantage_service import get_alpha_vantage_service
        service = get_alpha_vantage_service()
        
        # Test in smaller batches to avoid rate limits
        tickers = list(PORTFOLIO_DATA.keys())
        batch_size = 5
        
        successful_tickers = []
        failed_tickers = []
        
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i+batch_size]
            print(f"\n--- Batch {i//batch_size + 1}: {batch} ---")
            
            try:
                batch_results = service.get_current_prices(tuple(batch))
                
                for ticker in batch:
                    data = batch_results.get(ticker, {})
                    shares = PORTFOLIO_DATA[ticker]
                    
                    if data.get('current_price'):
                        price = data['current_price']
                        value = price * shares
                        print(f"✅ {ticker}: ${price:.2f} | Value: ${value:,.2f}")
                        successful_tickers.append((ticker, price, shares, value))
                    else:
                        error = data.get('error', 'No data')
                        print(f"❌ {ticker}: {error}")
                        failed_tickers.append((ticker, error))
                        
            except Exception as e:
                print(f"❌ Batch error: {e}")
                for ticker in batch:
                    failed_tickers.append((ticker, f"Batch error: {e}"))
        
        # Summary
        print(f"\n=== BATCH SUMMARY ===")
        print(f"✅ Successful: {len(successful_tickers)} tickers")
        print(f"❌ Failed: {len(failed_tickers)} tickers")
        
        if successful_tickers:
            total_value = sum(value for _, _, _, value in successful_tickers)
            print(f"💰 Total Portfolio Value: ${total_value:,.2f}")
        
        if failed_tickers:
            print(f"\nFailed Tickers:")
            for ticker, error in failed_tickers:
                print(f"  • {ticker}: {error}")
                
    except Exception as e:
        print(f"❌ Error in batch fetching: {e}")
        logging.error(f"Batch fetching error: {e}", exc_info=True)

def test_portfolio_analysis():
    """Test the portfolio analysis module with user's portfolio"""
    print("\n=== Testing Portfolio Analysis ===")
    
    try:
        from portfolio_analysis import get_batch_stock_data, get_batch_price_performance
        
        # Test current prices
        tickers = tuple(PORTFOLIO_DATA.keys())
        print(f"Testing portfolio analysis with {len(tickers)} tickers...")
        
        stock_data = get_batch_stock_data(tickers)
        
        successful_tickers = []
        failed_tickers = []
        
        print("Results:")
        for ticker, data in stock_data.items():
            shares = PORTFOLIO_DATA[ticker]
            if data.get('current_price'):
                price = data['current_price']
                value = price * shares
                print(f"✅ {ticker}: ${price:.2f} | Value: ${value:,.2f}")
                successful_tickers.append((ticker, price, shares, value))
            else:
                error = data.get('error', 'No data')
                print(f"❌ {ticker}: {error}")
                failed_tickers.append((ticker, error))
        
        # Summary
        print(f"\n=== PORTFOLIO ANALYSIS SUMMARY ===")
        print(f"✅ Successful: {len(successful_tickers)} tickers")
        print(f"❌ Failed: {len(failed_tickers)} tickers")
        
        if successful_tickers:
            total_value = sum(value for _, _, _, value in successful_tickers)
            print(f"💰 Total Portfolio Value: ${total_value:,.2f}")
        
        if failed_tickers:
            print(f"\nFailed Tickers:")
            for ticker, error in failed_tickers:
                print(f"  • {ticker}: {error}")
                
    except Exception as e:
        print(f"❌ Error in portfolio analysis: {e}")
        logging.error(f"Portfolio analysis error: {e}", exc_info=True)

def test_historical_performance():
    """Test historical performance with a subset of tickers"""
    print("\n=== Testing Historical Performance ===")
    
    try:
        from portfolio_analysis import get_batch_price_performance
        
        # Test with a subset of major tickers to avoid rate limits
        test_tickers = ("AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "BRK-B", "MO", "PFE")
        
        print(f"Testing historical performance for {test_tickers}...")
        end_date = pd.Timestamp.now()
        start_date = end_date - pd.Timedelta(days=7)
        
        # Ensure timestamps are valid
        if start_date is pd.NaT or end_date is pd.NaT:
            print("❌ Error: Invalid timestamps generated")
            return
        
        # Type cast to ensure proper types
        start_date_ts = pd.Timestamp(start_date)
        end_date_ts = pd.Timestamp(end_date)
        
        perf_data = get_batch_price_performance(test_tickers, start_date_ts, end_date_ts, "weekly")
        
        print("Performance Results:")
        for ticker, perf in perf_data.items():
            if 'error' not in perf:
                print(f"✅ {ticker}: {perf['pct_change']:.2f}% ({perf['first_date']} to {perf['last_date']})")
            else:
                print(f"❌ {ticker}: {perf['error']}")
                
    except Exception as e:
        print(f"❌ Error in historical performance: {e}")
        logging.error(f"Historical performance error: {e}", exc_info=True)

def test_rate_limiting():
    """Test rate limiting behavior"""
    print("\n=== Testing Rate Limiting ===")
    
    try:
        from alpha_vantage_service import get_alpha_vantage_service
        service = get_alpha_vantage_service()
        
        # Test rapid requests to see rate limiting
        print("Testing rate limiting with rapid requests...")
        
        test_ticker = "AAPL"  # Use a reliable ticker
        start_time = datetime.now()
        
        for i in range(6):  # Test 6 requests (should hit rate limit)
            print(f"Request {i+1}: Testing {test_ticker}")
            try:
                price = service.get_current_price(test_ticker)
                if price:
                    print(f"  ✅ {test_ticker}: ${price:.2f}")
                else:
                    print(f"  ❌ {test_ticker}: No price")
            except Exception as e:
                print(f"  ❌ Error: {e}")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"\nTotal time for 6 requests: {duration:.1f} seconds")
        print(f"Average time per request: {duration/6:.1f} seconds")
        
    except Exception as e:
        print(f"❌ Error testing rate limiting: {e}")
        logging.error(f"Rate limiting test error: {e}", exc_info=True)

def main():
    """Run all tests with user's portfolio"""
    print("🚀 Starting Portfolio Price Fetching Tests")
    print("=" * 60)
    print(f"Testing {len(PORTFOLIO_DATA)} portfolio tickers")
    print("=" * 60)
    
    # Test each component
    test_alpha_vantage_service()
    test_batch_fetching()
    test_portfolio_analysis()
    test_historical_performance()
    test_rate_limiting()
    
    print("\n" + "=" * 60)
    print("✅ All portfolio tests completed!")

if __name__ == "__main__":
    main() 