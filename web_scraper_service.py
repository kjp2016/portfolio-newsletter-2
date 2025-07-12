"""
Web Scraper Service - Extract financial data from web sources and parse with OpenAI
Provides reliable stock/mutual fund data by scraping multiple sources and using AI to structure the data.
"""

import logging
import json
import time
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List, Optional
import pandas as pd
from openai import OpenAI
import streamlit as st
import requests
from bs4 import BeautifulSoup
import urllib.parse

# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

class WebScraperService:
    """
    Service for fetching stock and mutual fund data using web scraping and OpenAI parsing.
    """
    
    def __init__(self, openai_client: OpenAI):
        self.client = openai_client
        
        # Rate limiting settings for web scraping
        self.calls_per_minute = 30  # 1 call per 2 seconds (reasonable)
        self.calls_per_second = 0.5  # 1 call per 2 seconds
        self.last_call_time = 0
        self.call_count = 0
        self.last_reset_time = time.time()
        
        # Cache for current prices to avoid duplicate calls
        self.price_cache = {}
        self.cache_duration = 300  # 5 minutes
        
        # Cache for historical data parsing to reduce OpenAI calls
        self.historical_cache = {}
        self.historical_cache_duration = 3600  # 1 hour
        
        # User agents to avoid being blocked
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
    
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
    
    def _make_web_request(self, url: str) -> Optional[str]:
        """Make a rate-limited web request with proper headers."""
        self._rate_limit()
        
        headers = {
            'User-Agent': self.user_agents[self.call_count % len(self.user_agents)],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.text
            else:
                logging.error(f"HTTP {response.status_code} for {url}")
                return None
        except Exception as e:
            logging.error(f"Request failed for {url}: {e}")
            return None
    
    def _scrape_google_finance(self, ticker: str) -> Optional[str]:
        """Scrape current price from Google Finance."""
        try:
            # Try different URL formats for different security types
            urls = [
                f"https://www.google.com/finance/quote/{ticker}:MUTF",
                f"https://www.google.com/finance/quote/{ticker}:NASDAQ",
                f"https://www.google.com/finance/quote/{ticker}:NYSE",
                f"https://www.google.com/finance/quote/{ticker}"
            ]
            
            for url in urls:
                html = self._make_web_request(url)
                if html and "price" in html.lower():
                    return html
            
            return None
        except Exception as e:
            logging.error(f"Failed to scrape Google Finance for {ticker}: {e}")
            return None
    
    def _scrape_yahoo_finance(self, ticker: str) -> Optional[str]:
        """Scrape current price from Yahoo Finance."""
        try:
            url = f"https://finance.yahoo.com/quote/{ticker}"
            return self._make_web_request(url)
        except Exception as e:
            logging.error(f"Failed to scrape Yahoo Finance for {ticker}: {e}")
            return None
    
    def _scrape_ft_historical(self, ticker: str) -> Optional[str]:
        """Scrape historical data from Financial Times."""
        try:
            # Try equities first (for stocks), then funds (for mutual funds)
            urls = [
                f"https://markets.ft.com/data/equities/tearsheet/historical?s={ticker}",
                f"https://markets.ft.com/data/funds/tearsheet/historical?s={ticker}"
            ]
            
            for url in urls:
                html = self._make_web_request(url)
                if html and ("historical" in html.lower() or "price" in html.lower()):
                    return html
            
            return None
        except Exception as e:
            logging.error(f"Failed to scrape FT for {ticker}: {e}")
            return None
    
    def _scrape_yahoo_historical(self, ticker: str) -> Optional[str]:
        """Scrape historical data from Yahoo Finance."""
        try:
            # Yahoo Finance historical URLs often return 404, so try the main quote page
            # which usually contains some historical data
            url = f"https://finance.yahoo.com/quote/{ticker}"
            html = self._make_web_request(url)
            if html and ("price" in html.lower() or "close" in html.lower()):
                return html
            
            return None
        except Exception as e:
            logging.error(f"Failed to scrape Yahoo historical for {ticker}: {e}")
            return None
    
    def _scrape_nasdaq_historical(self, ticker: str) -> Optional[str]:
        """Scrape historical data from NASDAQ."""
        try:
            url = f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}/historical"
            html = self._make_web_request(url)
            if html and ("Historical Data" in html or "Close" in html or "Date" in html):
                return html
            return None
        except Exception as e:
            logging.error(f"Failed to scrape NASDAQ historical for {ticker}: {e}")
            return None

    def _scrape_wsj_historical(self, ticker: str) -> Optional[str]:
        """Scrape historical data from Wall Street Journal."""
        try:
            url = f"https://www.wsj.com/market-data/quotes/{ticker}/historical-prices"
            html = self._make_web_request(url)
            if html and ("Historical Prices" in html or "Close" in html or "Date" in html):
                return html
            return None
        except Exception as e:
            logging.error(f"Failed to scrape WSJ historical for {ticker}: {e}")
            return None
    
    def _parse_current_price_with_openai(self, ticker: str, html_content: str, source: str) -> Optional[Dict[str, Any]]:
        """Use OpenAI to parse current price from cleaned visible text."""
        try:
            # Clean the HTML with BeautifulSoup first
            soup = BeautifulSoup(html_content, 'html.parser')
            for script in soup(["script", "style"]):
                script.decompose()
            visible_text = soup.get_text(separator="\n", strip=True)
            visible_text = '\n'.join([line for line in visible_text.splitlines() if line.strip()])

            # Fallback price extraction
            fallback_price = self._extract_price_with_soup(html_content, source)

            prompt = f"""
You are a financial data parser. Extract the current price and company name from the following visible text from {source}.

TICKER: {ticker}
SOURCE: {source}

VISIBLE TEXT:
{visible_text[:6000]}

INSTRUCTIONS:
1. Look for the current stock/mutual fund price (usually displayed prominently)
2. Find the company/fund name
3. Return ONLY a JSON object with this exact format:
{{"price": "123.45", "name": "Company Name", "source": "{source}"}}

CRITICAL OUTPUT REQUIREMENTS:
- Return ONLY the JSON object, no introduction, explanation, or other text
- Do NOT include markdown formatting, backticks, or code blocks
- Do NOT add any text before or after the JSON
- The price should be a number without dollar signs (e.g., "123.45" not "$123.45")
- If you cannot find the price, return: {{"price": null, "name": "{ticker}", "source": "{source}"}}
- Ensure the JSON is valid and properly formatted

EXAMPLE OUTPUT:
{{"price": "209.19", "name": "Apple Inc", "source": "{source}"}}
"""

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )
            response_text = response.choices[0].message.content
            if response_text is None:
                logging.warning(f"OpenAI returned None content for {ticker}")
                return None
            response_text = response_text.strip()

            # Try to extract JSON from response with improved parsing
            def extract_and_clean_json(text):
                """Extract JSON from text and clean it up."""
                # Remove any markdown formatting
                text = re.sub(r'```json\s*', '', text)
                text = re.sub(r'```\s*', '', text)
                text = text.strip()
                
                # Try to find JSON object
                json_match = re.search(r'\{[^}]*"price"[^}]*\}', text)
                if json_match:
                    json_str = json_match.group()
                    try:
                        data = json.loads(json_str)
                        return data
                    except json.JSONDecodeError:
                        pass
                
                # If no match found, try to parse the entire text as JSON
                try:
                    data = json.loads(text)
                    return data
                except json.JSONDecodeError:
                    return None
            
            parsed_data = extract_and_clean_json(response_text)
            if parsed_data:
                price_str = parsed_data.get("price")
                name = parsed_data.get("name", ticker)
                
                if price_str and price_str != "null":
                    # Clean the price string (remove dollar signs, commas, etc.)
                    price_str = str(price_str).replace('$', '').replace(',', '').strip()
                    try:
                        current_price = float(price_str)
                        return {
                            'company_name': name,
                            'current_price': current_price,
                            'source': source
                        }
                    except ValueError as e:
                        logging.warning(f"Failed to convert price '{price_str}' to float for {ticker}: {e}")
            else:
                logging.warning(f"Could not extract valid JSON from OpenAI response for {ticker}")

            # If OpenAI parsing failed, try fallback
            if fallback_price:
                logging.info(f"Using fallback price extraction for {ticker}: ${fallback_price}")
                return {
                    'company_name': ticker,
                    'current_price': fallback_price,
                    'source': f"{source} (fallback)"
                }

            logging.warning(f"Could not parse price from {source} for {ticker}")
            return None
        except Exception as e:
            logging.error(f"OpenAI parsing failed for {ticker} from {source}: {e}")
            return None
    
    def _extract_price_with_soup(self, html_content: str, source: str) -> Optional[float]:
        """Extract price using BeautifulSoup as a fallback method."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Look for price patterns
            price_patterns = [
                r'\$(\d+\.\d{2})',  # $22.59
                r'(\d+\.\d{2})',    # 22.59
                r'(\d+,\d+\.\d{2})', # 1,234.56
            ]
            
            for pattern in price_patterns:
                matches = re.findall(pattern, text)
                if matches:
                    # Convert to float and return the first reasonable price
                    for match in matches:
                        try:
                            price = float(match.replace(',', ''))
                            if 0.01 <= price <= 10000:  # Reasonable price range
                                return price
                        except ValueError:
                            continue
            
            return None
            
        except Exception as e:
            logging.error(f"BeautifulSoup extraction failed: {e}")
            return None
    
    def _parse_historical_data_with_openai(self, ticker: str, html_content: str, source: str, start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
        """Use OpenAI to parse historical data from cleaned visible text."""
        try:
            # Check cache first
            cache_key = f"{ticker}_{source}_{start_date}_{end_date}"
            current_time = time.time()
            
            if cache_key in self.historical_cache:
                cache_time, cache_data = self.historical_cache[cache_key]
                if current_time - cache_time < self.historical_cache_duration:
                    logging.info(f"Using cached historical data for {ticker} from {source}")
                    return cache_data
            
            # Clean the HTML with BeautifulSoup first
            soup = BeautifulSoup(html_content, 'html.parser')
            for script in soup(["script", "style"]):
                script.decompose()
            visible_text = soup.get_text(separator="\n", strip=True)
            visible_text = '\n'.join([line for line in visible_text.splitlines() if line.strip()])

            prompt = f"""
