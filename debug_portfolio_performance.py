#!/usr/bin/env python3
"""
Debug script to test portfolio performance calculation
"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple
import os
from dotenv import load_dotenv
from openai import OpenAI
from stock_data_service import get_stock_data_service

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

def test_portfolio_performance():
    """Test the portfolio performance calculation with sample data"""
    
    # Sample portfolio (you can replace with actual client data)
    test_holdings = {
        "AAPL": 100.0,
        "MSFT": 50.0,
        "GOOGL": 25.0,
        "AMZN": 30.0,
        "NVDA": 20.0
    }
    
    print("=== PORTFOLIO PERFORMANCE DEBUG ===")
    print(f"Test Holdings: {test_holdings}")
    
    # Get the stock data service
    service = get_stock_data_service()
    
    # Calculate dates
    today = pd.Timestamp.utcnow()
    week_ago = today - timedelta(days=7)
    
    print(f"\nDate Range: {week_ago.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}")
    
    # Get current prices
    print("\n=== CURRENT PRICES ===")
    current_prices = service.get_current_prices(tuple(test_holdings.keys()))
    for ticker, data in current_prices.items():
        price = data.get('current_price')
        if price:
            print(f"{ticker}: ${price:.2f}")
        else:
            print(f"{ticker}: Price unavailable")
    
    # Get historical prices
    print("\n=== HISTORICAL PRICES (1 week ago) ===")
    historical_data = service.get_historical_prices(tuple(test_holdings.keys()), week_ago, today)
    
    for ticker, data in historical_data.items():
        if 'error' not in data:
            print(f"{ticker}: ${data['first_close']:.2f} → ${data['last_close']:.2f} ({data['pct_change']:.2f}%)")
        else:
            print(f"{ticker}: {data['error']}")
    
    # Calculate portfolio performance manually
    print("\n=== MANUAL PORTFOLIO CALCULATION ===")
    total_value_start = 0
    total_value_end = 0
    valid_tickers = 0
    
    for ticker, shares in test_holdings.items():
        if ticker in historical_data and 'error' not in historical_data[ticker]:
            start_price = historical_data[ticker]['first_close']
            end_price = historical_data[ticker]['last_close']
            
            value_start = start_price * shares
            value_end = end_price * shares
            
            total_value_start += value_start
            total_value_end += value_end
            valid_tickers += 1
            
            print(f"{ticker}: {shares} shares × ${start_price:.2f} = ${value_start:.2f} → ${value_end:.2f}")
        else:
            print(f"{ticker}: No valid historical data")
    
    if total_value_start > 0:
        portfolio_change_pct = ((total_value_end - total_value_start) / total_value_start) * 100
        print(f"\nPortfolio Summary:")
        print(f"Total Value Start: ${total_value_start:.2f}")
        print(f"Total Value End: ${total_value_end:.2f}")
        print(f"Portfolio Change: {portfolio_change_pct:.2f}%")
        print(f"Valid Tickers: {valid_tickers}/{len(test_holdings)}")
    else:
        print("\nERROR: No valid historical data found for portfolio calculation")
    
    # Test the actual function from main.py
    print("\n=== TESTING MAIN.PY FUNCTION ===")
    from main import get_overall_portfolio_performance
    
    result = get_overall_portfolio_performance(tuple(test_holdings.keys()), "weekly", test_holdings)
    print(f"Main.py result: {result['overall_change_pct']:.2f}%")
    print(f"Major movers: {result['major_movers']}")

if __name__ == "__main__":
    test_portfolio_performance() 