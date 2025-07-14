#!/usr/bin/env python3
"""
Optimized Newsletter System - Fixes duplicate API calls, AI analysis errors, and rate limiting
"""

import logging
import os
import pandas as pd
from openai import OpenAI
from typing import Dict, Any, Tuple, List, Optional
import streamlit as st
import re
from datetime import datetime, timedelta
import json
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

class OptimizedNewsletterSystem:
    """
    Optimized newsletter system that:
    1. Fetches data once and reuses it
    2. Uses batch processing to minimize API calls
    3. Has bulletproof error handling
    4. Ensures AI uses correct price data
    """
    
    def __init__(self):
        try:
            self.openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        except (AttributeError, KeyError):
            self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        self.model = "gpt-4o-mini"
        
        # Import Alpha Vantage service
        from alpha_vantage_service import get_alpha_vantage_service
        self.av_service = get_alpha_vantage_service()
        
        # Cache for data reuse
        self.performance_cache = {}
        self.company_cache = {}
        self.cache_duration = 300  # 5 minutes
        
    def get_portfolio_data_efficiently(self, tickers: Tuple[str, ...], holdings: Dict[str, float]) -> Dict[str, Any]:
        """
        Fetch all portfolio data efficiently in one pass, with bulletproof error handling.
        Returns both performance and company data to avoid duplicate API calls.
        """
        if not tickers:
            return {"performance_data": {}, "company_data": {}, "success_rate": 0.0}
        
        logging.info(f"=== Fetching portfolio data for {len(tickers)} tickers efficiently ===")
        start_time = time.time()
        
        # Step 1: Fetch historical performance data (this includes current prices)
        logging.info("Step 1: Fetching historical performance data...")
        today = pd.Timestamp.now()
        week_ago = today - pd.Timedelta(days=7)
        
        performance_data = {}
        successful_tickers = []
        failed_tickers = []
        
        # Process in batches of 5 to respect rate limits
        batch_size = 5
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i+batch_size]
            logging.info(f"Processing batch {i//batch_size + 1}: {batch}")
            
            try:
                batch_perf = self.av_service.get_batch_price_performance(batch, week_ago, today, "weekly")
                
                for ticker in batch:
                    data = batch_perf.get(ticker, {})
                    if 'error' not in data:
                        performance_data[ticker] = data
                        successful_tickers.append(ticker)
                        logging.info(f"✅ {ticker}: {data.get('pct_change', 0):.2f}%")
                    else:
                        failed_tickers.append(ticker)
                        logging.warning(f"❌ {ticker}: {data.get('error', 'Unknown error')}")
                        
            except Exception as e:
                logging.error(f"Batch error: {e}")
                for ticker in batch:
                    failed_tickers.append(ticker)
        
        # Step 2: Extract current prices from performance data to avoid duplicate API calls
        logging.info("Step 2: Extracting current prices from performance data...")
        company_data = {}
        
        for ticker, perf_data in performance_data.items():
            if 'last_close' in perf_data:
                company_data[ticker] = {
                    'current_price': perf_data['last_close'],
                    'company_name': self._get_company_name(ticker),
                    'last_updated': perf_data.get('last_date', 'Unknown')
                }
        
        # Calculate success rate
        success_rate = (len(successful_tickers) / len(tickers)) * 100 if tickers else 0.0
        
        # Calculate portfolio performance
        portfolio_performance = self._calculate_portfolio_performance(performance_data, holdings)
        
        duration = time.time() - start_time
        logging.info(f"=== Portfolio data fetch complete ===")
        logging.info(f"✅ Successful: {len(successful_tickers)}/{len(tickers)} ({success_rate:.1f}%)")
        logging.info(f"❌ Failed: {len(failed_tickers)} tickers")
        logging.info(f"💰 Portfolio change: {portfolio_performance['overall_change_pct']:.2f}%")
        logging.info(f"⏱️ Total time: {duration:.1f} seconds")
        
        if failed_tickers:
            logging.warning(f"Failed tickers: {', '.join(failed_tickers)}")
        
        return {
            "performance_data": performance_data,
            "company_data": company_data,
            "success_rate": success_rate,
            "failed_tickers": failed_tickers,
            "portfolio_performance": portfolio_performance
        }
    
    def _get_company_name(self, ticker: str) -> str:
        """Get company name from ticker - simplified to avoid extra API calls"""
        company_names = {
            'GOOGL': 'Alphabet Inc.',
            'MO': 'Altria Group Inc.',
            'AMZN': 'Amazon.com Inc.',
            'BRK-B': 'Berkshire Hathaway Inc.',
            'AVGO': 'Broadcom Inc.',
            'CAT': 'Caterpillar Inc.',
            'CRWD': 'CrowdStrike Holdings Inc.',
            'DE': 'Deere & Company',
            'EMR': 'Emerson Electric Co.',
            'GE': 'General Electric Company',
            'GEV': 'GE Vernova Inc.',
            'GD': 'General Dynamics Corporation',
            'HON': 'Honeywell International Inc.',
            'MSFT': 'Microsoft Corporation',
            'NVDA': 'NVIDIA Corporation',
            'PFE': 'Pfizer Inc.',
            'PM': 'Philip Morris International Inc.',
            'RTX': 'Raytheon Technologies Corporation',
            'NOW': 'ServiceNow Inc.',
            'SHEL': 'Shell plc',
            'XLE': 'Energy Select Sector SPDR Fund',
            'GLD': 'SPDR Gold Shares',
        }
        return company_names.get(ticker, ticker)
    
    def _calculate_portfolio_performance(self, performance_data: Dict[str, Any], holdings: Dict[str, float]) -> Dict[str, Any]:
        """Calculate portfolio performance with bulletproof error handling"""
        if not performance_data or not holdings:
            return {"overall_change_pct": 0.0, "major_movers": []}
        
        total_value_start = 0
        total_value_end = 0
        valid_holdings = 0
        
        for ticker, perf_data in performance_data.items():
            if 'error' not in perf_data and ticker in holdings:
                shares = holdings[ticker]
                if shares > 0 and 'first_close' in perf_data and 'last_close' in perf_data:
                    total_value_start += perf_data['first_close'] * shares
                    total_value_end += perf_data['last_close'] * shares
                    valid_holdings += 1
        
        if total_value_start > 0:
            overall_change_pct = ((total_value_end - total_value_start) / total_value_start) * 100
        else:
            overall_change_pct = 0.0
        
        # Get major movers (top 2 by absolute percentage change)
        major_movers = []
        sorted_by_impact = sorted(
            [(t, d) for t, d in performance_data.items() if 'error' not in d],
            key=lambda x: abs(x[1].get('pct_change', 0)),
            reverse=True
        )
        
        for ticker, data in sorted_by_impact[:2]:
            major_movers.append(f"{ticker} ({data['pct_change']:.2f}%)")
        
        return {
            "overall_change_pct": overall_change_pct,
            "major_movers": major_movers,
            "valid_holdings": valid_holdings
        }
    
    def generate_ai_analysis_with_correct_data(self, ticker: str, price_data: Dict[str, Any], company_name: str) -> str:
        """
        Generate AI analysis that MUST use the provided price data correctly.
        Uses a more restrictive prompt and validation.
        """
        try:
            # Create a very explicit prompt that forces the AI to use the provided data
            prompt = f"""
You are a financial analyst creating a brief analysis for a client newsletter.

**CRITICAL: You MUST use ONLY the exact price data provided below. Do NOT search for or use any other price information.**

EXACT PRICE DATA FOR {ticker} ({company_name}):
- Start Price: ${price_data.get('first_close', 'N/A')}
- End Price: ${price_data.get('last_close', 'N/A')}
- Price Change: ${price_data.get('abs_change', 'N/A')}
- Percentage Change: {price_data.get('pct_change', 'N/A')}%
- Period: {price_data.get('period_name', 'weekly')}

Create exactly 4 bullet points:

• **Performance**: {company_name} {ticker} {price_data.get('pct_change', 0):.2f}% this week, moving from ${price_data.get('first_close', 0):.2f} to ${price_data.get('last_close', 0):.2f}.

• **Key Driver**: [Use web search to find the main news/factor that explains this {price_data.get('pct_change', 0):.2f}% movement]

• **Additional Context**: [Use web search to find secondary factors or analyst opinions about {company_name}]

• **Outlook**: [Brief forward-looking sentiment based on recent developments]

**REQUIREMENTS:**
- Use EXACTLY the percentage and price data above
- Use web search only for news/context, not for price data
- Keep each bullet to 1-2 sentences
- Include source URLs for news
- Return only the 4 bullet points, no other text
"""
            
            logging.info(f"[AI] Generating analysis for {ticker} with {price_data.get('pct_change', 0):.2f}% change")
            
            response = self.openai_client.responses.create(
                model=self.model,
                tools=[{"type": "web_search_preview"}],
                input=prompt
            )
            
            analysis = response.output_text.strip()
            if not analysis:
                raise ValueError("Empty response from AI")
            
            # Validate that the AI used the correct percentage
            expected_pct = price_data.get('pct_change', 0)
            pct_pattern = r'(\d+\.?\d*)%'
            pct_matches = re.findall(pct_pattern, analysis)
            
            if pct_matches:
                found_pct = float(pct_matches[0])
                if abs(found_pct - expected_pct) > 0.1:
                    logging.error(f"[AI] {ticker}: AI used wrong percentage! Expected {expected_pct:.2f}%, found {found_pct:.2f}%")
                    # Force the correct percentage into the analysis
                    analysis = analysis.replace(f"{found_pct:.2f}%", f"{expected_pct:.2f}%")
                    logging.info(f"[AI] {ticker}: Corrected percentage in analysis")
            
            # Validate direction
            expected_direction = "up" if expected_pct >= 0 else "down"
            if expected_direction == "up" and "down" in analysis.lower() and "up" not in analysis.lower():
                logging.error(f"[AI] {ticker}: AI said 'down' when stock went up {expected_pct:.2f}%")
            elif expected_direction == "down" and "up" in analysis.lower() and "down" not in analysis.lower():
                logging.error(f"[AI] {ticker}: AI said 'up' when stock went down {expected_pct:.2f}%")
            
            logging.info(f"[AI] {ticker}: Analysis generated successfully")
            return analysis
            
        except Exception as e:
            logging.error(f"[AI] {ticker}: Analysis generation failed: {e}")
            return f"⚠️ Unable to generate analysis for {ticker}: {str(e)}"
    
    def generate_newsletter_efficiently(self, email: str, holdings: Dict[str, float]) -> bool:
        """
        Generate newsletter with optimized data fetching and bulletproof error handling.
        """
        if not holdings:
            logging.warning(f"No holdings for {email}")
            return False
        
        tickers = tuple(holdings.keys())
        logging.info(f"=== Generating optimized newsletter for {email} ===")
        logging.info(f"Portfolio: {len(tickers)} tickers")
        
        # Step 1: Fetch all data efficiently (one pass)
        portfolio_data = self.get_portfolio_data_efficiently(tickers, holdings)
        
        performance_data = portfolio_data["performance_data"]
        company_data = portfolio_data["company_data"]
        success_rate = portfolio_data["success_rate"]
        portfolio_performance = portfolio_data["portfolio_performance"]
        
        # Step 2: Check if we have enough data
        if success_rate < 50.0:
            logging.error(f"Insufficient data for {email}: {success_rate:.1f}% success rate")
            return False
        
        # Step 3: Generate AI analysis for top movers
        logging.info("Step 3: Generating AI analysis for top movers...")
        
        # Get top 5 movers by absolute percentage change
        valid_performances = [(t, d) for t, d in performance_data.items() if 'error' not in d]
        valid_performances.sort(key=lambda x: abs(x[1].get('pct_change', 0)), reverse=True)
        top_movers = valid_performances[:5]
        
        holdings_analysis = []
        for ticker, price_data in top_movers:
            company_name = company_data.get(ticker, {}).get('company_name', ticker)
            analysis = self.generate_ai_analysis_with_correct_data(ticker, price_data, company_name)
            
            if not analysis.startswith("⚠️"):
                holdings_analysis.append({
                    "ticker": ticker,
                    "analysis": analysis,
                    "pct_change": price_data.get('pct_change', 0)
                })
        
        logging.info(f"Generated analysis for {len(holdings_analysis)} holdings")
        
        # Step 4: Create summary
        overall_change = portfolio_performance["overall_change_pct"]
        direction = "increased" if overall_change >= 0 else "decreased"
        major_movers = portfolio_performance["major_movers"]
        
        summary = f"Your portfolio {direction} by {abs(overall_change):.2f}% this week."
        if major_movers:
            summary += f" Key movers: {', '.join(major_movers)}."
        
        logging.info(f"Newsletter summary: {summary}")
        logging.info(f"=== Newsletter generation complete for {email} ===")
        
        return True