You are a financial data parser. Extract historical price data from the following visible text from {source}.

TICKER: {ticker}
SOURCE: {source}
START DATE: {start_date}
END DATE: {end_date}

VISIBLE TEXT:
{visible_text[:8000]}

INSTRUCTIONS:
1. Look for any price data, charts, or financial information
2. Try to find current price and any historical price information
3. If you can't find exact dates, look for recent price changes or performance data
4. Return ONLY a JSON object with this exact format:
{{"start_price": "123.45", "end_price": "124.56", "start_date": "{start_date}", "end_date": "{end_date}", "source": "{source}"}}

CRITICAL OUTPUT REQUIREMENTS:
- Return ONLY the JSON object, no introduction, explanation, or other text
- Do NOT include markdown formatting, backticks, or code blocks
- Do NOT add any text before or after the JSON
- The prices should be numbers without dollar signs (e.g., "123.45" not "$123.45")
- If you cannot find the prices, return: {{"start_price": null, "end_price": null, "source": "{source}"}}
- Ensure the JSON is valid and properly formatted

EXAMPLE OUTPUT:
{{"start_price": "22.54", "end_price": "22.59", "start_date": "{start_date}", "end_date": "{end_date}", "source": "{source}"}}
"""

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )
            
            response_text = response.choices[0].message.content
            if response_text is None:
                logging.warning(f"OpenAI returned None content for {ticker}")
                return None
            response_text = response_text.strip()
            
            # Try to extract JSON from response with improved parsing
            def extract_and_clean_json(text):
                """Extract JSON from text and clean it up."""
                # Remove any markdown formatting
                text = re.sub(r'```json\s*', '', text)
                text = re.sub(r'```\s*', '', text)
                text = text.strip()
                
                # Try to find JSON object
                json_match = re.search(r'\{[^}]*"start_price"[^}]*\}', text)
                if json_match:
                    json_str = json_match.group()
                    try:
                        data = json.loads(json_str)
                        return data
                    except json.JSONDecodeError:
                        pass
                
                # If no match found, try to parse the entire text as JSON
                try:
                    data = json.loads(text)
                    return data
                except json.JSONDecodeError:
                    return None
            
            parsed_data = extract_and_clean_json(response_text)
            if parsed_data:
                start_price_str = parsed_data.get("start_price")
                end_price_str = parsed_data.get("end_price")
                
                if start_price_str and end_price_str and start_price_str != "null" and end_price_str != "null":
                    # Clean the price strings (remove dollar signs, commas, etc.)
                    start_price_str = str(start_price_str).replace('$', '').replace(',', '').strip()
                    end_price_str = str(end_price_str).replace('$', '').replace(',', '').strip()
                    
                    try:
                        start_price = float(start_price_str)
                        end_price = float(end_price_str)
                        
                        # Calculate performance metrics
                        abs_change = end_price - start_price
                        pct_change = (abs_change / start_price) * 100 if start_price != 0 else 0.0
                        
                        result = {
                            "ticker": ticker.upper(),
                            "first_date": start_date,
                            "last_date": end_date,
                            "first_close": round(start_price, 2),
                            "last_close": round(end_price, 2),
                            "abs_change": round(abs_change, 2),
                            "pct_change": round(pct_change, 2),
                            "source": source
                        }
                        
                        # Cache the result
                        self.historical_cache[cache_key] = (current_time, result)
                        return result
                        
                    except ValueError as e:
                        logging.warning(f"Failed to convert prices '{start_price_str}' or '{end_price_str}' to float for {ticker}: {e}")
            else:
                logging.warning(f"Could not extract valid JSON from OpenAI response for {ticker}")
            
            # Fallback: Try to extract any price information from the visible text
            logging.info(f"Trying fallback price extraction for {ticker} from {source}")
            fallback_price = self._extract_fallback_historical_price(visible_text, ticker, source)
            if fallback_price:
                return fallback_price
            
            logging.warning(f"Could not parse historical data from {source} for {ticker}")
            return None
            
        except Exception as e:
            logging.error(f"OpenAI historical parsing failed for {ticker} from {source}: {e}")
            return None
    
    def _extract_fallback_historical_price(self, visible_text: str, ticker: str, source: str) -> Optional[Dict[str, Any]]:
        """Fallback method to extract price information when OpenAI parsing fails."""
        try:
            # Look for price patterns in the text
            price_patterns = [
                r'\$(\d+\.?\d*)',  # $123.45
                r'(\d+\.?\d*)\s*USD',  # 123.45 USD
                r'(\d+\.?\d*)\s*dollars',  # 123.45 dollars
                r'price[:\s]*(\d+\.?\d*)',  # price: 123.45
                r'close[:\s]*(\d+\.?\d*)',  # close: 123.45
            ]
            
            prices = []
            for pattern in price_patterns:
                matches = re.findall(pattern, visible_text, re.IGNORECASE)
                for match in matches:
                    try:
                        price = float(match)
                        if 1.0 <= price <= 10000.0:  # Reasonable price range
                            prices.append(price)
                    except ValueError:
                        continue
            
            if len(prices) >= 2:
                # Use the first two prices found as start and end
                start_price = min(prices)
                end_price = max(prices)
                
                # Calculate performance metrics
                abs_change = end_price - start_price
                pct_change = (abs_change / start_price) * 100 if start_price != 0 else 0.0
                
                # Use today's date as end date, 7 days ago as start date
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                
                return {
                    "ticker": ticker.upper(),
                    "first_date": start_date,
                    "last_date": end_date,
                    "first_close": round(start_price, 2),
                    "last_close": round(end_price, 2),
                    "abs_change": round(abs_change, 2),
                    "pct_change": round(pct_change, 2),
                    "source": f"{source} (fallback)"
                }
            
            return None
            
        except Exception as e:
            logging.error(f"Fallback price extraction failed for {ticker}: {e}")
            return None
    
    def get_current_prices(self, tickers: Tuple[str, ...]) -> Dict[str, Dict[str, Any]]:
        """
        Fetch current stock prices using web scraping and OpenAI parsing.
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
            
            logging.info(f"Fetching current price for {ticker} using web scraping...")
            
            # Try multiple sources
            sources = [
                ("Google Finance", lambda: self._scrape_google_finance(ticker)),
                ("Yahoo Finance", lambda: self._scrape_yahoo_finance(ticker))
            ]
            
            price_found = False
            for source_name, scrape_func in sources:
                try:
                    html_content = scrape_func()
                    if html_content:
                        parsed_data = self._parse_current_price_with_openai(ticker, html_content, source_name)
                        if parsed_data and parsed_data.get('current_price'):
                            stock_data[ticker] = parsed_data
                            self.price_cache[ticker] = (current_time, parsed_data)
                            logging.info(f"Successfully retrieved current price for {ticker} from {source_name}: ${parsed_data['current_price']}")
                            price_found = True
                            break
                except Exception as e:
                    logging.error(f"Failed to get price from {source_name} for {ticker}: {e}")
                    continue
            
            if not price_found:
                logging.warning(f"No valid current price found for {ticker}")
                stock_data[ticker] = {'company_name': ticker, 'current_price': None, 'source': 'None'}
        
        valid_count = sum(1 for data in stock_data.values() 
                         if data.get('current_price') is not None and data.get('current_price') > 0)
        logging.info(f"Successfully retrieved current prices for {valid_count}/{len(tickers)} tickers")
        return stock_data
    
    def get_historical_prices(self, tickers: Tuple[str, ...], start_date: pd.Timestamp, end_date: pd.Timestamp) -> Dict[str, Dict[str, Any]]:
        """
        Fetch historical price data using web scraping and OpenAI parsing.
        """
        if not tickers:
            return {}
        
        performance_data = {}
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        for ticker in tickers:
            logging.info(f"Fetching historical price for {ticker} using web scraping...")
            
            # Try multiple sources for historical data (prioritize working ones)
            sources = [
                ("Financial Times", lambda: self._scrape_ft_historical(ticker)),  # Works well for mutual funds
                ("Yahoo Finance", lambda: self._scrape_yahoo_historical(ticker)),  # Works for some stocks
                ("NASDAQ", lambda: self._scrape_nasdaq_historical(ticker)),  # Fallback
            ]
            
            data_found = False
            for source_name, scrape_func in sources:
                try:
                    html_content = scrape_func()
                    if html_content:
                        parsed_data = self._parse_historical_data_with_openai(
                            ticker, html_content, source_name, start_date_str, end_date_str
                        )
                        if parsed_data and parsed_data.get('first_close'):
                            performance_data[ticker] = parsed_data
                            logging.info(f"Successfully retrieved historical price for {ticker} from {source_name}: ${parsed_data['first_close']} → ${parsed_data['last_close']} ({parsed_data['pct_change']:.2f}%)")
                            data_found = True
                            break
                except Exception as e:
                    logging.error(f"Failed to get historical data from {source_name} for {ticker}: {e}")
                    continue
            
            if not data_found:
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

def get_web_scraper_service() -> WebScraperService:
    """
    Get or create a WebScraperService instance with proper initialization.
    """
    if 'web_scraper_service' not in st.session_state:
        # Initialize with OpenAI client
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        st.session_state['web_scraper_service'] = WebScraperService(client)
    
    return st.session_state['web_scraper_service'] 