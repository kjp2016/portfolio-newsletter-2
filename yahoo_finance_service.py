#!/usr/bin/env python3
"""
Yahoo Finance Service - Extract financial data using fin-streamer tags
This approach is much more reliable than general HTML scraping.
"""

import logging
import time
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List, Optional
import pandas as pd
import requests
from bs4 import BeautifulSoup

# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

class YahooFinanceService:
    """
    Service for fetching stock data using Yahoo Finance fin-streamer tags.
    """
    
    def __init__(self):
        # Rate limiting settings
        self.calls_per_minute = 30  # 1 call per 2 seconds
        self.calls_per_second = 0.5  # 1 call per 2 seconds
        self.last_call_time = 0
        self.call_count = 0
        self.last_reset_time = time.time()
        
        # Cache for current prices
        self.price_cache = {}
        self.cache_duration = 300  # 5 minutes
        
        # User agent to prevent 403
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
    
    def _rate_limit(self):
        """Implement rate limiting to avoid being blocked."""
        current_time = time.time()
        
        # Reset counter if a minute has passed
        if current_time - self.last_reset_time >= 60:
            self.call_count = 0
            self.last_reset_time = current_time
        
        # Check if we're at the limit
        if self.call_count >= self.calls_per_minute:
            sleep_time = 60 - (current_time - self.last_reset_time)
            if sleep_time > 0:
                logging.info(f"Rate limit reached. Sleeping for {sleep_time:.1f} seconds...")
                time.sleep(sleep_time)
                self.call_count = 0
                self.last_reset_time = time.time()
        
        # Ensure minimum delay between calls
        time_since_last = current_time - self.last_call_time
        if time_since_last < (1.0 / self.calls_per_second):
            sleep_time = (1.0 / self.calls_per_second) - time_since_last
            time.sleep(sleep_time)
        
        self.last_call_time = time.time()
        self.call_count += 1
    
    def get_current_price(self, ticker: str) -> Optional[float]:
        """
        Get current price using Yahoo Finance fin-streamer tags.
        """
        try:
            # Check cache first
            current_time = time.time()
            if ticker in self.price_cache:
                cache_time, cache_price = self.price_cache[ticker]
                if current_time - cache_time < self.cache_duration:
                    logging.info(f"Using cached price for {ticker}: ${cache_price}")
                    return cache_price
            
            self._rate_limit()
            
            url = f"https://finance.yahoo.com/quote/{ticker}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Look for the fin-streamer tag with current price for THIS ticker
                # Yahoo Finance uses regularMarketPreviousClose for the current price
                tag = soup.find("fin-streamer", {"data-field": "regularMarketPreviousClose", "data-symbol": ticker})
                
                if tag:
                    price_text = tag.text.replace(",", "")
                    try:
                        price = float(price_text)
                        self.price_cache[ticker] = (current_time, price)
                        logging.info(f"Successfully retrieved current price for {ticker}: ${price}")
                        return price
                    except ValueError:
                        logging.warning(f"Could not convert price text '{price_text}' to float for {ticker}")
                else:
                    logging.warning(f"Could not find regularMarketPreviousClose tag for {ticker}")
                    
                    # Debug: show what fin-streamer tags we found for this ticker
                    all_fin_streamers = soup.find_all("fin-streamer", {"data-symbol": ticker})
                    logging.info(f"Found {len(all_fin_streamers)} fin-streamer tags for {ticker}")
                    for i, tag in enumerate(all_fin_streamers[:5]):
                        field = tag.get("data-field", "unknown")
                        text = tag.text
                        logging.info(f"  {i+1}. field={field}, text='{text}'")
            else:
                logging.error(f"HTTP {response.status_code} for {ticker}")
                
        except Exception as e:
            logging.error(f"Failed to get current price for {ticker}: {e}")
        
        return None
    
    def get_historical_data(self, ticker: str, days: int = 7) -> Optional[Dict[str, Any]]:
        """
        Get historical data by scraping the close price from exactly N days ago using Selenium.
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            import pandas as pd
            import time as pytime
            
            self._rate_limit()
            
            # Calculate the date exactly N days ago
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")
            
            url = f"https://finance.yahoo.com/quote/{ticker}/history?p={ticker}"
            
            # Set up Selenium headless Chrome
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--window-size=1920,1080")
            driver = webdriver.Chrome(options=options)
            driver.get(url)
            pytime.sleep(3)  # Wait for JS to load
            
            # Find the historical price table rows
            rows = driver.find_elements(By.CSS_SELECTOR, 'table[data-test="historical-prices"] tbody tr')
            prices = []
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, 'td')
                if len(cols) >= 6:
                    date_str = cols[0].text.strip()
                    close_str = cols[4].text.strip().replace(',', '')
                    try:
                        date = pd.to_datetime(date_str)
                        close = float(close_str)
                        prices.append((date, close))
                    except Exception:
                        continue
            driver.quit()
            
            # Find the price closest to N days ago
            if prices:
                prices.sort(key=lambda x: abs((x[0] - start_date).days))
                start_price = prices[0][1]
                # Find the most recent price (today or last trading day)
                prices.sort(key=lambda x: x[0], reverse=True)
                end_price = prices[0][1]
                
                abs_change = end_price - start_price
                pct_change = (abs_change / start_price) * 100 if start_price != 0 else 0.0
                return {
                    "ticker": ticker.upper(),
                    "first_date": start_date_str,
                    "last_date": end_date_str,
                    "first_close": round(start_price, 2),
                    "last_close": round(end_price, 2),
                    "abs_change": round(abs_change, 2),
                    "pct_change": round(pct_change, 2),
                    "source": "Yahoo Finance (selenium)"
                }
            logging.warning(f"Could not extract historical data for {ticker} using Selenium")
        except Exception as e:
            logging.error(f"Failed to get historical data for {ticker} using Selenium: {e}")
        return None
    
    def get_current_prices(self, tickers: Tuple[str, ...]) -> Dict[str, Dict[str, Any]]:
        """
        Fetch current stock prices for multiple tickers.
        """
        if not tickers:
            return {}
        
        stock_data = {}
        
        for ticker in tickers:
            current_price = self.get_current_price(ticker)
            
            if current_price:
                stock_data[ticker] = {
                    'company_name': ticker,
                    'current_price': current_price,
                    'source': 'Yahoo Finance'
                }
            else:
                stock_data[ticker] = {
                    'company_name': ticker,
                    'current_price': None,
                    'source': 'None'
                }
        
        valid_count = sum(1 for data in stock_data.values() 
                         if data.get('current_price') is not None and data.get('current_price') > 0)
        logging.info(f"Successfully retrieved current prices for {valid_count}/{len(tickers)} tickers")
        return stock_data
    
    def get_historical_prices(self, tickers: Tuple[str, ...], start_date: pd.Timestamp, end_date: pd.Timestamp) -> Dict[str, Dict[str, Any]]:
        """
        Fetch historical price data for multiple tickers.
        Note: This is a simplified implementation. For production, consider using an API.
        """
        if not tickers:
            return {}
        
        performance_data = {}
        days_diff = (end_date - start_date).days
        
        for ticker in tickers:
            logging.info(f"Fetching historical price for {ticker} using Yahoo Finance...")
            
            historical_data = self.get_historical_data(ticker, days_diff)
            
            if historical_data:
                performance_data[ticker] = historical_data
                logging.info(f"Successfully retrieved historical price for {ticker}: ${historical_data['first_close']} → ${historical_data['last_close']} ({historical_data['pct_change']:.2f}%)")
            else:
                logging.warning(f"No historical data found for {ticker}")
                performance_data[ticker] = {"error": f"No historical data available for {ticker}"}
        
        valid_count = sum(1 for data in performance_data.values() if "error" not in data)
        logging.info(f"Successfully retrieved historical data for {valid_count}/{len(tickers)} tickers")
        return performance_data
    
    def get_batch_price_performance(self, tickers: Tuple[str, ...], start_date: pd.Timestamp, end_date: pd.Timestamp, period_name: str = "period") -> Dict[str, Dict[str, Any]]:
        """
        Main function to get historical price performance with period name.
        """
        performance_data = self.get_historical_prices(tickers, start_date, end_date)
        
        # Add period_name to each result
        for ticker_data in performance_data.values():
            if "error" not in ticker_data:
                ticker_data["period_name"] = period_name
        
        return performance_data
    
    def validate_tickers(self, tickers: List[str]) -> List[str]:
        """
        Validate tickers by checking if current prices can be fetched.
        """
        if not tickers:
            return []
        current_data = self.get_current_prices(tuple(tickers))
        valid_tickers = [
            ticker for ticker in tickers 
            if ticker in current_data and current_data[ticker].get('current_price') is not None
        ]
        logging.info(f"Validated {len(valid_tickers)} out of {len(tickers)} tickers")
        return valid_tickers

def get_yahoo_finance_service() -> YahooFinanceService:
    """
    Get or create a YahooFinanceService instance.
    """
    if not hasattr(get_yahoo_finance_service, '_instance'):
        get_yahoo_finance_service._instance = YahooFinanceService()
    return get_yahoo_finance_service._instance 