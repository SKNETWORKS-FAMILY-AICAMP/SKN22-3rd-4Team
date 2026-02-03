"""
미국 시가총액 상위 100대 기업 재무제표 수집 스크립트 (전체 100개)
SEC EDGAR API 직접 호출
"""
import os
import sys
from pathlib import Path
import pandas as pd
import requests
from datetime import datetime
import time
import json

# SEC EDGAR API 설정
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# 미국 시가총액 상위 100대 기업 티커 목록 (2024년 기준)
TOP_100_TICKERS = [
    # 빅테크 (10)
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "TSM", "AVGO",
    # 금융 (10)
    "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "AXP", "SPGI", "BLK",
    # 헬스케어 (10)
    "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY",
    # 소비재 (10)
    "WMT", "PG", "KO", "PEP", "COST", "MCD", "NKE", "DIS", "SBUX", "TGT",
    # 산업재 (10)
    "CAT", "GE", "HON", "UNP", "RTX", "BA", "LMT", "DE", "UPS", "MMM",
    # 에너지 (10)
    "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "KMI",
    # 통신 (5)
    "VZ", "T", "TMUS", "CMCSA", "CHTR",
    # 부동산 (5)
    "PLD", "AMT", "EQIX", "CCI", "SPG",
    # 유틸리티 (5)
    "NEE", "DUK", "SO", "D", "AEP",
    # 기술 (10)
    "ORCL", "CRM", "ADBE", "AMD", "INTC", "QCOM", "TXN", "AMAT", "MU", "LRCX",
    # 반도체/기타 (10)
    "ASML", "NOW", "INTU", "PYPL", "ISRG", "BKNG", "MDLZ", "ADP", "CI", "REGN",
    # 추가 대형주 (10)
    "CVS", "GILD", "VRTX", "AMGN", "ZTS", "SYK", "BDX", "ELV", "HUM", "MCK"
]

# 재무 지표 XBRL 태그
FINANCIAL_TAGS = {
    "Revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "TotalRevenuesAndOtherIncome"],
    "NetIncome": ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
    "TotalAssets": ["Assets"],
    "TotalLiabilities": ["Liabilities"],
    "Equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "OperatingIncome": ["OperatingIncomeLoss"],
    "CashFlow": ["NetCashProvidedByUsedInOperatingActivities"],
    "EPS": ["EarningsPerShareBasic", "EarningsPerShareDiluted"],
}


def get_user_agent():
    """SEC API 요청에 필요한 User-Agent 반환"""
    email = os.getenv("SEC_API_USER_AGENT", "myapp@example.com")
    return f"Mozilla/5.0 (compatible; MyApp/1.0; +{email})"


def get_company_cik_map():
    """SEC에서 회사 티커-CIK 매핑 가져오기"""
    headers = {
        "User-Agent": get_user_agent(),
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(SEC_COMPANY_TICKERS_URL, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        cik_map = {}
        for item in data.values():
            ticker = item.get("ticker", "").upper()
            cik = str(item.get("cik_str", "")).zfill(10)
            title = item.get("title", "")
            cik_map[ticker] = {"cik": cik, "title": title}
        
        return cik_map
    
    except Exception as e:
        print(f"❌ CIK 매핑 가져오기 실패: {e}")
        return {}


def get_company_facts(cik):
    """특정 회사의 재무 데이터 가져오기"""
    headers = {
        "User-Agent": get_user_agent(),
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json"
    }
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    
    except:
        return None


def extract_financial_metric(facts, tag_list, form_type="10-K"):
    """XBRL 데이터에서 특정 재무 지표 추출"""
    if not facts or "facts" not in facts:
        return {}
    
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    
    for tag in tag_list:
        if tag in us_gaap:
            units = us_gaap[tag].get("units", {})
            
            for unit_type in ["USD", "USD/shares"]:
                if unit_type in units:
                    values = units[unit_type]
                    
                    annual_values = {}
                    for v in values:
                        if v.get("form") == form_type and v.get("fy"):
                            fy = v["fy"]
                            val = v.get("val")
                            if fy not in annual_values or v.get("end", "") > annual_values[fy].get("end", ""):
                                annual_values[fy] = {"value": val, "end": v.get("end", "")}
                    
                    if annual_values:
                        return {fy: data["value"] for fy, data in annual_values.items()}
    
    return {}


def collect_company_financials(ticker, cik, company_name):
    """단일 회사의 재무 데이터 수집"""
    facts = get_company_facts(cik)
    
    if not facts:
        return None
    
    financials = {
        "ticker": ticker,
        "company_name": company_name,
        "cik": cik
    }
    
    for metric_name, tags in FINANCIAL_TAGS.items():
        data = extract_financial_metric(facts, tags)
        if data:
            recent_years = sorted(data.keys(), reverse=True)[:5]
            for year in recent_years:
                financials[f"{metric_name}_{year}"] = data[year]
    
    return financials


def collect_all_financials(output_dir="data/processed"):
    """전체 100대 기업 재무 데이터 수집"""
    print("="*60)
    print("🏦 미국 100대 기업 재무제표 수집 시작 (전체)")
    print("="*60)
    
    print("\n📋 SEC 회사 목록 로드 중...")
    cik_map = get_company_cik_map()
    
    if not cik_map:
        print("❌ SEC API 연결 실패")
        return None
    
    print(f"✅ {len(cik_map)}개 회사 정보 로드 완료")
    
    all_financials = []
    success_count = 0
    fail_count = 0
    
    print(f"\n📊 {len(TOP_100_TICKERS)}개 기업 재무 데이터 수집 중...\n")
    
    for i, ticker in enumerate(TOP_100_TICKERS, 1):
        lookup_ticker = ticker.replace("-", "")
        
        if ticker not in cik_map and lookup_ticker not in cik_map:
            print(f"  [{i:3d}/{len(TOP_100_TICKERS)}] {ticker}: ❌ CIK 없음")
            fail_count += 1
            continue
        
        company_info = cik_map.get(ticker) or cik_map.get(lookup_ticker)
        cik = company_info["cik"]
        company_name = company_info["title"]
        
        print(f"  [{i:3d}/{len(TOP_100_TICKERS)}] {ticker}: {company_name[:30]:<30}", end="", flush=True)
        
        try:
            financials = collect_company_financials(ticker, cik, company_name)
            
            if financials and len(financials) > 3:
                all_financials.append(financials)
                print(" ✅")
                success_count += 1
            else:
                print(" ⚠️ 데이터 부족")
                fail_count += 1
        
        except Exception as e:
            print(f" ❌ 오류")
            fail_count += 1
        
        time.sleep(0.12)
    
    print("\n" + "="*60)
    print(f"📊 수집 완료: 성공 {success_count}개, 실패 {fail_count}개")
    print("="*60)
    
    if all_financials:
        df = pd.DataFrame(all_financials)
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        csv_file = output_path / f"top_100_financials_{datetime.now().strftime('%Y%m%d')}.csv"
        df.to_csv(csv_file, index=False, encoding="utf-8-sig")
        print(f"\n💾 저장됨: {csv_file}")
        
        json_file = output_path / f"top_100_financials_{datetime.now().strftime('%Y%m%d')}.json"
        df.to_json(json_file, orient="records", force_ascii=False, indent=2)
        print(f"💾 저장됨: {json_file}")
        
        print(f"\n✅ 총 {len(df)}개 기업 재무 데이터 수집 완료!")
        
        return df
    
    return None


if __name__ == "__main__":
    df = collect_all_financials()
