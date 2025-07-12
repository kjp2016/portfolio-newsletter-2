#!/usr/bin/env python3
"""
Improved web scraper that focuses on finding actual price data.
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import os
import sys
import toml
import json
import re
from bs4 import BeautifulSoup
from openai import OpenAI

def get_actual_price_data(ticker: str):
    """Get actual price data from multiple sources with better extraction."""
    
    # Read API key from Streamlit secrets
    try:
        secrets = toml.load(".streamlit/secrets.toml")
        api_key = secrets.get("OPENAI_API_KEY")
    except Exception as e:
        print(f"Could not read secrets file: {e}")
        return None
    
    if not api_key:
        print("No OpenAI API key found in secrets file")
        return None
    
    client = OpenAI(api_key=api_key)
    
    print(f"Getting price data for {ticker}")
    print("=" * 60)
    
    # Try multiple sources
    sources = [
        ("Yahoo Finance Quote", f"https://finance.yahoo.com/quote/{ticker}"),
        ("NASDAQ Quote", f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}"),
        ("Google Finance", f"https://www.google.com/finance/quote/{ticker}:NASDAQ"),
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    for source_name, url in sources:
        print(f"\nTrying {source_name}: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                # Parse with BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for specific price elements
                price_data = extract_price_from_soup(soup, ticker, source_name)
                
                if price_data:
                    print(f"✅ Found price data from {source_name}: {price_data}")
                    return price_data
                else:
                    print(f"❌ No price data found in {source_name}")
                    
                    # Try OpenAI parsing as fallback
                    print(f"🔄 Trying OpenAI parsing for {source_name}...")
                    openai_data = parse_with_openai(client, response.text, ticker, source_name)
                    if openai_data:
                        print(f"✅ OpenAI found data from {source_name}: {openai_data}")
                        return openai_data
                    
            else:
                print(f"❌ Failed with status code: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error with {source_name}: {e}")
            continue
    
    print("❌ No price data found from any source")
    return None

def extract_price_from_soup(soup, ticker: str, source: str):
    """Extract price data directly from BeautifulSoup."""
    
    # Look for common price patterns in different sources
    price_patterns = []
    
    if "yahoo" in source.lower():
        # Yahoo Finance specific patterns
        price_patterns = [
            # Look for data-testid attributes
            soup.find(attrs={"data-testid": "qsp-price"}),
            soup.find(attrs={"data-testid": "quote-price"}),
            # Look for specific classes
            soup.find(class_=re.compile(r"price", re.I)),
            soup.find(class_=re.compile(r"quote", re.I)),
            # Look for spans with price-like content
            soup.find("span", string=re.compile(r"\$\d+\.?\d*")),
        ]
    elif "nasdaq" in source.lower():
        # NASDAQ specific patterns
        price_patterns = [
            soup.find(class_=re.compile(r"price", re.I)),
            soup.find(class_=re.compile(r"quote", re.I)),
            soup.find("span", string=re.compile(r"\$\d+\.?\d*")),
        ]
    else:
        # Generic patterns
        price_patterns = [
            soup.find(string=re.compile(r"\$\d+\.?\d*")),
            soup.find(class_=re.compile(r"price", re.I)),
            soup.find(class_=re.compile(r"quote", re.I)),
        ]
    
    # Extract text from found elements
    price_texts = []
    for pattern in price_patterns:
        if pattern:
            text = pattern.get_text(strip=True)
            if text and re.search(r'\$\d+\.?\d*', text):
                price_texts.append(text)
    
    # Also look for any text containing price patterns
    all_text = soup.get_text()
    price_matches = re.findall(r'\$\d+\.?\d*', all_text)
    
    if price_matches:
        price_texts.extend(price_matches)
    
    # Remove duplicates and clean
    unique_prices = list(set(price_texts))
    print(f"Found price patterns: {unique_prices[:5]}")  # Show first 5
    
    # Try to extract meaningful prices
    prices = []
    for text in unique_prices:
        matches = re.findall(r'\$(\d+\.?\d*)', text)
        for match in matches:
            try:
                price = float(match)
                if 1.0 <= price <= 10000.0:  # Reasonable price range
                    prices.append(price)
            except ValueError:
                continue
    
    if len(prices) >= 2:
        # Use the two most recent/relevant prices
        prices.sort()
        start_price = prices[0]
        end_price = prices[-1]
        
        # Calculate performance
        change = end_price - start_price
        pct_change = (change / start_price) * 100 if start_price != 0 else 0.0
        
        # Use today's date as end date, 7 days ago as start date
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        return {
            "ticker": ticker.upper(),
            "first_date": start_date,
            "last_date": end_date,
            "first_close": round(start_price, 2),
            "last_close": round(end_price, 2),
            "abs_change": round(change, 2),
            "pct_change": round(pct_change, 2),
            "source": f"{source} (direct extraction)"
        }
    
    return None

def parse_with_openai(client, html_content: str, ticker: str, source: str):
    """Parse HTML content with OpenAI."""
    
    # Clean the HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    for script in soup(["script", "style"]):
        script.decompose()
    visible_text = soup.get_text(separator="\n", strip=True)
    visible_text = '\n'.join([line for line in visible_text.splitlines() if line.strip()])
    
    # Use today's date as end date, 7 days ago as start date
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    prompt = f"""
Extract ANY price information from this financial website text. Look for current prices, recent prices, or any numerical price data.

TICKER: {ticker}
SOURCE: {source}

TEXT:
{visible_text[:6000]}

Return ONLY a JSON object with this format:
{{"start_price": "123.45", "end_price": "124.56", "start_date": "{start_date}", "end_date": "{end_date}", "source": "{source}"}}

If you find any prices, use them. If not, return null values.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Clean and parse JSON
        cleaned_text = re.sub(r'```json\s*', '', response_text)
        cleaned_text = re.sub(r'```\s*', '', cleaned_text)
        cleaned_text = cleaned_text.strip()
        
        try:
            data = json.loads(cleaned_text)
            start_price_str = data.get("start_price")
            end_price_str = data.get("end_price")
            
            if start_price_str and end_price_str and start_price_str != "null" and end_price_str != "null":
                start_price = float(str(start_price_str).replace('$', '').replace(',', ''))
                end_price = float(str(end_price_str).replace('$', '').replace(',', ''))
                
                change = end_price - start_price
                pct_change = (change / start_price) * 100 if start_price != 0 else 0.0
                
                return {
                    "ticker": ticker.upper(),
                    "first_date": start_date,
                    "last_date": end_date,
                    "first_close": round(start_price, 2),
                    "last_close": round(end_price, 2),
                    "abs_change": round(change, 2),
                    "pct_change": round(pct_change, 2),
                    "source": f"{source} (OpenAI)"
                }
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Failed to parse OpenAI response: {e}")
            
    except Exception as e:
        print(f"OpenAI parsing failed: {e}")
    
    return None

def main():
    """Test the improved scraper."""
    tickers = ["AMZN", "MSFT", "GOOGL"]
    
    for ticker in tickers:
        print(f"\n{'='*80}")
        print(f"TESTING {ticker}")
        print(f"{'='*80}")
        
        result = get_actual_price_data(ticker)
        
        if result:
            print(f"\n✅ SUCCESS for {ticker}:")
            print(f"  ${result['first_close']} → ${result['last_close']} ({result['pct_change']:.2f}%)")
            print(f"  Source: {result['source']}")
        else:
            print(f"\n❌ FAILED for {ticker}")

if __name__ == "__main__":
    main() 