"""
SEC EDGAR data downloader and processor
Downloads 10-K, 10-Q, and 8-K filings from SEC EDGAR
"""
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import pandas as pd
from sec_edgar_downloader import Downloader

logger = logging.getLogger(__name__)


class SECDataCollector:
    """Collects financial data from SEC EDGAR"""
    
    def __init__(self, user_agent: str, download_dir: Path):
        """
        Initialize SEC data collector
        
        Args:
            user_agent: Email address for SEC API
            download_dir: Directory to save downloaded files
        """
        self.user_agent = user_agent
        self.download_dir = download_dir
        self.downloader = Downloader("MyCompanyName", user_agent, str(download_dir))
        
    def download_company_filings(
        self,
        ticker: str,
        form_types: List[str] = ["10-K", "10-Q", "8-K"],
        limit: Optional[int] = None,
        after_date: Optional[str] = None,
        before_date: Optional[str] = None
    ) -> dict:
        """
        Download filings for a specific company
        
        Args:
            ticker: Company ticker symbol
            form_types: List of form types to download
            limit: Maximum number of filings to download per form type
            after_date: Download filings after this date (YYYY-MM-DD)
            before_date: Download filings before this date (YYYY-MM-DD)
            
        Returns:
            Dictionary with download results
        """
        results = {}
        
        for form_type in form_types:
            try:
                logger.info(f"Downloading {form_type} filings for {ticker}")
                
                num_downloaded = self.downloader.get(
                    form_type,
                    ticker,
                    limit=limit,
                    after=after_date,
                    before=before_date
                )
                
                results[form_type] = {
                    "status": "success",
                    "count": num_downloaded,
                    "ticker": ticker
                }
                
                logger.info(f"Downloaded {num_downloaded} {form_type} filings for {ticker}")
                
            except Exception as e:
                logger.error(f"Error downloading {form_type} for {ticker}: {str(e)}")
                results[form_type] = {
                    "status": "error",
                    "error": str(e),
                    "ticker": ticker
                }
        
        return results
    
    def download_multiple_companies(
        self,
        tickers: List[str],
        form_types: List[str] = ["10-K", "10-Q"],
        limit: int = 5
    ) -> pd.DataFrame:
        """
        Download filings for multiple companies
        
        Args:
            tickers: List of company ticker symbols
            form_types: List of form types to download
            limit: Maximum number of filings per form type per company
            
        Returns:
            DataFrame with download results
        """
        all_results = []
        
        for ticker in tickers:
            results = self.download_company_filings(
                ticker=ticker,
                form_types=form_types,
                limit=limit
            )
            
            for form_type, result in results.items():
                all_results.append({
                    "ticker": ticker,
                    "form_type": form_type,
                    "status": result["status"],
                    "count": result.get("count", 0),
                    "error": result.get("error", None),
                    "timestamp": datetime.now()
                })
        
        return pd.DataFrame(all_results)
    
    def get_company_info(self, ticker: str) -> dict:
        """
        Get company information from SEC
        
        Args:
            ticker: Company ticker symbol
            
        Returns:
            Dictionary with company information
        """
        # This is a placeholder - you would implement actual SEC API calls
        return {
            "ticker": ticker,
            "cik": None,  # Central Index Key
            "company_name": None,
            "sic_code": None,  # Standard Industrial Classification
            "industry": None
        }
