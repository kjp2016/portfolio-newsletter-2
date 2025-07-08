"""
Stock Data Service - Twelve Data API integration with rate limiting and fallbacks
Provides reliable stock price data using Twelve Data API with intelligent error handling.
"""

import logging
import json
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List, Optional
import pandas as pd
from openai import OpenAI
import streamlit as st
import requests
from twelvedata import TDClient

# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

class StockDataService:
    """
    Service for fetching stock and mutual fund data using Twelve Data API with rate limiting.
    """
    
    def __init__(self, openai_client: OpenAI, twelve_data_api_key: str = "2ddacad0dbdb4673bd92aff99988248c"):
        self.client = openai_client
        self.api_key = twelve_data_api_key
        self.td_client = TDClient(apikey=self.api_key)
        
        # Rate limiting settings
        self.calls_per_minute = 8  # Conservative limit
        self.calls_per_second = 2
        self.last_call_time = 0
        self.call_count = 0
        self.last_reset_time = time.time()
        
        # Cache for current prices to avoid duplicate calls
        self.price_cache = {}
        self.cache_duration = 300  # 5 minutes
    
    def _rate_limit(self):
        """Implement rate limiting to avoid API throttling."""
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
    
    def _make_api_call(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make a rate-limited API call with error handling."""
        self._rate_limit()
        
        try:
            response = requests.get(
                f"https://api.twelvedata.com/{endpoint}",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "error":
                    logging.error(f"API Error: {data.get('message', 'Unknown error')}")
                    return None
                return data
            elif response.status_code == 429:
                logging.warning("Rate limit hit, waiting 60 seconds...")
                time.sleep(60)
                return self._make_api_call(endpoint, params)  # Retry once
            else:
                logging.error(f"HTTP {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logging.error(f"API call failed: {e}")
            return None
    
    def get_current_prices(self, tickers: Tuple[str, ...]) -> Dict[str, Dict[str, Any]]:
        """
        Fetch current stock prices using Twelve Data API with fallback for unsupported symbols.
        """
        if not tickers:
            return {}
        
        stock_data = {}
        current_time = time.time()
        
        for ticker in tickers:
            # Check cache first
            if ticker in self.price_cache:
                cache_time, cache_data = self.price_cache[ticker]
                if current_time - cache_time < self.cache_duration:
                    stock_data[ticker] = cache_data
                    logging.info(f"Using cached price for {ticker}: ${cache_data['current_price']}")
                    continue
            
            logging.info(f"Fetching current price for {ticker} using Twelve Data...")
            
            try:
                # Get current price
                price_data = self._make_api_call("price", {
                    "symbol": ticker,
                    "apikey": self.api_key
                })
                
                if price_data and "price" in price_data:
                    current_price = float(price_data["price"])
                    
                    # Get company info
                    quote_data = self._make_api_call("quote", {
                        "symbol": ticker,
                        "apikey": self.api_key
                    })
                    
                    company_name = ticker
                    if quote_data and "name" in quote_data:
                        company_name = quote_data["name"]
                    
                    data = {
                        'company_name': company_name,
                        'current_price': current_price
                    }
                    
                    stock_data[ticker] = data
                    self.price_cache[ticker] = (current_time, data)
                    
                    logging.info(f"Successfully retrieved current price for {ticker}: ${current_price}")
                else:
                    # Fallback for unsupported symbols (mutual funds, etc.)
                    logging.warning(f"Twelve Data doesn't support {ticker}, using fallback...")
                    fallback_data = self._get_fallback_price(ticker)
                    if fallback_data:
                        stock_data[ticker] = fallback_data
                        self.price_cache[ticker] = (current_time, fallback_data)
                        logging.info(f"Fallback price for {ticker}: ${fallback_data['current_price']}")
                    else:
                        logging.warning(f"No valid current price found for {ticker}")
                        stock_data[ticker] = {'company_name': ticker, 'current_price': None}
                    
            except Exception as e:
                logging.error(f"Failed to fetch current price for {ticker}: {e}")
                stock_data[ticker] = {'company_name': ticker, 'current_price': None}
        
        valid_count = sum(1 for data in stock_data.values() 
                         if data.get('current_price') is not None and data.get('current_price') > 0)
        logging.info(f"Successfully retrieved current prices for {valid_count}/{len(tickers)} tickers")
        return stock_data
    
    def _get_fallback_price(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fallback method using OpenAI web search for symbols not supported by Twelve Data.
        Uses specific prompts to get accurate prices from Yahoo Finance.
        """
        try:
            logging.info(f"Using OpenAI web search fallback for {ticker}...")
            
            # Create a specific prompt for current price
            current_price_prompt = f"""
You are a financial data researcher. Find the CURRENT stock/mutual fund price for {ticker}.

STEP-BY-STEP INSTRUCTIONS:
1. Go to Yahoo Finance: https://finance.yahoo.com/quote/{ticker}
2. Find the current stock/mutual fund price (usually displayed prominently at the top)
3. Also find the company/fund name
4. Return ONLY a JSON object with this exact format:
{{"price": "123.45", "name": "Company Name"}}

IMPORTANT:
- Return ONLY the JSON object, no other text
- Use the exact price shown on Yahoo Finance
- For mutual funds, use the NAV (Net Asset Value) price
- If you cannot find the price, return {{"price": null, "name": "{ticker}"}}
"""

            # Use OpenAI web search to get current price
            response = self.client.responses.create(
                model="gpt-4o-mini",
                tools=[{"type": "web_search_preview"}],
                input=current_price_prompt
            )
            
            # Extract the response text
            response_text = ""
            for output in response.output:
                if output.type == "message" and hasattr(output, 'content'):
                    for content in output.content:
                        if hasattr(content, 'text'):
                            response_text += content.text
                        elif hasattr(content, 'output_text'):
                            response_text += content.output_text
            
            # Try to parse JSON from the response
            import re
            json_match = re.search(r'\{[^}]*"price"[^}]*\}', response_text)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    price_str = data.get("price")
                    name = data.get("name", ticker)
                    
                    if price_str and price_str != "null":
                        current_price = float(price_str)
                        return {
                            'company_name': name,
                            'current_price': current_price
                        }
                except (json.JSONDecodeError, ValueError) as e:
                    logging.error(f"Failed to parse JSON for {ticker}: {e}")
            
            logging.warning(f"Could not extract valid price for {ticker} from OpenAI response")
            return None
            
        except Exception as e:
            logging.error(f"OpenAI fallback failed for {ticker}: {e}")
            return None
    
    def _get_fallback_historical_price(self, ticker: str, start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
        """
        Fallback method using OpenAI web search for historical prices.
        """
        try:
            logging.info(f"Using OpenAI web search fallback for historical price of {ticker}...")
            
            # Create a specific prompt for historical price
            historical_prompt = f"""
You are a financial data researcher. Find the historical stock/mutual fund prices for {ticker}.

STEP-BY-STEP INSTRUCTIONS:
1. Go to Yahoo Finance historical data: https://finance.yahoo.com/quote/{ticker}/history
2. Find the closing price for {start_date} (start date)
3. Find the closing price for {end_date} (end date)
4. Return ONLY a JSON object with this exact format:
{{"start_price": "123.45", "end_price": "124.56", "start_date": "{start_date}", "end_date": "{end_date}"}}

IMPORTANT:
- Return ONLY the JSON object, no other text
- Use the exact closing prices shown on Yahoo Finance
- For mutual funds, use the NAV (Net Asset Value) prices
- If you cannot find the prices, return {{"start_price": null, "end_price": null}}
- Make sure to use the correct date format and find the actual historical data
"""

            # Use OpenAI web search to get historical prices
            response = self.client.responses.create(
                model="gpt-4o-mini",
                tools=[{"type": "web_search_preview"}],
                input=historical_prompt
            )
            
            # Extract the response text
            response_text = ""
            for output in response.output:
                if output.type == "message" and hasattr(output, 'content'):
                    for content in output.content:
                        if hasattr(content, 'text'):
                            response_text += content.text
                        elif hasattr(content, 'output_text'):
                            response_text += content.output_text
            
            # Try to parse JSON from the response
            import re
            json_match = re.search(r'\{[^}]*"start_price"[^}]*\}', response_text)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    start_price_str = data.get("start_price")
                    end_price_str = data.get("end_price")
                    
                    if start_price_str and end_price_str and start_price_str != "null" and end_price_str != "null":
                        start_price = float(start_price_str)
                        end_price = float(end_price_str)
                        
                        # Calculate performance metrics
                        abs_change = end_price - start_price
                        pct_change = (abs_change / start_price) * 100 if start_price != 0 else 0.0
                        
                        return {
                            "ticker": ticker.upper(),
                            "first_date": start_date,
                            "last_date": end_date,
                            "first_close": round(start_price, 2),
                            "last_close": round(end_price, 2),
                            "abs_change": round(abs_change, 2),
                            "pct_change": round(pct_change, 2),
                        }
                except (json.JSONDecodeError, ValueError) as e:
                    logging.error(f"Failed to parse JSON for {ticker}: {e}")
            
            logging.warning(f"Could not extract valid historical prices for {ticker} from OpenAI response")
            return None
            
        except Exception as e:
            logging.error(f"OpenAI historical fallback failed for {ticker}: {e}")
            return None
    
    def get_historical_prices(self, tickers: Tuple[str, ...], start_date: pd.Timestamp, end_date: pd.Timestamp) -> Dict[str, Dict[str, Any]]:
        """
        Fetch historical price data using Twelve Data API.
        Returns: {ticker: {"start_price": float, "end_price": float, "start_date": str, "end_date": str}}
        """
        if not tickers:
            return {}

        # First, get current prices (end_date)
        current_prices = self.get_current_prices(tickers)
        
        # Then, get historical prices (start_date) for each ticker individually
        performance_data = {}
        
        for ticker in tickers:
            logging.info(f"Fetching historical price for {ticker} using Twelve Data...")
            
            try:
                # Get historical data
                hist_data = self._make_api_call("time_series", {
                    "symbol": ticker,
                    "interval": "1day",
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "apikey": self.api_key
                })
                
                if hist_data and "values" in hist_data and hist_data["values"]:
                    # Get the first (oldest) and last (newest) prices
                    values = hist_data["values"]
                    first_price = float(values[-1]["close"])  # First in time series
                    last_price = float(values[0]["close"])    # Last in time series
                    
                    # Get current price
                    current_data = current_prices.get(ticker, {})
                    end_price = current_data.get('current_price')
                    
                    # Use current price if available, otherwise use last historical price
                    if end_price is None:
                        end_price = last_price
                    
                    # Validate price data
                    if (first_price is not None and end_price is not None and 
                        first_price > 0 and end_price > 0):
                        
                        # Calculate performance metrics
                        abs_change = float(end_price) - float(first_price)
                        pct_change = (abs_change / float(first_price)) * 100 if first_price != 0 else 0.0
                        
                        performance_data[ticker] = {
                            "ticker": ticker.upper(),
                            "first_date": start_date.strftime("%Y-%m-%d"),
                            "last_date": end_date.strftime("%Y-%m-%d"),
                            "first_close": round(float(first_price), 2),
                            "last_close": round(float(end_price), 2),
                            "abs_change": round(abs_change, 2),
                            "pct_change": round(pct_change, 2),
                        }
                        logging.info(f"Successfully retrieved historical price for {ticker}: ${first_price} → ${end_price} ({pct_change:.2f}%)")
                    else:
                        logging.warning(f"Invalid price data for {ticker}: first_price={first_price}, end_price={end_price}")
                        performance_data[ticker] = {"error": f"Invalid price data for {ticker}"}
                else:
                    # Fallback for unsupported symbols (mutual funds, etc.)
                    logging.warning(f"Twelve Data doesn't support historical data for {ticker}, using fallback...")
                    fallback_data = self._get_fallback_historical_price(
                        ticker, 
                        start_date.strftime("%Y-%m-%d"), 
                        end_date.strftime("%Y-%m-%d")
                    )
                    if fallback_data:
                        performance_data[ticker] = fallback_data
                        logging.info(f"Fallback historical price for {ticker}: ${fallback_data['first_close']} → ${fallback_data['last_close']} ({fallback_data['pct_change']:.2f}%)")
                    else:
                        logging.warning(f"No historical data found for {ticker}")
                        performance_data[ticker] = {"error": f"No historical data available for {ticker}"}
                    
            except Exception as e:
                logging.error(f"Failed to fetch historical price for {ticker}: {e}")
                performance_data[ticker] = {"error": f"Failed to fetch data: {str(e)}"}
        
        valid_count = sum(1 for data in performance_data.values() if "error" not in data)
        logging.info(f"Successfully retrieved historical data for {valid_count}/{len(tickers)} tickers")
        return performance_data
    
    def get_batch_price_performance(self, tickers: Tuple[str, ...], start_date: pd.Timestamp, end_date: pd.Timestamp, period_name: str = "period") -> Dict[str, Dict[str, Any]]:
        """
        Main function to get historical price performance with period name.
        Returns data in the format expected by the existing codebase.
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
        Returns list of valid tickers.
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

# Global instance for use across the application
def get_stock_data_service() -> StockDataService:
    """Get the global stock data service instance."""
    try:
        if 'stock_data_service' not in st.session_state:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            st.session_state['stock_data_service'] = StockDataService(client)
        return st.session_state['stock_data_service']
    except (AttributeError, KeyError):
        # Fallback for non-Streamlit environments
        from dotenv import load_dotenv
        import os
        load_dotenv()
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        return StockDataService(client) 