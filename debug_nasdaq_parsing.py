#!/usr/bin/env python3
"""
Debug script to test NASDAQ scraping for better historical data.
"""

import pandas as pd
from datetime import datetime, timedelta
import os
import sys
import toml
import json
import re
from bs4 import BeautifulSoup
import requests

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from openai import OpenAI

def debug_nasdaq_parsing():
    """Debug NASDAQ scraping for historical data."""
    
    # Read API key from Streamlit secrets
    try:
        secrets = toml.load(".streamlit/secrets.toml")
        api_key = secrets.get("OPENAI_API_KEY")
    except Exception as e:
        print(f"Could not read secrets file: {e}")
        return
    
    if not api_key:
        print("No OpenAI API key found in secrets file")
        return
    
    client = OpenAI(api_key=api_key)
    
    # Test with AMZN
    ticker = "AMZN"
    start_date = "2025-07-02"
    end_date = "2025-07-09"
    
    print(f"Debugging NASDAQ parsing for {ticker}")
    print(f"Date range: {start_date} to {end_date}")
    print("=" * 80)
    
    # Get HTML content from NASDAQ
    url = f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}/historical"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"NASDAQ Status Code: {response.status_code}")
        
        if response.status_code == 200:
            # Clean the HTML with BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            for script in soup(["script", "style"]):
                script.decompose()
            visible_text = soup.get_text(separator="\n", strip=True)
            visible_text = '\n'.join([line for line in visible_text.splitlines() if line.strip()])
            
            print(f"HTML Content Length: {len(response.text)} characters")
            print(f"Visible Text Length: {len(visible_text)} characters")
            
            # Show first 2000 characters of visible text
            print("\n" + "=" * 80)
            print("FIRST 2000 CHARACTERS OF VISIBLE TEXT:")
            print("=" * 80)
            print(visible_text[:2000])
            
            # Look for price-related content
            price_indicators = ['price', 'close', 'open', 'high', 'low', 'volume', 'date', 'change', 'percent']
            found_indicators = [indicator for indicator in price_indicators if indicator.lower() in visible_text.lower()]
            print(f"\nPrice indicators found: {found_indicators}")
            
            # Look for specific price patterns
            print("\n" + "=" * 80)
            print("PRICE PATTERNS FOUND:")
            print("=" * 80)
            
            # Look for dollar amounts
            dollar_patterns = [
                r'\$(\d+\.?\d*)',  # $123.45
                r'(\d+\.?\d*)\s*USD',  # 123.45 USD
                r'price[:\s]*(\d+\.?\d*)',  # price: 123.45
                r'close[:\s]*(\d+\.?\d*)',  # close: 123.45
            ]
            
            for pattern in dollar_patterns:
                matches = re.findall(pattern, visible_text, re.IGNORECASE)
                if matches:
                    print(f"Pattern '{pattern}': {matches[:10]}")  # Show first 10 matches
            
            # Now test OpenAI parsing
            print("\n" + "=" * 80)
            print("TESTING OPENAI PARSING:")
            print("=" * 80)
            
            prompt = f"""
You are a financial data parser. Extract historical price data from the following visible text from NASDAQ.

TICKER: {ticker}
SOURCE: NASDAQ
START DATE: {start_date}
END DATE: {end_date}

VISIBLE TEXT:
{visible_text[:8000]}

INSTRUCTIONS:
1. Look for any price data, charts, or financial information
2. Try to find current price and any historical price information
3. If you can't find exact dates, look for recent price changes or performance data
4. Return ONLY a JSON object with this exact format:
{{"start_price": "123.45", "end_price": "124.56", "start_date": "{start_date}", "end_date": "{end_date}", "source": "NASDAQ"}}

CRITICAL OUTPUT REQUIREMENTS:
- Return ONLY the JSON object, no introduction, explanation, or other text
- Do NOT include markdown formatting, backticks, or code blocks
- Do NOT add any text before or after the JSON
- The prices should be numbers without dollar signs (e.g., "123.45" not "$123.45")
- If you cannot find the prices, return: {{"start_price": null, "end_price": null, "source": "NASDAQ"}}
- Ensure the JSON is valid and properly formatted

EXAMPLE OUTPUT:
{{"start_price": "22.54", "end_price": "22.59", "start_date": "{start_date}", "end_date": "{end_date}", "source": "NASDAQ"}}
"""

            print(f"Prompt length: {len(prompt)} characters")
            print(f"Visible text in prompt: {len(visible_text[:8000])} characters")
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )
            
            response_text = response.choices[0].message.content
            print(f"\nOpenAI Response Length: {len(response_text)} characters")
            print(f"OpenAI Response: {repr(response_text)}")
            
            # Try to parse the response
            try:
                # Remove any markdown formatting
                cleaned_text = re.sub(r'```json\s*', '', response_text)
                cleaned_text = re.sub(r'```\s*', '', cleaned_text)
                cleaned_text = cleaned_text.strip()
                
                print(f"\nCleaned Response: {repr(cleaned_text)}")
                
                # Try to parse as JSON
                try:
                    data = json.loads(cleaned_text)
                    print(f"\nParsed JSON: {json.dumps(data, indent=2)}")
                except json.JSONDecodeError as e:
                    print(f"\nJSON Parse Error: {e}")
                    
                    # Try to find JSON object in the text
                    json_match = re.search(r'\{[^}]*"start_price"[^}]*\}', cleaned_text)
                    if json_match:
                        json_str = json_match.group()
                        print(f"\nFound JSON match: {json_str}")
                        try:
                            data = json.loads(json_str)
                            print(f"Parsed from match: {json.dumps(data, indent=2)}")
                        except json.JSONDecodeError as e2:
                            print(f"Match parse error: {e2}")
                    
            except Exception as e:
                print(f"Error processing response: {e}")
                
        else:
            print(f"Failed to get NASDAQ data: {response.status_code}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_nasdaq_parsing() 