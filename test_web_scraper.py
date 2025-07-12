"""
Test script for the web scraper service
Tests the scraping functionality with the GSIMX mutual fund example.
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from openai import OpenAI
from web_scraper_service import WebScraperService

def test_web_scraper():
    """Test the web scraper service with GSIMX and other tickers."""
    
    # Initialize OpenAI client (you'll need to set your API key)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        return
    
    client = OpenAI(api_key=api_key)
    scraper = WebScraperService(client)
    
    # Test tickers including the GSIMX mutual fund
    test_tickers = ["GSIMX", "AAPL", "MSFT", "GOOGL"]
    
    print("=== Testing Web Scraper Service ===")
    print(f"Testing tickers: {test_tickers}")
    
    # Test current prices
    print("\n1. Testing current price fetching...")
    current_prices = scraper.get_current_prices(tuple(test_tickers))
    
    print("\nCurrent Prices Results:")
    for ticker, data in current_prices.items():
        if data.get('current_price'):
            print(f"  {ticker}: ${data['current_price']:.2f} ({data.get('company_name', 'N/A')}) - Source: {data.get('source', 'N/A')}")
        else:
            print(f"  {ticker}: Price unavailable")
    
    # Test historical data
    print("\n2. Testing historical data fetching...")
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.Timedelta(days=30)  # 30 days ago
    
    historical_data = scraper.get_historical_prices(tuple(test_tickers), start_date, end_date)
    
    print("\nHistorical Data Results:")
    for ticker, data in historical_data.items():
        if 'error' not in data:
            print(f"  {ticker}: {data['pct_change']:.2f}% ({data['first_date']} to {data['last_date']})")
            print(f"    Start: ${data['first_close']:.2f}, End: ${data['last_close']:.2f}")
            print(f"    Source: {data.get('source', 'N/A')}")
        else:
            print(f"  {ticker}: {data['error']}")
    
    # Test individual scraping functions
    print("\n3. Testing individual scraping functions...")
    
    # Test Google Finance scraping
    print("\nTesting Google Finance scraping for GSIMX...")
    google_html = scraper._scrape_google_finance("GSIMX")
    if google_html:
        print("  ✓ Google Finance HTML retrieved")
        parsed_google = scraper._parse_current_price_with_openai("GSIMX", google_html, "Google Finance")
        if parsed_google:
            print(f"  ✓ Parsed: ${parsed_google['current_price']:.2f} - {parsed_google['company_name']}")
        else:
            print("  ✗ Failed to parse Google Finance data")
    else:
        print("  ✗ Failed to retrieve Google Finance HTML")
    
    # Test Yahoo Finance scraping
    print("\nTesting Yahoo Finance scraping for GSIMX...")
    yahoo_html = scraper._scrape_yahoo_finance("GSIMX")
    if yahoo_html:
        print("  ✓ Yahoo Finance HTML retrieved")
        parsed_yahoo = scraper._parse_current_price_with_openai("GSIMX", yahoo_html, "Yahoo Finance")
        if parsed_yahoo:
            print(f"  ✓ Parsed: ${parsed_yahoo['current_price']:.2f} - {parsed_yahoo['company_name']}")
        else:
            print("  ✗ Failed to parse Yahoo Finance data")
    else:
        print("  ✗ Failed to retrieve Yahoo Finance HTML")
    
    # Test Financial Times historical scraping
    print("\nTesting Financial Times historical scraping for GSIMX...")
    ft_html = scraper._scrape_ft_historical("GSIMX")
    if ft_html:
        print("  ✓ Financial Times HTML retrieved")
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        parsed_ft = scraper._parse_historical_data_with_openai("GSIMX", ft_html, "Financial Times", start_date_str, end_date_str)
        if parsed_ft:
            print(f"  ✓ Parsed: {parsed_ft['pct_change']:.2f}% ({parsed_ft['first_close']:.2f} → {parsed_ft['last_close']:.2f})")
        else:
            print("  ✗ Failed to parse Financial Times data")
    else:
        print("  ✗ Failed to retrieve Financial Times HTML")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_web_scraper() 