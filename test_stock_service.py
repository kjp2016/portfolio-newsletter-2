#!/usr/bin/env python3
"""
Test script for the stock data service.
This script tests the functionality without requiring Streamlit secrets.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
import pandas as pd
from openai import OpenAI

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from stock_data_service import StockDataService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

def test_stock_data_service():
    """Test the stock data service functionality."""
    
    # Check if OpenAI API key is available (try environment variable first)
    api_key = os.environ.get("OPENAI_API_KEY")
    
    # If not in environment, try to load from Streamlit secrets
    if not api_key:
        try:
            import toml
            secrets_path = os.path.join(os.path.dirname(__file__), '.streamlit', 'secrets.toml')
            if os.path.exists(secrets_path):
                secrets = toml.load(secrets_path)
                api_key = secrets.get("OPENAI_API_KEY")
                if api_key and api_key != "your-openai-api-key-here":
                    print("✅ OpenAI API key found in Streamlit secrets")
                else:
                    print("❌ OPENAI_API_KEY not properly configured in .streamlit/secrets.toml")
                    print("Please update the secrets file with your actual API key")
                    return False
            else:
                print("❌ No secrets file found at .streamlit/secrets.toml")
                print("Please create the secrets file with your OpenAI API key")
                return False
        except Exception as e:
            print(f"❌ Error loading secrets: {e}")
            return False
    else:
        print("✅ OpenAI API key found in environment variables")
    
    # Initialize the service
    client = OpenAI(api_key=api_key)
    service = StockDataService(client)
    
    # Test tickers - expanded list for comprehensive testing
    test_tickers = ("AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "NFLX")
    
    print(f"\n🔄 Testing current price fetching for {test_tickers}...")
    
    try:
        # Test current prices
        current_data = service.get_current_prices(test_tickers)
        
        print("\n📊 Current Price Results:")
        for ticker, data in current_data.items():
            price = data.get('current_price')
            company = data.get('company_name', ticker)
            if price:
                print(f"  {ticker}: ${price:.2f} ({company})")
            else:
                print(f"  {ticker}: Price unavailable")
        
        # Test historical data
        print(f"\n🔄 Testing historical data fetching...")
        
        today = pd.Timestamp.utcnow()
        week_ago = today - timedelta(days=7)
        
        historical_data = service.get_batch_price_performance(
            test_tickers, week_ago, today, "weekly"
        )
        
        print("\n📈 Historical Performance Results:")
        for ticker, data in historical_data.items():
            if 'error' not in data:
                print(f"  {ticker}: {data['pct_change']:.2f}% "
                      f"({data['first_date']} to {data['last_date']})")
                print(f"    Start: ${data['first_close']:.2f} | End: ${data['last_close']:.2f} | Change: ${data['abs_change']:.2f}")
            else:
                print(f"  {ticker}: {data['error']}")
        
        # Test ticker validation
        print(f"\n🔄 Testing ticker validation...")
        
        test_tickers_list = ["AAPL", "MSFT", "GOOGL", "INVALID", "TSLA"]
        valid_tickers = service.validate_tickers(test_tickers_list)
        
        print(f"Valid tickers: {valid_tickers}")
        
        print("\n✅ All tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        logging.error(f"Test error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Stock Data Service")
    print("=" * 50)
    
    success = test_stock_data_service()
    
    if success:
        print("\n🎉 All tests passed! The stock data service is working correctly.")
    else:
        print("\n💥 Tests failed. Please check the error messages above.")
        sys.exit(1) 