#!/usr/bin/env python3
"""
Hybrid Finance Service - Alpha Vantage API for reliable financial data
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List, Optional
import pandas as pd
from alpha_vantage_service import AlphaVantageService

# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

class HybridFinanceService:
    """
    Service that uses Alpha Vantage API for reliable financial data.
    """
    
    def __init__(self):
        self.alpha_vantage_service = AlphaVantageService()
        
        # Cache for historical data
        self.historical_cache = {}
        self.cache_duration = 3600  # 1 hour
    
    def get_current_prices(self, tickers: Tuple[str, ...]) -> Dict[str, Dict[str, Any]]:
        """
        Get current prices using Alpha Vantage API (reliable).
        """
        return self.alpha_vantage_service.get_current_prices(tickers)
    
    def get_historical_prices(self, tickers: Tuple[str, ...], start_date: pd.Timestamp, end_date: pd.Timestamp) -> Dict[str, Dict[str, Any]]:
        """
        Get historical prices using Alpha Vantage API.
        """
        return self.alpha_vantage_service.get_historical_prices(tickers, start_date, end_date)
    
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
        return self.alpha_vantage_service.validate_tickers(tickers)

def get_hybrid_finance_service() -> HybridFinanceService:
    """
    Get or create a HybridFinanceService instance.
    """
    if not hasattr(get_hybrid_finance_service, '_instance'):
        get_hybrid_finance_service._instance = HybridFinanceService()
    return get_hybrid_finance_service._instance 