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

# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

class StockDataService:
    """
    Multi-source stock data service with fallback mechanisms.
    Prioritizes OpenAI web search for reliability, with yfinance as backup.
    """
    
    def __init__(self, openai_client: OpenAI):
        self.client = openai_client
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour cache
        
    def get_current_prices(self, tickers: Tuple[str, ...]) -> Dict[str, Dict[str, Any]]:
        """
        Fetch current stock prices using OpenAI web search.
        Returns: {ticker: {"company_name": str, "current_price": float}}
        """
        if not tickers:
            return {}
        
        tickers_str = ", ".join(tickers)
        today = datetime.now().strftime("%B %d, %Y")
        
        query = f"""
Return ONLY a JSON object (no markdown, no explanation, no prose) with the most recent closing stock prices as of {today} for these companies: {tickers_str}

Format:
{{
    "AAPL": {{"company_name": "Apple Inc.", "current_price": 212.44}},
    "MSFT": {{"company_name": "Microsoft Corporation", "current_price": 420.50}}
}}

Include all requested tickers. Use the most recent closing price available from reliable financial sources.
"""
        
        try:
            response = self.client.responses.create(
                model="gpt-4.1",
                tools=[{"type": "web_search_preview"}],
                input=query
            )
            content = response.output_text
            logging.info(f"OpenAI current prices response: {content[:200]}...")
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                stock_data = json.loads(json_match.group())
                # Ensure all tickers are present
                for ticker in tickers:
                    if ticker not in stock_data:
                        stock_data[ticker] = {'company_name': ticker, 'current_price': None}
                    else:
                        # Ensure company_name is present
                        if 'company_name' not in stock_data[ticker]:
                            stock_data[ticker]['company_name'] = ticker
                return stock_data
            else:
                logging.error("No JSON found in OpenAI current prices response. Full response: %s", content)
                return {ticker: {'company_name': ticker, 'current_price': None} for ticker in tickers}
        except Exception as e:
            logging.error(f"Failed to fetch current prices from OpenAI: {e}")
            return {ticker: {'company_name': ticker, 'current_price': None} for ticker in tickers}
    
    def get_historical_prices(self, tickers: Tuple[str, ...], start_date: pd.Timestamp, end_date: pd.Timestamp) -> Dict[str, Dict[str, Any]]:
        """
        Fetch historical price data using OpenAI web search.
        Returns: {ticker: {"start_price": float, "end_price": float, "start_date": str, "end_date": str}}
        """
        if not tickers:
            return {}

        # Format dates for the query
        start_date_str = start_date.strftime("%B %d, %Y")
        end_date_str = end_date.strftime("%B %d, %Y")
        tickers_str = ", ".join(tickers)
        
        query = f"""Search for historical stock price data for these companies: {tickers_str}

I need the closing prices on {start_date_str} and {end_date_str} to calculate performance.

Return a JSON object with this exact format:
{{
    "AAPL": {{
        "start_date": "2024-01-15",
        "start_price": 185.92,
        "end_date": "2024-01-22", 
        "end_price": 191.56
    }},
    "MSFT": {{
        "start_date": "2024-01-15",
        "start_price": 388.47,
        "end_date": "2024-01-22",
        "end_price": 397.58
    }}
}}

Use the most accurate closing prices available for each date. If exact dates aren't available, use the closest trading day."""
        
        try:
            response = self.client.responses.create(
                model="gpt-4.1",
                tools=[{"type": "web_search_preview"}],
                input=query
            )
            content = response.output_text
            logging.info(f"OpenAI historical data response: {content[:200]}...")
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                historical_data = json.loads(json_match.group())
                performance_data = {}
                for ticker in tickers:
                    if ticker in historical_data:
                        ticker_data = historical_data[ticker]
                        # Extract prices and dates
                        start_price = ticker_data.get('start_price')
                        end_price = ticker_data.get('end_price')
                        start_date_actual = ticker_data.get('start_date')
                        end_date_actual = ticker_data.get('end_date')
                        if start_price is not None and end_price is not None:
                            # Calculate performance metrics
                            abs_change = end_price - start_price
                            pct_change = (abs_change / start_price) * 100 if start_price != 0 else 0.0
                            performance_data[ticker] = {
                                "ticker": ticker.upper(),
                                "first_date": start_date_actual,
                                "last_date": end_date_actual,
                                "first_close": round(start_price, 2),
                                "last_close": round(end_price, 2),
                                "abs_change": round(abs_change, 2),
                                "pct_change": round(pct_change, 2),
                            }
                        else:
                            performance_data[ticker] = {"error": "Missing price data"}
                    else:
                        performance_data[ticker] = {"error": "Ticker not found in response"}
                return performance_data
            else:
                logging.error("No JSON found in OpenAI historical data response")
                return {ticker: {"error": "No data available"} for ticker in tickers}
        except Exception as e:
            logging.error(f"Failed to fetch historical data from OpenAI: {e}")
            return {ticker: {"error": str(e)} for ticker in tickers}
    
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