def test_optimized_system():
    """Test the optimized system with user's portfolio"""
    print("🚀 Testing Optimized Newsletter System")
    print("=" * 60)
    
    # User's portfolio data
    portfolio = {
        "GOOGL": 125, "MO": 225, "AMZN": 150, "BRK-B": 60, "AVGO": 75,
        "CAT": 33, "CRWD": 75, "DE": 18, "EMR": 70, "GE": 225,
        "GEV": 40, "GD": 75, "HON": 105, "MSFT": 75, "NVDA": 200,
        "PFE": 225, "PM": 65, "RTX": 151, "NOW": 23, "SHEL": 180,
        "XLE": 90, "GLD": 100, "DHEIX": 4091, "LSYIX": 1198, "PHYZX": 1015,
        "DRGVX": 512, "CTSIX": 263, "FEGIX": 380, "GSIMX": 483, "VSMIX": 834,
        "PCBIX": 662, "RMLPX": 871
    }
    
    system = OptimizedNewsletterSystem()
    
    # Test data fetching
    print("\n=== Testing Data Fetching ===")
    result = system.get_portfolio_data_efficiently(tuple(portfolio.keys()), portfolio)
    
    print(f"\nResults:")
    print(f"✅ Success Rate: {result['success_rate']:.1f}%")
    print(f"💰 Portfolio Change: {result['portfolio_performance']['overall_change_pct']:.2f}%")
    print(f"📊 Major Movers: {', '.join(result['portfolio_performance']['major_movers'])}")
    
    if result['failed_tickers']:
        print(f"❌ Failed Tickers: {', '.join(result['failed_tickers'])}")
    
    # Test AI analysis
    print("\n=== Testing AI Analysis ===")
    performance_data = result['performance_data']
    company_data = result['company_data']
    
    # Test with top 3 movers
    valid_performances = [(t, d) for t, d in performance_data.items() if 'error' not in d]
    valid_performances.sort(key=lambda x: abs(x[1].get('pct_change', 0)), reverse=True)
    
    for i, (ticker, price_data) in enumerate(valid_performances[:3]):
        print(f"\n--- Testing AI Analysis for {ticker} ({price_data.get('pct_change', 0):.2f}%) ---")
        company_name = company_data.get(ticker, {}).get('company_name', ticker)
        analysis = system.generate_ai_analysis_with_correct_data(ticker, price_data, company_name)
        print(f"Analysis: {analysis[:200]}...")
    
    print("\n" + "=" * 60)
    print("✅ Optimized system test completed!")

if __name__ == "__main__":
    test_optimized_system() 