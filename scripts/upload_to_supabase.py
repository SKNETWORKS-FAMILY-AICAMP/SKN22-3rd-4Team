"""
Supabase 데이터베이스에 재무제표 데이터 업로드

SEC EDGAR에서 수집한 100대 기업 재무제표를 Supabase에 저장합니다.
"""
import os
import sys
from pathlib import Path
import pandas as pd
import json
from datetime import datetime
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# Supabase 클라이언트
from supabase import create_client, Client

# 설정
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# 데이터 파일 경로
DATA_DIR = Path(__file__).parent.parent / "data" / "processed"


def get_supabase_client() -> Client:
    """Supabase 클라이언트 생성"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL과 SUPABASE_KEY가 .env 파일에 설정되어야 합니다.")
    
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def load_financial_data() -> pd.DataFrame:
    """수집된 재무 데이터 로드"""
    # 최신 CSV 파일 찾기
    csv_files = list(DATA_DIR.glob("top_100_financials_*.csv"))
    
    if not csv_files:
        raise FileNotFoundError("재무 데이터 파일을 찾을 수 없습니다. 먼저 collect_top100_financials.py를 실행하세요.")
    
    latest_file = max(csv_files, key=lambda x: x.stat().st_mtime)
    print(f"📂 데이터 파일 로드: {latest_file}")
    
    return pd.read_csv(latest_file)


def upsert_companies(supabase: Client, df: pd.DataFrame):
    """companies 테이블에 기업 정보 업로드"""
    print("\n📝 기업 정보 업로드 중...")
    
    companies_data = []
    for _, row in df.iterrows():
        company = {
            "ticker": row["ticker"],
            "company_name": row["company_name"],
            "cik": row["cik"] if pd.notna(row.get("cik")) else None,
        }
        companies_data.append(company)
    
    # Upsert (있으면 업데이트, 없으면 삽입)
    try:
        result = supabase.table("companies").upsert(
            companies_data,
            on_conflict="ticker"
        ).execute()
        print(f"  ✅ {len(companies_data)}개 기업 정보 저장 완료")
        return result.data
    except Exception as e:
        print(f"  ❌ 기업 정보 저장 실패: {e}")
        return []


def get_company_id_map(supabase: Client) -> dict:
    """ticker -> company_id 매핑 조회"""
    result = supabase.table("companies").select("id, ticker").execute()
    return {row["ticker"]: row["id"] for row in result.data}


def extract_annual_data(df: pd.DataFrame) -> list:
    """DataFrame에서 연간 재무 데이터 추출"""
    annual_data = []
    
    # 2020-2025년 데이터 추출
    years = range(2020, 2026)
    
    for _, row in df.iterrows():
        ticker = row["ticker"]
        
        for year in years:
            record = {
                "ticker": ticker,
                "fiscal_year": year,
            }
            
            # 각 재무 지표 추출
            revenue_col = f"Revenue_{year}"
            net_income_col = f"NetIncome_{year}"
            assets_col = f"TotalAssets_{year}"
            liabilities_col = f"TotalLiabilities_{year}"
            equity_col = f"Equity_{year}"
            operating_col = f"OperatingIncome_{year}"
            cashflow_col = f"CashFlow_{year}"
            eps_col = f"EPS_{year}"
            
            # 값이 있는 경우만 추가
            has_data = False
            
            if revenue_col in df.columns and pd.notna(row.get(revenue_col)):
                record["revenue"] = float(row[revenue_col])
                has_data = True
            
            if net_income_col in df.columns and pd.notna(row.get(net_income_col)):
                record["net_income"] = float(row[net_income_col])
                has_data = True
            
            if assets_col in df.columns and pd.notna(row.get(assets_col)):
                record["total_assets"] = float(row[assets_col])
                has_data = True
            
            if liabilities_col in df.columns and pd.notna(row.get(liabilities_col)):
                record["total_liabilities"] = float(row[liabilities_col])
                has_data = True
            
            if equity_col in df.columns and pd.notna(row.get(equity_col)):
                record["stockholders_equity"] = float(row[equity_col])
                has_data = True
            
            if operating_col in df.columns and pd.notna(row.get(operating_col)):
                record["operating_income"] = float(row[operating_col])
                has_data = True
            
            if cashflow_col in df.columns and pd.notna(row.get(cashflow_col)):
                record["operating_cash_flow"] = float(row[cashflow_col])
                has_data = True
            
            if eps_col in df.columns and pd.notna(row.get(eps_col)):
                record["eps"] = float(row[eps_col])
                has_data = True
            
            # 비율 계산
            if "revenue" in record and "net_income" in record and record["revenue"] > 0:
                record["profit_margin"] = record["net_income"] / record["revenue"]
            
            if "stockholders_equity" in record and "net_income" in record and record["stockholders_equity"] > 0:
                record["roe"] = record["net_income"] / record["stockholders_equity"]
            
            if "total_assets" in record and "net_income" in record and record["total_assets"] > 0:
                record["roa"] = record["net_income"] / record["total_assets"]
            
            if "stockholders_equity" in record and "total_liabilities" in record and record["stockholders_equity"] > 0:
                record["debt_to_equity"] = record["total_liabilities"] / record["stockholders_equity"]
            
            if has_data:
                annual_data.append(record)
    
    return annual_data


def upsert_annual_reports(supabase: Client, annual_data: list, company_id_map: dict):
    """annual_reports 테이블에 연간 재무 데이터 업로드"""
    print("\n📝 연간 재무 데이터 업로드 중...")
    
    # company_id 추가
    for record in annual_data:
        ticker = record.pop("ticker")
        if ticker in company_id_map:
            record["company_id"] = company_id_map[ticker]
        else:
            continue
    
    # company_id가 있는 레코드만 필터링
    valid_data = [r for r in annual_data if "company_id" in r]
    
    if not valid_data:
        print("  ⚠️ 업로드할 데이터가 없습니다.")
        return
    
    # 배치로 업로드 (100개씩)
    batch_size = 100
    total_uploaded = 0
    
    for i in range(0, len(valid_data), batch_size):
        batch = valid_data[i:i+batch_size]
        
        try:
            result = supabase.table("annual_reports").upsert(
                batch,
                on_conflict="company_id,fiscal_year"
            ).execute()
            total_uploaded += len(batch)
            print(f"  📤 {total_uploaded}/{len(valid_data)} 레코드 업로드됨...")
        except Exception as e:
            print(f"  ❌ 배치 업로드 실패: {e}")
    
    print(f"  ✅ 총 {total_uploaded}개 연간 재무 데이터 저장 완료")


def check_and_create_tables(supabase: Client):
    """필요한 테이블이 있는지 확인하고 없으면 생성 안내"""
    print("\n🔍 테이블 존재 여부 확인 중...")
    
    tables_to_check = ["companies", "annual_reports", "quarterly_reports"]
    missing_tables = []
    
    for table in tables_to_check:
        try:
            # 테이블 존재 확인 (1개만 조회)
            result = supabase.table(table).select("*").limit(1).execute()
            print(f"  ✅ {table} 테이블 존재")
        except Exception as e:
            if "does not exist" in str(e).lower() or "relation" in str(e).lower():
                print(f"  ❌ {table} 테이블 없음")
                missing_tables.append(table)
            else:
                print(f"  ⚠️ {table} 테이블 확인 중 오류: {e}")
                missing_tables.append(table)
    
    if missing_tables:
        print(f"\n⚠️ 다음 테이블이 없습니다: {missing_tables}")
        print("📝 Supabase SQL Editor에서 다음 SQL을 실행하세요:")
        print("-" * 60)
        print("sql/additional_tables.sql 파일 참조")
        print("-" * 60)
        return False
    
    return True


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("📊 Supabase 데이터베이스 업로드")
    print("=" * 60)
    
    # 1. Supabase 클라이언트 생성
    try:
        supabase = get_supabase_client()
        print("✅ Supabase 연결 성공")
    except Exception as e:
        print(f"❌ Supabase 연결 실패: {e}")
        return
    
    # 2. 테이블 확인
    if not check_and_create_tables(supabase):
        print("\n⚠️ 테이블을 먼저 생성한 후 다시 실행하세요.")
        return
    
    # 3. 재무 데이터 로드
    try:
        df = load_financial_data()
        print(f"📊 {len(df)}개 기업 데이터 로드됨")
    except Exception as e:
        print(f"❌ 데이터 로드 실패: {e}")
        return
    
    # 4. 기업 정보 업로드
    companies = upsert_companies(supabase, df)
    
    # 5. company_id 매핑 조회
    company_id_map = get_company_id_map(supabase)
    print(f"📋 {len(company_id_map)}개 기업 ID 매핑 완료")
    
    # 6. 연간 재무 데이터 추출 및 업로드
    annual_data = extract_annual_data(df)
    print(f"📈 {len(annual_data)}개 연간 재무 레코드 추출됨")
    
    upsert_annual_reports(supabase, annual_data, company_id_map)
    
    print("\n" + "=" * 60)
    print("✅ Supabase 데이터 업로드 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
