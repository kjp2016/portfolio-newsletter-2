#!/usr/bin/env python3
"""
Test Alpha Vantage API for historical data.
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import os
import sys
import toml

def test_alpha_vantage():
    """Test Alpha Vantage API for historical data."""
    
    # Alpha Vantage API key (free tier)
    api_key = "demo"  # You can get a free key from https://www.alphavantage.co/support/#api-key
    
    ticker = "AMZN"
    
    print(f"Testing Alpha Vantage API for {ticker}")
    print("=" * 60)
    
    # Test current price
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={api_key}"
    
    try:
        response = requests.get(url, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {data}")
            
            if "Global Quote" in data:
                quote = data["Global Quote"]
                print(f"\nCurrent Price: ${quote.get('05. price', 'N/A')}")
                print(f"Change: {quote.get('09. change', 'N/A')}")
                print(f"Change Percent: {quote.get('10. change percent', 'N/A')}")
            else:
                print("No quote data found")
        else:
            print(f"Failed with status code: {response.status_code}")
            
    except Exception as e:
        print(f"Error: {e}")
    
    # Test historical data
    print("\n" + "=" * 60)
    print("Testing Historical Data:")
    print("=" * 60)
    
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={api_key}"
    
    try:
        response = requests.get(url, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if "Time Series (Daily)" in data:
                time_series = data["Time Series (Daily)"]
                dates = list(time_series.keys())
                
                print(f"Available dates: {len(dates)} days")
                print(f"Date range: {dates[-1]} to {dates[0]}")
                
                # Get last 7 days
                recent_dates = dates[:7]
                print(f"\nLast 7 days:")
                for date in recent_dates:
                    daily_data = time_series[date]
                    close_price = daily_data.get("4. close", "N/A")
                    print(f"  {date}: ${close_price}")
                
                # Calculate 7-day performance
                if len(recent_dates) >= 2:
                    start_price = float(time_series[recent_dates[-1]]["4. close"])
                    end_price = float(time_series[recent_dates[0]]["4. close"])
                    change = end_price - start_price
                    pct_change = (change / start_price) * 100
                    
                    print(f"\n7-day performance:")
                    print(f"  Start: ${start_price:.2f} ({recent_dates[-1]})")
                    print(f"  End: ${end_price:.2f} ({recent_dates[0]})")
                    print(f"  Change: ${change:.2f} ({pct_change:.2f}%)")
            else:
                print("No historical data found")
                print(f"Response: {data}")
        else:
            print(f"Failed with status code: {response.status_code}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_alpha_vantage() 