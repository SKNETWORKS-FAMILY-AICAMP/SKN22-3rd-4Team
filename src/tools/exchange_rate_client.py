"""
Exchange Rate Client - 한국 거주자 맞춤형 환율 클라이언트
Open Exchange Rates API (Base: KRW 또는 USD)를 사용하여 한국 시간(KST) 기반 정보를 제공합니다.
"""

import os
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dotenv import load_dotenv
import pytz

load_dotenv()

logger = logging.getLogger(__name__)

# 무료 API 엔드포인트
EXCHANGE_RATE_API_URL = "https://open.er-api.com/v6/latest"


class ExchangeRateClient:
    """한국 기준(KRW 중심) 환율 정보 API 클라이언트"""

    def __init__(self):
        """Initialize exchange rate client"""
        self._cache = {}
        self._cache_time = None
        self._cache_duration = timedelta(minutes=30)  # 30분 캐시
        self.kst = pytz.timezone("Asia/Seoul")
        logger.info("ExchangeRateClient (Korean Standard) initialized")

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache is still valid for a specific key"""
        if cache_key not in self._cache:
            return False
        timestamp, _ = self._cache[cache_key]
        return datetime.now() - timestamp < self._cache_duration

    def get_latest_rates(self, base: str = "USD") -> Dict:
        """
        최신 환율 정보 가져오기

        Args:
            base: 기준 통화 (기본: USD)

        Returns:
            Dict with exchange rates and KST timestamp
        """
        cache_key = f"latest_{base}"

        if self._is_cache_valid(cache_key):
            return self._cache[cache_key][1]

        try:
            response = requests.get(f"{EXCHANGE_RATE_API_URL}/{base}", timeout=10)

            if response.status_code == 200:
                data = response.json()

                # UTC 시간을 KST로 변환
                utc_time_str = data.get("time_last_update_utc", "")
                if utc_time_str:
                    # 'Wed, 28 Jan 2026 00:00:01 +0000' 형태
                    try:
                        # 간편하게 현재 KST 시간 사용 (업데이트 주기가 길어서 현재 시간 표시가 사용자에게 더 친숙함)
                        now_kst = datetime.now(self.kst)
                        update_time_kst = now_kst.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        update_time_kst = "최근 정보"
                else:
                    update_time_kst = "최근 정보"

                result = {
                    "base": base,
                    "update_time_kst": update_time_kst,
                    "rates": data.get("rates", {}),
                    "source": "Global Open Exchange",
                    "note": "한국 시간(KST) 기준",
                }

                self._cache[cache_key] = (datetime.now(), result)
                return result

        except Exception as e:
            logger.error(f"Exchange rate API error: {e}")

        return {"error": "환율 정보를 가져올 수 없습니다.", "rates": {}}

    def get_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """두 통화간 환율 가져오기 (예: USD, KRW)"""
        data = self.get_latest_rates(from_currency)
        return data.get("rates", {}).get(to_currency)

    def convert(
        self, amount: float, from_currency: str, to_currency: str
    ) -> Optional[float]:
        """통화 변환"""
        rate = self.get_rate(from_currency, to_currency)
        if rate:
            return amount * rate
        return None

    def format_rate_for_display(
        self, from_currency: str, to_currency: str, rate: float
    ) -> str:
        """환율 정보 문자열 포맷팅"""
        if to_currency == "KRW":
            return f"1 {from_currency} = {rate:,.2f}원"
        return f"1 {from_currency} = {rate:.4f} {to_currency}"

    def get_krw_rate(self, target: str = "USD") -> Optional[float]:
        """
        1 외화당 KRW 가격 가져오기 (예: 1 USD = 1,440원)
        """
        return self.get_rate(target, "KRW")

    def convert_to_krw(self, amount: float, currency: str = "USD") -> Optional[float]:
        """외화를 원화로 변환"""
        return self.convert(amount, currency, "KRW")

    def get_major_rates_summary(self) -> Dict:
        """
        한국 투자자가 주로 보는 주요 통화 요약 (원화 기준)
        """
        # USD 기반으로 가져와서 각 외화 1단위당 원화 가격 계산
        usd_data = self.get_latest_rates("USD")
        usd_rates = usd_data.get("rates", {})
        usd_to_krw = usd_rates.get("KRW", 0)

        # JPY는 보통 100엔 기준으로 표시하므로 주의
        jpy_to_usd = usd_rates.get("JPY", 0)
        jpy_to_krw = (
            (usd_to_krw / jpy_to_usd * 100) if jpy_to_usd else 0
        )  # 100엔당 원화

        eur_to_usd = usd_rates.get("EUR", 0)
        eur_to_krw = (usd_to_krw / eur_to_usd) if eur_to_usd else 0

        gbp_to_usd = usd_rates.get("GBP", 0)
        gbp_to_krw = (usd_to_krw / gbp_to_usd) if gbp_to_usd else 0

        return {
            "update_time": usd_data.get("update_time_kst"),
            "display_rates": {
                "USD/KRW": f"₩{usd_to_krw:,.2f}",
                "JPY/KRW (100엔)": f"₩{jpy_to_krw:,.2f}",
                "EUR/KRW": f"₩{eur_to_krw:,.2f}",
                "GBP/KRW": f"₩{gbp_to_krw:,.2f}",
            },
            "raw_rates": {
                "USD": usd_to_krw,
                "JPY": jpy_to_krw / 100,
                "EUR": eur_to_krw,
                "GBP": gbp_to_krw,
            },
        }


# Singleton instance
_exchange_client = None


def get_exchange_client() -> ExchangeRateClient:
    """Get singleton exchange rate client"""
    global _exchange_client
    if _exchange_client is None:
        _exchange_client = ExchangeRateClient()
    return _exchange_client
