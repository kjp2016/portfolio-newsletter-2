#!/usr/bin/env python3
"""
Debug script to see what Yahoo Finance fin-streamer tags are actually returning.
"""

import requests
from bs4 import BeautifulSoup
import re

def debug_yahoo_prices():
    """Debug what Yahoo Finance is actually returning."""
    
    ticker = "AMZN"
    url = f"https://finance.yahoo.com/quote/{ticker}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    print(f"Debugging Yahoo Finance for {ticker}")
    print(f"URL: {url}")
    print("=" * 60)
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for the fin-streamer tag
            tag = soup.find("fin-streamer", {"data-field": "regularMarketPrice"})
            
            if tag:
                print(f"Found fin-streamer tag: {tag}")
                print(f"Tag text: '{tag.text}'")
                print(f"Tag attributes: {tag.attrs}")
                
                # Try to parse the price
                price_text = tag.text.replace(",", "")
                print(f"Cleaned price text: '{price_text}'")
                
                try:
                    price = float(price_text)
                    print(f"Parsed price: ${price}")
                except ValueError as e:
                    print(f"Failed to parse price: {e}")
            else:
                print("❌ Could not find fin-streamer tag with data-field='regularMarketPrice'")
                
                # Look for any fin-streamer tags
                all_fin_streamers = soup.find_all("fin-streamer")
                print(f"Found {len(all_fin_streamers)} fin-streamer tags:")
                
                for i, tag in enumerate(all_fin_streamers[:10]):  # Show first 10
                    print(f"  {i+1}. {tag}")
                    print(f"     Text: '{tag.text}'")
                    print(f"     Attrs: {tag.attrs}")
                
                # Also look for other price-related elements
                print("\nLooking for other price elements:")
                
                # Look for elements with price-like content
                price_elements = soup.find_all(string=re.compile(r'\$\d+\.?\d*'))
                print(f"Found {len(price_elements)} elements with price patterns:")
                
                for i, element in enumerate(price_elements[:10]):  # Show first 10
                    print(f"  {i+1}. '{element}'")
                    parent = element.parent
                    if parent:
                        print(f"     Parent tag: {parent.name}")
                        print(f"     Parent attrs: {parent.attrs}")
                
        else:
            print(f"Failed with status code: {response.status_code}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_yahoo_prices() 