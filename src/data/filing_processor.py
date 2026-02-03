"""
Process and parse SEC filings into structured data
"""
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class FilingProcessor:
    """Process SEC filings and extract structured data"""
    
    def __init__(self):
        self.financial_keywords = [
            "revenue", "net income", "total assets", "total liabilities",
            "cash flow", "earnings per share", "operating income"
        ]
    
    def parse_10k(self, file_path: Path) -> Dict:
        """
        Parse 10-K filing and extract key information
        
        Args:
            file_path: Path to the 10-K filing
            
        Returns:
            Dictionary with extracted data
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            return {
                "file_path": str(file_path),
                "text_content": soup.get_text(),
                "tables": self._extract_tables(soup),
                "sections": self._extract_sections(soup),
                "financial_data": self._extract_financial_data(soup)
            }
            
        except Exception as e:
            logger.error(f"Error parsing 10-K file {file_path}: {str(e)}")
            return {}
    
    def parse_10q(self, file_path: Path) -> Dict:
        """
        Parse 10-Q filing and extract key information
        
        Args:
            file_path: Path to the 10-Q filing
            
        Returns:
            Dictionary with extracted data
        """
        # Similar to parse_10k but for quarterly reports
        return self.parse_10k(file_path)  # Simplified for now
    
    def _extract_tables(self, soup: BeautifulSoup) -> List[pd.DataFrame]:
        """Extract all tables from the filing"""
        tables = []
        
        for table in soup.find_all('table'):
            try:
                df = pd.read_html(str(table))[0]
                tables.append(df)
            except Exception as e:
                logger.debug(f"Could not parse table: {str(e)}")
        
        return tables
    
    def _extract_sections(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        Extract major sections from the filing
        Standard 10-K sections include:
        - Item 1: Business
        - Item 1A: Risk Factors
        - Item 7: MD&A
        - Item 8: Financial Statements
        """
        sections = {}
        text = soup.get_text()
        
        # Common section patterns
        section_patterns = {
            "business": r"ITEM\s+1\.?\s+BUSINESS",
            "risk_factors": r"ITEM\s+1A\.?\s+RISK\s+FACTORS",
            "mda": r"ITEM\s+7\.?\s+MANAGEMENT'?S\s+DISCUSSION",
            "financial_statements": r"ITEM\s+8\.?\s+FINANCIAL\s+STATEMENTS"
        }
        
        for section_name, pattern in section_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                sections[section_name] = {
                    "start_position": match.start(),
                    "title": match.group()
                }
        
        return sections
    
    def _extract_financial_data(self, soup: BeautifulSoup) -> Dict:
        """Extract specific financial metrics"""
        financial_data = {}
        text = soup.get_text().lower()
        
        # Simple keyword-based extraction
        for keyword in self.financial_keywords:
            if keyword in text:
                # Find context around the keyword
                pattern = rf"{keyword}[:\s]+\$?\s*([\d,]+\.?\d*)"
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    financial_data[keyword] = matches
        
        return financial_data
    
    def extract_text_chunks(
        self,
        file_path: Path,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> List[Dict]:
        """
        Extract text chunks from filing for RAG processing
        
        Args:
            file_path: Path to the filing
            chunk_size: Size of each text chunk
            chunk_overlap: Overlap between chunks
            
        Returns:
            List of text chunks with metadata
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            text = soup.get_text()
            
            # Clean text
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()
            
            chunks = []
            start = 0
            
            while start < len(text):
                end = start + chunk_size
                chunk_text = text[start:end]
                
                chunks.append({
                    "text": chunk_text,
                    "start_pos": start,
                    "end_pos": end,
                    "file_path": str(file_path),
                    "chunk_id": len(chunks)
                })
                
                start += chunk_size - chunk_overlap
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error extracting chunks from {file_path}: {str(e)}")
            return []
