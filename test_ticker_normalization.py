#!/usr/bin/env python3
"""
Test script to verify ticker normalization and variation handling.
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

def test_ticker_normalization():
    """Test the ticker normalization system."""
    print("\n=== Testing Ticker Normalization ===")
    
    service = AlphaVantageService()
    
    # Test cases with known variations
    test_cases = [
        ("BRKB", "BRK.B"),  # Berkshire Hathaway B shares
        ("BRKA", "BRK.A"),  # Berkshire Hathaway A shares
        ("GOOG", "GOOGL"),  # Google
        ("GOOGL", "GOOGL"), # Google (already correct)
        ("AAPL", "AAPL"),   # Apple (should work as-is)
        ("MSFT", "MSFT"),   # Microsoft (should work as-is)
    ]
    
    print("\nTesting ticker normalization:")
    for original, expected in test_cases:
        normalized = service._normalize_ticker(original)
        status = "✅" if normalized == expected else "❌"
        print(f"  {status} {original} -> {normalized} (expected: {expected})")
    
    # Test ticker variation system
    print("\nTesting ticker variation system:")
    problem_tickers = ["BRKB", "GOOG", "INVALID_TICKER"]
    
    for ticker in problem_tickers:
        print(f"\nTesting variations for {ticker}:")
        time_series = service._try_ticker_variations(ticker)
        if time_series:
            print(f"  ✅ Success! Found data for {ticker}")
        else:
            print(f"  ❌ Failed to find data for {ticker}")

def test_actual_price_fetching():
    """Test actual price fetching with problematic tickers."""
    print("\n=== Testing Actual Price Fetching ===")
    
    service = AlphaVantageService()
    
    # Test tickers that commonly fail
    test_tickers = ["BRKB", "GOOG", "AAPL", "MSFT", "INVALID"]
    
    print(f"\nTesting current price fetching for {test_tickers}:")
    for ticker in test_tickers:
        price = service.get_current_price(ticker)
        if price:
            print(f"  ✅ {ticker}: ${price:.2f}")
        else:
            print(f"  ❌ {ticker}: Price unavailable")
    
    # Test historical performance
    print(f"\nTesting historical performance for {test_tickers[:3]}:")
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    
    for ticker in test_tickers[:3]:
        perf = service.get_historical_performance(ticker, week_ago, today)
        if perf:
            print(f"  ✅ {ticker}: {perf['pct_change']:.2f}% ({perf['first_date']} to {perf['last_date']})")
        else:
            print(f"  ❌ {ticker}: Performance data unavailable")

def main():
    """Run all tests."""
    print("Starting Ticker Normalization Tests...")
    
    # Test 1: Ticker normalization
    test_ticker_normalization()
    
    # Test 2: Actual price fetching
    test_actual_price_fetching()
    
    print("\n=== All Tests Complete ===")

if __name__ == "__main__":
    main() 