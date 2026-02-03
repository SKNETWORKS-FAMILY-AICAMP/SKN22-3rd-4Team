"""
Seeking Alpha API 클라이언트
RapidAPI를 통해 실시간 주가 정보를 가져옵니다.
"""
import os
import requests
from typing import Optional, Dict, List
import pandas as pd
from dotenv import load_dotenv

load_dotenv()


class SeekingAlphaClient:
    """Seeking Alpha API 클라이언트 (RapidAPI)"""
    
    BASE_URL = "https://seeking-alpha.p.rapidapi.com"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("RAPIDAPI_KEY")
        
        if not self.api_key:
            raise ValueError("RAPIDAPI_KEY가 설정되어야 합니다.")
        
        self.headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "seeking-alpha.p.rapidapi.com"
        }
    
    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """API 요청 실행"""
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params or {})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API 요청 오류: {e}")
            return {}
    
    def get_summary(self, ticker: str) -> dict:
        """주식 요약 정보 조회"""
        endpoint = "symbols/get-summary"
        params = {"symbols": ticker}
        return self._make_request(endpoint, params)
    
    def get_quote(self, ticker: str) -> dict:
        """실시간 주가 조회"""
        endpoint = "symbols/get-chart"
        params = {"symbol": ticker, "period": "1D"}
        return self._make_request(endpoint, params)
    
    def get_profile(self, ticker: str) -> dict:
        """기업 프로필 조회"""
        endpoint = "symbols/get-profile"
        params = {"symbols": ticker}
        return self._make_request(endpoint, params)
    
    def get_metrics(self, ticker: str) -> dict:
        """주요 재무 지표 조회"""
        endpoint = "symbols/get-metrics"
        params = {"symbols": ticker}
        return self._make_request(endpoint, params)
    
    def get_peers(self, ticker: str) -> dict:
        """경쟁사 목록 조회"""
        endpoint = "symbols/get-peers"
        params = {"symbol": ticker}
        return self._make_request(endpoint, params)
    
    def get_ratings(self, ticker: str) -> dict:
        """애널리스트 평점 조회"""
        endpoint = "symbols/get-ratings"
        params = {"symbol": ticker}
        return self._make_request(endpoint, params)
    
    def get_news(self, ticker: str, limit: int = 10) -> List[dict]:
        """관련 뉴스 조회"""
        endpoint = "news/v2/list-by-symbol"
        params = {"id": ticker, "size": limit}
        return self._make_request(endpoint, params)
    
    def get_price_data(self, ticker: str) -> dict:
        """가격 데이터 종합 조회 (차트 데이터에서 최신 가격 추출)"""
        # 차트 데이터에서 최신 가격 가져오기
        chart = self.get_quote(ticker)
        
        if not chart or "attributes" not in chart:
            return {}
        
        attributes = chart.get("attributes", {})
        
        if not attributes:
            return {}
        
        # 가장 최근 시간의 데이터 추출
        latest_time = max(attributes.keys()) if attributes else None
        
        if not latest_time:
            return {}
        
        latest_data = attributes[latest_time]
        
        # summary에서 추가 지표 가져오기
        summary = self.get_summary(ticker)
        summary_attrs = {}
        if summary and "data" in summary and summary["data"]:
            summary_attrs = summary["data"][0].get("attributes", {})
        
        return {
            "ticker": ticker,
            "close": latest_data.get("close"),
            "open": latest_data.get("open"),
            "high": latest_data.get("high"),
            "low": latest_data.get("low"),
            "volume": latest_data.get("volume"),
            "pe_ratio": summary_attrs.get("lastClosePriceEarningsRatio"),
            "pe_forward": summary_attrs.get("peRatioFwd"),
            "eps": summary_attrs.get("dilutedEpsExclExtraItmes"),
            "eps_estimate": summary_attrs.get("estimateEps"),
            "last_updated": latest_time,
        }


def get_stock_prices(tickers: List[str]) -> pd.DataFrame:
    """여러 주식의 가격 정보 조회"""
    try:
        client = SeekingAlphaClient()
        
        results = []
        for ticker in tickers:
            data = client.get_price_data(ticker)
            if data:
                results.append(data)
        
        return pd.DataFrame(results)
    
    except Exception as e:
        print(f"주가 조회 오류: {e}")
        return pd.DataFrame()


def get_stock_quote(ticker: str) -> dict:
    """단일 주식 시세 조회"""
    try:
        client = SeekingAlphaClient()
        return client.get_price_data(ticker)
    except Exception as e:
        print(f"주가 조회 오류: {e}")
        return {}


# 테스트
if __name__ == "__main__":
    # API 키 확인
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        print("⚠️ RAPIDAPI_KEY가 .env 파일에 설정되어야 합니다.")
        print("RapidAPI에서 키 발급: https://rapidapi.com/apidojo/api/seeking-alpha")
    else:
        print("✅ RAPIDAPI_KEY 설정됨")
        
        # 테스트 조회
        client = SeekingAlphaClient()
        
        print("\n📊 Apple 주가 조회 중...")
        data = client.get_price_data("AAPL")
        
        if data:
            print(f"  기업명: {data.get('company_name')}")
            print(f"  현재가: ${data.get('close')}")
            print(f"  변동: {data.get('change_percent')}%")
            print(f"  시가총액: ${data.get('market_cap')}")
        else:
            print("  데이터를 가져올 수 없습니다.")
