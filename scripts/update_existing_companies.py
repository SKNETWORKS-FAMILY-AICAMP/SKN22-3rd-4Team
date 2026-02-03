"""
기존 기업 데이터 업데이트
DB에 이미 있는 기업들의 누락된 필드를 채웁니다.

업데이트 대상:
- cik: SEC API에서 가져오기
- korean_name: OpenAI API로 번역
- logo_url, website, exchange, market_cap: Finnhub API
- headquarters: 위키피디아 S&P 500 목록에서 가져오기
"""

import os
import sys
import time
import pandas as pd
import requests
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv
from openai import OpenAI

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.supabase_client import SupabaseClient
from src.data.finnhub_client import FinnhubClient

load_dotenv()

# OpenAI 클라이언트
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_existing_companies() -> pd.DataFrame:
    """DB에서 모든 기업 가져오기"""
    try:
        client = SupabaseClient.get_client()
        result = client.table("companies").select("*").execute()
        df = pd.DataFrame(result.data)
        print(f"📊 DB에서 {len(df)}개 기업 로드됨")
        return df
    except Exception as e:
        print(f"❌ 기업 조회 실패: {e}")
        return pd.DataFrame()


def get_cik_map() -> Dict[str, str]:
    """SEC에서 티커-CIK 매핑 가져오기"""
    print("📋 SEC에서 CIK 매핑 로드 중...")

    headers = {
        "User-Agent": os.getenv("SEC_API_USER_AGENT", "researcher@university.edu"),
        "Accept": "application/json",
    }

    try:
        url = "https://www.sec.gov/files/company_tickers.json"
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        cik_map = {}
        for item in data.values():
            ticker = item.get("ticker", "").upper()
            cik = str(item.get("cik_str", "")).zfill(10)
            cik_map[ticker] = cik

        print(f"   {len(cik_map)}개 CIK 매핑 로드됨")
        return cik_map

    except Exception as e:
        print(f"⚠️  CIK 매핑 로드 실패: {e}")
        return {}


def get_sp500_headquarters() -> Dict[str, str]:
    """위키피디아에서 S&P 500 기업 본사 위치 가져오기"""
    print("📋 위키피디아에서 본사 정보 로드 중...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    try:
        # User-Agent 헤더 추가 (403 방지)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        tables = pd.read_html(response.text)
        sp500_table = tables[0]

        hq_map = {}
        for _, row in sp500_table.iterrows():
            ticker = str(row["Symbol"]).replace(".", "-")
            headquarters = row.get("Headquarters Location", "")
            if headquarters:
                hq_map[ticker] = headquarters

        print(f"   {len(hq_map)}개 본사 정보 로드됨")
        return hq_map

    except Exception as e:
        print(f"⚠️  본사 정보 로드 실패: {e}")
        return {}


def translate_batch(company_names: List[str], batch_size: int = 20) -> Dict[str, str]:
    """여러 회사명을 배치로 번역 (API 호출 최소화)"""
    translations = {}

    print(f"📝 {len(company_names)}개 기업 한글 이름 번역 중...")

    for i in range(0, len(company_names), batch_size):
        batch = company_names[i : i + batch_size]
        batch_text = "\n".join([f"{j+1}. {name}" for j, name in enumerate(batch)])

        try:
            response = openai_client.chat.completions.create(
                model=os.getenv("CHAT_MODEL", "gpt-4.1-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": """당신은 미국 기업명을 한글로 번역하는 전문가입니다.
널리 알려진 한글 표기가 있으면 그것을 사용하고, 없으면 발음을 한글로 표기하세요.
각 줄에 번호와 한글 회사명만 반환하세요. 예: "1. 애플""",
                    },
                    {
                        "role": "user",
                        "content": f"다음 미국 기업명들을 한글로 번역하세요:\n{batch_text}",
                    },
                ],
                max_tokens=1000,
                temperature=0.1,
            )

            result = response.choices[0].message.content.strip()
            lines = result.split("\n")

            for j, line in enumerate(lines):
                if j < len(batch):
                    # "1. 애플" 형식에서 한글명 추출
                    if ". " in line:
                        korean_name = line.split(". ", 1)[1].strip()
                    else:
                        korean_name = line.strip()
                    translations[batch[j]] = korean_name

            print(f"   📝 {i+1}~{min(i+batch_size, len(company_names))}개 번역 완료")
            time.sleep(0.5)  # Rate limit

        except Exception as e:
            print(f"   ⚠️ 배치 번역 실패: {e}")

    return translations


def fetch_finnhub_profile(ticker: str, finnhub_client: FinnhubClient) -> Optional[Dict]:
    """Finnhub에서 기업 프로필 가져오기"""
    try:
        profile = finnhub_client.get_company_profile(ticker)
        if profile:
            return {
                "exchange": profile.get("exchange", ""),
                "market_cap": profile.get("marketCapitalization", 0),
                "logo_url": profile.get("logo", ""),
                "website": profile.get("weburl", ""),
            }
        return None
    except:
        return None


