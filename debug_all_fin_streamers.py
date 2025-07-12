#!/usr/bin/env python3
"""
Comprehensive debug script to see all fin-streamer tags and find the correct price.
"""

import requests
from bs4 import BeautifulSoup
import re

def debug_all_fin_streamers():
    """Debug all fin-streamer tags to find the correct price."""
    
    ticker = "AMZN"
    url = f"https://finance.yahoo.com/quote/{ticker}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    print(f"Debugging ALL fin-streamer tags for {ticker}")
    print(f"URL: {url}")
    print("=" * 80)
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find ALL fin-streamer tags
            all_fin_streamers = soup.find_all("fin-streamer")
            print(f"Found {len(all_fin_streamers)} fin-streamer tags")
            print("=" * 80)
            
            # Show all fin-streamer tags with their attributes
            for i, tag in enumerate(all_fin_streamers):
                symbol = tag.get("data-symbol", "unknown")
                field = tag.get("data-field", "unknown")
                value = tag.get("data-value", "unknown")
                text = tag.text.strip()
                
                print(f"{i+1:2d}. Symbol: {symbol:10s} | Field: {field:20s} | Value: {value:10s} | Text: '{text}'")
                
                # Highlight the ones that might be relevant
                if symbol == ticker:
                    print(f"     ⭐ THIS IS FOR {ticker}!")
                elif field == "regularMarketPrice":
                    print(f"     💰 This is a price field!")
                elif "price" in field.lower():
                    print(f"     💰 This is a price-related field!")
            
            print("\n" + "=" * 80)
            print("ANALYSIS:")
            print("=" * 80)
            
            # Look for tags specifically for AMZN
            amzn_tags = [tag for tag in all_fin_streamers if tag.get("data-symbol") == ticker]
            print(f"Tags specifically for {ticker}: {len(amzn_tags)}")
            
            for tag in amzn_tags:
                field = tag.get("data-field", "unknown")
                text = tag.text.strip()
                print(f"  - {field}: '{text}'")
            
            # Look for price-related fields
            price_fields = [tag for tag in all_fin_streamers if "price" in tag.get("data-field", "").lower()]
            print(f"\nPrice-related fields: {len(price_fields)}")
            
            for tag in price_fields:
                symbol = tag.get("data-symbol", "unknown")
                field = tag.get("data-field", "unknown")
                text = tag.text.strip()
                print(f"  - {symbol} {field}: '{text}'")
            
            # Look for regularMarketPrice specifically
            regular_price_tags = [tag for tag in all_fin_streamers if tag.get("data-field") == "regularMarketPrice"]
            print(f"\nRegular market price tags: {len(regular_price_tags)}")
            
            for tag in regular_price_tags:
                symbol = tag.get("data-symbol", "unknown")
                text = tag.text.strip()
                print(f"  - {symbol}: '{text}'")
                
        else:
            print(f"Failed with status code: {response.status_code}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_all_fin_streamers() 