#!/usr/bin/env python3
"""
Debug script to test portfolio performance with actual client data
"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple
import os
from dotenv import load_dotenv
from openai import OpenAI
from stock_data_service import get_stock_data_service
import json

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

def test_client_portfolio():
    """Test with actual client portfolio data"""
    
    # Actual client portfolio data
    client_holdings = {
        "GOOGL": 125.0,
        "MO": 225.0,
        "AMZN": 150.0,
        "BRKB": 60.0,
        "AVGO": 75.0,
        "CAT": 33.0,
        "CRWD": 75.0,
        "DE": 18.0,
        "EMR": 70.0,
        "GE": 225.0,
        "GEV": 40.0,
        "GD": 75.0,
        "HON": 105.0,
        "MSFT": 75.0,
        "NVDA": 200.0,
        "PFE": 225.0,
        "PM": 65.0,
        "RTX": 151.0,
        "NOW": 23.0,
        "SHEL": 180.0,
        "XLE": 90.0,
        "GLD": 100.0,
        "DHEIX": 4091.0,  # Mutual fund
        "LSYIX": 1198.0,  # Mutual fund
        "PHYZX": 1015.0,  # Mutual fund
        "DRGVX": 512.0,   # Mutual fund
        "CTSIX": 263.0,   # Mutual fund
        "FEGIX": 380.0,   # Mutual fund
        "GSIMX": 483.0,   # Mutual fund
        "VSMIX": 834.0,   # Mutual fund - this one showed 92% drop
        "PCBIX": 662.0,   # Mutual fund
        "RMLPX": 871.0    # Mutual fund
    }
    
    print("=== CLIENT PORTFOLIO DEBUG ===")
    print(f"Client Holdings: {len(client_holdings)} positions")
    print(f"Stocks: {len([k for k in client_holdings.keys() if not any(x in k for x in ['IX', 'ZX', 'VX', 'PX'])])}")
    print(f"Mutual Funds: {len([k for k in client_holdings.keys() if any(x in k for x in ['IX', 'ZX', 'VX', 'PX'])])}")
    
    # Get the stock data service
    service = get_stock_data_service()
    
    # Calculate dates
    today = pd.Timestamp.utcnow()
    week_ago = today - timedelta(days=7)
    
    print(f"\nDate Range: {week_ago.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}")
    
    # Test 1: Current prices
    print("\n=== CURRENT PRICES ===")
    current_prices = service.get_current_prices(tuple(client_holdings.keys()))
    
    # Separate stocks and mutual funds
    stocks = {k: v for k, v in current_prices.items() if not any(x in k for x in ['IX', 'ZX', 'VX', 'PX'])}
    mutual_funds = {k: v for k, v in current_prices.items() if any(x in k for x in ['IX', 'ZX', 'VX', 'PX'])}
    
    print(f"Stocks with prices: {len([k for k, v in stocks.items() if v.get('current_price')])}/{len(stocks)}")
    print(f"Mutual funds with prices: {len([k for k, v in mutual_funds.items() if v.get('current_price')])}/{len(mutual_funds)}")
    
    # Show some examples
    print("\nSample stock prices:")
    for ticker, data in list(stocks.items())[:5]:
        price = data.get('current_price')
        if price:
            print(f"  {ticker}: ${price:.2f}")
        else:
            print(f"  {ticker}: Price unavailable")
    
    print("\nSample mutual fund prices:")
    for ticker, data in list(mutual_funds.items())[:5]:
        price = data.get('current_price')
        if price:
            print(f"  {ticker}: ${price:.2f}")
        else:
            print(f"  {ticker}: Price unavailable")
    
    # Test 2: Historical prices - focus on problematic ones
    print("\n=== HISTORICAL PRICES (1 week ago) ===")
    
    # Test a subset first to identify issues
    test_tickers = ["VSMIX", "AMZN", "NVDA", "MSFT", "DHEIX", "LSYIX"]
    historical_data = service.get_historical_prices(tuple(test_tickers), week_ago, today)
    
    for ticker, data in historical_data.items():
        if 'error' not in data:
            print(f"{ticker}: ${data['first_close']:.2f} → ${data['last_close']:.2f} ({data['pct_change']:.2f}%)")
            if abs(data['pct_change']) > 50:
                print(f"  ⚠️  WARNING: {ticker} shows extreme movement!")
        else:
            print(f"{ticker}: {data['error']}")
    
    # Test 3: Manual portfolio calculation for test subset
    print("\n=== MANUAL PORTFOLIO CALCULATION (Test Subset) ===")
    test_holdings = {k: client_holdings[k] for k in test_tickers if k in client_holdings}
    
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
        print(f"\nTest Portfolio Summary:")
        print(f"Total Value Start: ${total_value_start:.2f}")
        print(f"Total Value End: ${total_value_end:.2f}")
        print(f"Portfolio Change: {portfolio_change_pct:.2f}%")
        print(f"Valid Tickers: {valid_tickers}/{len(test_holdings)}")
    
    # Test 4: Check VSMIX specifically
    print(f"\n=== VSMIX SPECIFIC ANALYSIS ===")
    if "VSMIX" in historical_data and 'error' not in historical_data["VSMIX"]:
        vsmix_data = historical_data["VSMIX"]
        print(f"VSMIX data: {vsmix_data}")
        
        # Check if the price looks reasonable
        if vsmix_data['first_close'] < 1 or vsmix_data['last_close'] < 1:
            print("⚠️  WARNING: VSMIX prices seem too low - mutual funds typically trade at NAV")
        if abs(vsmix_data['pct_change']) > 50:
            print("⚠️  WARNING: VSMIX shows extreme movement - this is likely incorrect")
    
    # Test 5: Test with main.py function for test subset
    print(f"\n=== TESTING MAIN.PY FUNCTION (Test Subset) ===")
    from main import get_overall_portfolio_performance
    
    result = get_overall_portfolio_performance(tuple(test_tickers), "weekly", test_holdings)
    print(f"Main.py result: {result['overall_change_pct']:.2f}%")
    print(f"Major movers: {result['major_movers']}")

def test_mutual_fund_pricing():
    """Test mutual fund pricing specifically"""
    print("\n=== MUTUAL FUND PRICING TEST ===")
    
    service = get_stock_data_service()
    today = pd.Timestamp.utcnow()
    week_ago = today - timedelta(days=7)
    
    # Test mutual funds that might be problematic
    mutual_funds = ["VSMIX", "DHEIX", "LSYIX", "PHYZX", "DRGVX"]
    
    for fund in mutual_funds:
        print(f"\nTesting {fund}:")
        try:
            data = service.get_historical_prices((fund,), week_ago, today)
            if fund in data and 'error' not in data[fund]:
                print(f"  Historical: ${data[fund]['first_close']:.2f} → ${data[fund]['last_close']:.2f} ({data[fund]['pct_change']:.2f}%)")
                
                # Check if prices look reasonable for mutual funds
                if data[fund]['first_close'] < 1 or data[fund]['last_close'] < 1:
                    print(f"  ⚠️  WARNING: {fund} prices seem too low")
                if abs(data[fund]['pct_change']) > 20:
                    print(f"  ⚠️  WARNING: {fund} shows large movement")
            else:
                print(f"  Error: {data.get(fund, {}).get('error', 'Unknown error')}")
        except Exception as e:
            print(f"  Exception: {e}")

if __name__ == "__main__":
    test_client_portfolio()
    test_mutual_fund_pricing() 