def update_companies(
    companies_df: pd.DataFrame, cik_map: Dict, hq_map: Dict, korean_names: Dict
):
    """기업 데이터 업데이트"""
    client = SupabaseClient.get_client()
    finnhub_client = FinnhubClient()

    total = len(companies_df)
    updated_count = 0

    print(f"\n📤 {total}개 기업 업데이트 중...")

    for idx, row in companies_df.iterrows():
        ticker = row["ticker"]
        company_name = row["company_name"]

        # 업데이트할 필드 수집
        updates = {}

        # CIK 업데이트
        if pd.isna(row.get("cik")) or not row.get("cik"):
            cik = cik_map.get(ticker) or cik_map.get(ticker.replace("-", ""))
            if cik:
                updates["cik"] = cik

        # 한글 이름 업데이트
        if pd.isna(row.get("korean_name")) or not row.get("korean_name"):
            korean_name = korean_names.get(company_name)
            if korean_name:
                updates["korean_name"] = korean_name

        # 본사 업데이트
        if pd.isna(row.get("headquarters")) or not row.get("headquarters"):
            hq = hq_map.get(ticker)
            if hq:
                updates["headquarters"] = hq

        # Finnhub 정보 업데이트 (logo_url, website, exchange, market_cap)
        needs_finnhub = (
            (pd.isna(row.get("logo_url")) or not row.get("logo_url"))
            or (pd.isna(row.get("website")) or not row.get("website"))
            or (pd.isna(row.get("exchange")) or not row.get("exchange"))
        )

        if needs_finnhub:
            profile = fetch_finnhub_profile(ticker, finnhub_client)
            if profile:
                if not row.get("logo_url") and profile["logo_url"]:
                    updates["logo_url"] = profile["logo_url"]
                if not row.get("website") and profile["website"]:
                    updates["website"] = profile["website"]
                if not row.get("exchange") and profile["exchange"]:
                    updates["exchange"] = profile["exchange"]
                if (
                    not row.get("market_cap") or row.get("market_cap") == 0
                ) and profile["market_cap"]:
                    updates["market_cap"] = profile["market_cap"]

        # 업데이트 실행
        if updates:
            try:
                result = (
                    client.table("companies")
                    .update(updates)
                    .eq("ticker", ticker)
                    .execute()
                )
                if result.data:
                    updated_count += 1
                    kr_display = (
                        f" ({updates.get('korean_name', '')})"
                        if updates.get("korean_name")
                        else ""
                    )
                    print(
                        f"  ✅ [{updated_count}] {ticker}{kr_display} - 업데이트: {list(updates.keys())}"
                    )
            except Exception as e:
                print(f"  ❌ {ticker} 업데이트 실패: {e}")

        # Rate limit
        if (idx + 1) % 10 == 0:
            time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"✅ 업데이트 완료: {updated_count}개 기업")
    print(f"{'='*60}\n")


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🔄 기존 기업 데이터 업데이트")
    print("=" * 60)

    # 1. 기존 기업 가져오기
    companies_df = get_existing_companies()
    if companies_df.empty:
        print("❌ 기업 데이터가 없습니다.")
        return

    # 2. 업데이트 필요한 기업 확인
    missing_cik = companies_df[
        companies_df["cik"].isna() | (companies_df["cik"] == "")
    ].shape[0]
    missing_korean = companies_df[
        companies_df["korean_name"].isna() | (companies_df["korean_name"] == "")
    ].shape[0]
    missing_hq = companies_df[
        companies_df["headquarters"].isna() | (companies_df["headquarters"] == "")
    ].shape[0]
    missing_logo = companies_df[
        companies_df["logo_url"].isna() | (companies_df["logo_url"] == "")
    ].shape[0]

    print(f"\n📋 업데이트 필요:")
    print(f"   - CIK 없음: {missing_cik}개")
    print(f"   - 한글 이름 없음: {missing_korean}개")
    print(f"   - 본사 정보 없음: {missing_hq}개")
    print(f"   - 로고 URL 없음: {missing_logo}개")

    if (
        missing_cik == 0
        and missing_korean == 0
        and missing_hq == 0
        and missing_logo == 0
    ):
        print("\n✅ 모든 기업 데이터가 완전합니다!")
        return

    # 3. 사용자 확인
    print(f"\n⚠️  업데이트하시겠습니까? (y/n): ", end="")
    confirm = input().strip().lower()

    if confirm != "y":
        print("❌ 작업 취소됨")
        return

    # 4. 데이터 소스 로드
    cik_map = get_cik_map()
    hq_map = get_sp500_headquarters()

    # 5. 한글 이름 번역 (없는 것만)
    companies_needing_korean = companies_df[
        companies_df["korean_name"].isna() | (companies_df["korean_name"] == "")
    ]["company_name"].tolist()

    korean_names = {}
    if companies_needing_korean:
        korean_names = translate_batch(companies_needing_korean)

    # 6. 업데이트 실행
    update_companies(companies_df, cik_map, hq_map, korean_names)

    print("✅ 기존 기업 업데이트 완료!")


if __name__ == "__main__":
    main()
