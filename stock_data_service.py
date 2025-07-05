"""
Stock Data Service - Multi-source stock data fetching with fallback mechanisms
Provides reliable stock price data using multiple sources to avoid rate limiting issues.
"""

import logging
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List, Optional
import pandas as pd
from openai import OpenAI
import streamlit as st
import random

# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

class StockDataService:
    """
    Multi-source stock data service with fallback mechanisms.
    Uses OpenAI Responses API with web search for reliable stock data.
    """
    
    def __init__(self, openai_client: OpenAI):
        self.client = openai_client
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour cache
        
    def get_current_prices(self, tickers: Tuple[str, ...]) -> Dict[str, Dict[str, Any]]:
        """
        Fetch current stock prices using individual API calls for each ticker.
        Returns: {ticker: {"company_name": str, "current_price": float}}
        """
        if not tickers:
            return {}
        
        stock_data = {}
        today = datetime.now().strftime("%B %d, %Y")
        
        for ticker in tickers:
            logging.info(f"Fetching current price for {ticker}...")
            
            query = f"""You are a financial data researcher. Find the CURRENT stock price for {ticker} as of {today}.

Search the web for the most recent closing stock price for {ticker}.
Return ONLY a JSON object with the current price:

{{
    "company_name": "[Full Company Name]",
    "current_price": [price]
}}

CRITICAL REQUIREMENTS:
- Use web search to find current market price
- Return realistic stock price
- Include full company name
- Return ONLY the JSON object - no explanation, no markdown, no other text
- The response must start with {{ and end with }}
- Do not include any text before or after the JSON
- Do not use ```json``` formatting - just return the raw JSON"""

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.client.responses.create(
                        model="gpt-4o-mini",
                        tools=[{"type": "web_search_preview"}],
                        input=query
                    )
                    
                    output_text = response.output_text
                    if output_text is None:
                        raise ValueError("OpenAI returned None content")
                    
                    # Try to extract JSON from response - be more flexible
                    json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', output_text)
                    if not json_match:
                        json_match = re.search(r'\{[\s\S]*\}', output_text)
                    
                    if json_match:
                        json_str = json_match.group(1) if json_match.groups() else json_match.group(0)
                        ticker_data = json.loads(json_str)
                        
                        # Validate price data
                        current_price = ticker_data.get('current_price')
                        company_name = ticker_data.get('company_name', ticker)
                        
                        if isinstance(current_price, (int, float)) and current_price > 0:
                            stock_data[ticker] = {
                                'company_name': company_name,
                                'current_price': current_price
                            }
                            logging.info(f"Successfully retrieved current price for {ticker}: ${current_price}")
                            break  # Success, move to next ticker
                        else:
                            raise ValueError(f"Invalid price data for {ticker}: {current_price}")
                    else:
                        raise ValueError("No JSON found in response")
                        
                except Exception as e:
                    logging.error(f"Attempt {attempt + 1} failed to fetch current price for {ticker}: {e}")
                    if attempt == max_retries - 1:
                        # Last attempt failed, return error data
                        stock_data[ticker] = {'company_name': ticker, 'current_price': None}
                    else:
                        # Wait before retrying
                        import time
                        time.sleep(2 ** attempt)  # Exponential backoff
        
        valid_count = sum(1 for data in stock_data.values() 
                         if data.get('current_price') is not None and data.get('current_price') > 0)
        logging.info(f"Successfully retrieved current prices for {valid_count}/{len(tickers)} tickers")
        return stock_data
    
    def get_historical_prices(self, tickers: Tuple[str, ...], start_date: pd.Timestamp, end_date: pd.Timestamp) -> Dict[str, Dict[str, Any]]:
        """
        Fetch historical price data using individual API calls for each ticker.
        Returns: {ticker: {"start_price": float, "end_price": float, "start_date": str, "end_date": str}}
        """
        if not tickers:
            return {}

        # First, get current prices (end_date)
        current_prices = self.get_current_prices(tickers)
        
        # Then, get historical prices (start_date) for each ticker individually
        start_date_str = start_date.strftime("%B %d, %Y")
        performance_data = {}
        
        for ticker in tickers:
            logging.info(f"Fetching historical price for {ticker} on {start_date_str}...")
            
            query = f"""You are a financial data researcher. Find the ACTUAL historical closing stock price for {ticker} on {start_date_str}.

STEP-BY-STEP INSTRUCTIONS:
1. Search the web for "historical stock price {ticker} {start_date_str}"
2. Look for financial websites like Yahoo Finance, MarketWatch, Alpha Vantage, or similar
3. Find the CLOSING PRICE for the specified date
4. If {start_date_str} was a weekend/holiday, find the closing price from the most recent trading day before that date
5. Do NOT use current prices - only use historical closing prices from the specified date
6. IMPORTANT: The price you return must be DIFFERENT from current market prices

Return ONLY a JSON object with the historical closing price:

{{
    "historical_price": [price]
}}

CRITICAL REQUIREMENTS:
- Search for ACTUAL historical data, not current prices
- Use web search to find real historical closing prices
- If the date was a weekend/holiday, use the previous trading day's closing price
- Price must be realistic (typically $1-$1000 for most stocks)
- Do NOT return current market prices under any circumstances
- Search multiple financial websites to verify accuracy
- The historical price MUST be different from current prices to be valid
- Return ONLY the JSON object - no explanation, no markdown, no other text
- The response must start with {{ and end with }}
- Do not include any text before or after the JSON
- Do not use ```json``` formatting - just return the raw JSON"""

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.client.responses.create(
                        model="gpt-4o-mini",
                        tools=[{"type": "web_search_preview"}],
                        input=query
                    )
                    
                    output_text = response.output_text
                    if output_text is None:
                        raise ValueError("OpenAI returned None content")
                    
                    # Try to extract JSON from response
                    json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', output_text)
                    if not json_match:
                        json_match = re.search(r'\{[\s\S]*\}', output_text)
                    
                    if json_match:
                        json_str = json_match.group(1) if json_match.groups() else json_match.group(0)
                        ticker_data = json.loads(json_str)
                        
                                                # Get historical price
                        start_price = ticker_data.get('historical_price')
                        
                        # Handle case where AI returns a list instead of a number
                        if isinstance(start_price, list) and len(start_price) > 0:
                            start_price = start_price[0]
                        
                        # Get current price
                        current_data = current_prices.get(ticker, {})
                        end_price = current_data.get('current_price')
                        
                        # Validate price data - check for realistic stock prices
                        if (start_price is not None and end_price is not None and 
                            isinstance(start_price, (int, float)) and isinstance(end_price, (int, float)) and
                            start_price > 0 and end_price > 0 and
                            start_price < 10000 and end_price < 10000):  # Reasonable upper bound
                            
                            # Calculate performance metrics
                            abs_change = float(end_price) - float(start_price)
                            pct_change = (abs_change / float(start_price)) * 100 if start_price != 0 else 0.0
                            performance_data[ticker] = {
                                "ticker": ticker.upper(),
                                "first_date": start_date.strftime("%Y-%m-%d"),
                                "last_date": end_date.strftime("%Y-%m-%d"),
                                "first_close": round(float(start_price), 2),
                                "last_close": round(float(end_price), 2),
                                "abs_change": round(abs_change, 2),
                                "pct_change": round(pct_change, 2),
                            }
                            logging.info(f"Successfully retrieved historical price for {ticker}: ${start_price} → ${end_price} ({pct_change:.2f}%)")
                            break  # Success, move to next ticker
                        else:
                            logging.warning(f"Invalid price data for {ticker}: start_price={start_price}, end_price={end_price}")
                            raise ValueError(f"Invalid price data for {ticker}")
                    else:
                        raise ValueError("No JSON found in response")
                        
                except Exception as e:
                    logging.error(f"Attempt {attempt + 1} failed to fetch historical price for {ticker}: {e}")
                    if attempt == max_retries - 1:
                        # Last attempt failed, return error data
                        performance_data[ticker] = {"error": f"Failed after {max_retries} attempts: {str(e)}"}
                    else:
                        # Wait before retrying
                        import time
                        time.sleep(2 ** attempt)  # Exponential backoff
        
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