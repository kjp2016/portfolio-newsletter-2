#!/usr/bin/env python3
"""
Alpha Vantage Service - Fetch financial data using Alpha Vantage API
"""

import logging
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List, Optional
import pandas as pd
import os
import streamlit as st

# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

class AlphaVantageService:
    """
    Service for fetching stock data using Alpha Vantage API.
    """
    
    def __init__(self):
        # Get API key from environment or Streamlit secrets
        try:
            self.api_key = st.secrets["ALPHA_VANTAGE_API_KEY"]
        except (AttributeError, KeyError):
            self.api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "K9ARFXZTWE9BE4MT")
        
        self.base_url = "https://www.alphavantage.co/query"
        self.quota_limit = 500  # Premium tier limit
        self.calls_per_minute = 5  # 5 requests per minute
        self.last_call_time = 0
        self.call_count = 0
        self.last_reset_time = time.time()
        
        # Cache for current prices and historical data
        self.price_cache = {}
        self.historical_cache = {}
        self.cache_duration = 300  # 5 minutes
    
    def _rate_limit(self):
        """Implement rate limiting to respect Alpha Vantage limits."""
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
        
        # Ensure minimum delay between calls (12.5 seconds as per your test script)
        time_since_last = current_time - self.last_call_time
        if time_since_last < 12.5:
            sleep_time = 12.5 - time_since_last
            time.sleep(sleep_time)
        
        self.last_call_time = time.time()
        self.call_count += 1
    
    def _safe_series(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Safely fetch time series data for a symbol.
        Based on your working test script.
        """
        try:
            self._rate_limit()
            
            params = {
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                "outputsize": "compact",
                "apikey": self.api_key
            }
            
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Check for API errors
            if "Time Series (Daily)" not in data:
                msg = data.get("Note") or data.get("Information") or data.get("Error Message")
                raise RuntimeError(msg or f"{symbol}: unknown API response")
            
            return data["Time Series (Daily)"]
            
        except Exception as e:
            logging.error(f"Failed to fetch data for {symbol}: {e}")
            return None
    
    def _nearest_date(self, time_series: Dict[str, Any], target_date: datetime) -> Optional[Tuple[str, float]]:
        """
        Find the nearest available date in the time series.
        Based on your working test script.
        """
        current_date = target_date
        max_attempts = 30  # Look back up to 30 days
        
        for _ in range(max_attempts):
            date_key = current_date.strftime("%Y-%m-%d")
            if date_key in time_series:
                try:
                    close_price = float(time_series[date_key]["4. close"])
                    return date_key, close_price
                except (KeyError, ValueError):
                    pass
            current_date -= timedelta(days=1)
        
        return None
    
    def get_current_price(self, ticker: str) -> Optional[float]:
        """
        Get current price using Alpha Vantage API.
        """
        try:
            # Check cache first
            current_time = time.time()
            if ticker in self.price_cache:
                cache_time, cache_price = self.price_cache[ticker]
                if current_time - cache_time < self.cache_duration:
                    logging.info(f"Using cached price for {ticker}: ${cache_price}")
                    return cache_price
            
            time_series = self._safe_series(ticker)
            if not time_series:
                return None
            
            # Get the most recent price (today or last trading day)
            today = datetime.now()
            nearest = self._nearest_date(time_series, today)
            
            if nearest:
                date_key, price = nearest
                self.price_cache[ticker] = (current_time, price)
                logging.info(f"Successfully retrieved current price for {ticker}: ${price} on {date_key}")
                return price
            
        except Exception as e:
            logging.error(f"Failed to get current price for {ticker}: {e}")
        
        return None
    
    def get_historical_performance(self, ticker: str, start_date: datetime, end_date: datetime) -> Optional[Dict[str, Any]]:
        """
        Get historical performance data for a ticker.
        """
        try:
            # Check cache first
            cache_key = f"{ticker}_{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}"
            current_time = time.time()
            
            if cache_key in self.historical_cache:
                cache_time, cache_data = self.historical_cache[cache_key]
                if current_time - cache_time < self.cache_duration:
                    logging.info(f"Using cached historical data for {ticker}")
                    return cache_data
            
            time_series = self._safe_series(ticker)
            if not time_series:
                return None
            
            # Find start and end prices
            start_nearest = self._nearest_date(time_series, start_date)
            end_nearest = self._nearest_date(time_series, end_date)
            
            if start_nearest and end_nearest:
                start_date_key, start_price = start_nearest
                end_date_key, end_price = end_nearest
                
                abs_change = end_price - start_price
                pct_change = (abs_change / start_price) * 100 if start_price != 0 else 0.0
                
                result = {
                    "ticker": ticker.upper(),
                    "first_date": start_date_key,
                    "last_date": end_date_key,
                    "first_close": round(start_price, 2),
                    "last_close": round(end_price, 2),
                    "abs_change": round(abs_change, 2),
                    "pct_change": round(pct_change, 2),
                    "source": "Alpha Vantage API"
                }
                
                # Cache the result
                self.historical_cache[cache_key] = (current_time, result)
                logging.info(f"Successfully retrieved historical data for {ticker}: ${start_price} → ${end_price} ({pct_change:.2f}%)")
                return result
            
        except Exception as e:
            logging.error(f"Failed to get historical performance for {ticker}: {e}")
        
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
                    'source': 'Alpha Vantage API'
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
        """
        if not tickers:
            return {}
        
        performance_data = {}
        
        for ticker in tickers:
            logging.info(f"Fetching historical price for {ticker} using Alpha Vantage...")
            
            # Convert pandas Timestamp to datetime
            start_dt = start_date.to_pydatetime()
            end_dt = end_date.to_pydatetime()
            
            historical_data = self.get_historical_performance(ticker, start_dt, end_dt)
            
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
        valid_tickers = []
        for ticker in tickers:
            if self.get_current_price(ticker):
                valid_tickers.append(ticker)
            else:
                logging.warning(f"Invalid ticker: {ticker}")
        return valid_tickers

def get_alpha_vantage_service() -> AlphaVantageService:
    """
    Get or create an AlphaVantageService instance.
    """
    if not hasattr(get_alpha_vantage_service, '_instance'):
        get_alpha_vantage_service._instance = AlphaVantageService()
    return get_alpha_vantage_service._instance 