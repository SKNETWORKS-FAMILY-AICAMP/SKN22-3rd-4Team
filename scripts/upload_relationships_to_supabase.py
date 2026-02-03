"""
기업 관계 데이터를 Supabase에 업로드

수집된 10-K 관계 데이터를 Supabase company_relationships 테이블에 저장합니다.
"""
import os
import sys
from pathlib import Path
import pandas as pd
import json
from dotenv import load_dotenv

load_dotenv()

from supabase import create_client, Client

# 설정
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# 데이터 파일 경로
DATA_DIR = Path(__file__).parent.parent / "data" / "10k_documents"

# 티커-기업명 매핑 (Supabase에서 조회)
TICKER_MAP = {}


def get_supabase_client() -> Client:
    """Supabase 클라이언트 생성"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL과 SUPABASE_KEY가 .env 파일에 설정되어야 합니다.")
    
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def load_relationships() -> pd.DataFrame:
    """관계 데이터 로드"""
    csv_path = DATA_DIR / "relationships.csv"
    
    if not csv_path.exists():
        raise FileNotFoundError(f"관계 데이터 파일을 찾을 수 없습니다: {csv_path}")
    
    df = pd.read_csv(csv_path)
    print(f"📂 {len(df)}개 관계 데이터 로드됨")
    
    return df


def load_processed_companies() -> pd.DataFrame:
    """처리된 기업 목록 로드"""
    csv_path = DATA_DIR / "processed_companies.csv"
    
    if not csv_path.exists():
        return pd.DataFrame()
    
    return pd.read_csv(csv_path)


def build_ticker_map(supabase: Client):
    """티커-기업명 매핑 생성"""
    global TICKER_MAP
    
    # Supabase에서 기업 목록 조회
    result = supabase.table("companies").select("ticker, company_name").execute()
    
    for row in result.data:
        ticker = row["ticker"]
        name = row["company_name"]
        TICKER_MAP[name.upper()] = ticker
        # 짧은 이름도 매핑
        short_name = name.split()[0].upper()
        if len(short_name) > 3:
            TICKER_MAP[short_name] = ticker
    
    print(f"📋 {len(TICKER_MAP)}개 기업 매핑 생성됨")


def find_ticker(company_name: str) -> str:
    """기업명으로 티커 찾기"""
    if not company_name:
        return None
    
    name_upper = company_name.upper()
    
    # 직접 매칭
    if name_upper in TICKER_MAP:
        return TICKER_MAP[name_upper]
    
    # 부분 매칭
    for key, ticker in TICKER_MAP.items():
        if key in name_upper or name_upper in key:
            return ticker
    
    return None


def prepare_relationship_data(df: pd.DataFrame, companies_df: pd.DataFrame) -> list:
    """업로드용 관계 데이터 준비"""
    records = []
    
    # 기업별 티커/제출일 매핑
    company_info = {}
    for _, row in companies_df.iterrows():
        company_info[row["name"]] = {
            "ticker": row["ticker"],
            "filing_date": row.get("filing_date")
        }
    
    for _, row in df.iterrows():
        source = row["source"]
        target = row["target"]
        rel_type = row["type"]
        
        # 소스 기업 정보
        source_info = company_info.get(source, {})
        source_ticker = source_info.get("ticker")
        filing_date = source_info.get("filing_date")
        
        # 타겟 기업 티커 찾기
        target_ticker = find_ticker(target)
        
        # 신뢰도 설정 (관계 유형별)
        confidence = {
            "supplier": 0.8,
            "customer": 0.8,
            "competitor": 0.7,
            "subsidiary": 0.9,
            "partner": 0.75,
            "mentioned": 0.5,
        }.get(rel_type, 0.5)
        
        record = {
            "source_company": source,
            "source_ticker": source_ticker,
            "target_company": target,
            "target_ticker": target_ticker,
            "relationship_type": rel_type,
            "confidence": confidence,
            "filing_date": filing_date if pd.notna(filing_date) else None,
        }
        
        records.append(record)
    
    return records


def check_and_create_table(supabase: Client):
    """테이블 존재 여부 확인"""
    try:
        result = supabase.table("company_relationships").select("id").limit(1).execute()
        print("✅ company_relationships 테이블 존재")
        return True
    except Exception as e:
        if "does not exist" in str(e).lower() or "relation" in str(e).lower():
            print("⚠️ company_relationships 테이블이 없습니다.")
            print("📝 Supabase SQL Editor에서 sql/company_relationships.sql을 실행하세요.")
            return False
        else:
            # 테이블은 있지만 다른 오류
            print(f"⚠️ 테이블 확인 중 오류: {e}")
            return True  # 일단 진행 시도


def upload_relationships(supabase: Client, records: list):
    """관계 데이터 업로드"""
    print(f"\n📝 {len(records)}개 관계 데이터 업로드 중...")
    
    # 기존 데이터 삭제 옵션 (중복 방지)
    try:
        # 기존 데이터 개수 확인
        existing = supabase.table("company_relationships").select("id", count="exact").execute()
        if existing.count and existing.count > 0:
            print(f"   기존 데이터: {existing.count}개")
            # 전체 삭제 후 재업로드
            supabase.table("company_relationships").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            print("   기존 데이터 삭제 완료")
    except Exception as e:
        print(f"   기존 데이터 확인/삭제 실패: {e}")
    
    # 배치 업로드 (500개씩)
    batch_size = 500
    total_uploaded = 0
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        
        try:
            result = supabase.table("company_relationships").insert(batch).execute()
            total_uploaded += len(batch)
            print(f"   📤 {total_uploaded}/{len(records)} 레코드 업로드됨...")
        except Exception as e:
            print(f"   ❌ 배치 업로드 실패 (batch {i}): {e}")
            # 개별 레코드 시도
            for record in batch:
                try:
                    supabase.table("company_relationships").insert(record).execute()
                    total_uploaded += 1
                except:
                    pass
    
    print(f"\n✅ 총 {total_uploaded}개 관계 데이터 저장 완료")


def show_summary(supabase: Client):
    """저장된 데이터 요약"""
    print("\n" + "=" * 60)
    print("📊 저장된 관계 데이터 요약")
    print("=" * 60)
    
    try:
        # 총 개수
        total = supabase.table("company_relationships").select("id", count="exact").execute()
        print(f"   총 관계: {total.count}개")
        
        # 관계 유형별
        for rel_type in ["supplier", "customer", "competitor", "subsidiary", "partner", "mentioned"]:
            result = supabase.table("company_relationships").select("id", count="exact").eq("relationship_type", rel_type).execute()
            print(f"   - {rel_type}: {result.count}개")
        
        # 티커가 있는 관계
        with_ticker = supabase.table("company_relationships").select("id", count="exact").not_.is_("target_ticker", "null").execute()
        print(f"\n   티커 매핑된 관계: {with_ticker.count}개")
        
    except Exception as e:
        print(f"   요약 조회 오류: {e}")


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("📊 Supabase 기업 관계 데이터 업로드")
    print("=" * 60)
    
    # 1. Supabase 클라이언트 생성
    try:
        supabase = get_supabase_client()
        print("✅ Supabase 연결 성공")
    except Exception as e:
        print(f"❌ Supabase 연결 실패: {e}")
        return
    
    # 2. 테이블 확인
    if not check_and_create_table(supabase):
        return
    
    # 3. 티커 매핑 생성
    build_ticker_map(supabase)
    
    # 4. 데이터 로드
    try:
        relationships_df = load_relationships()
        companies_df = load_processed_companies()
    except Exception as e:
        print(f"❌ 데이터 로드 실패: {e}")
        return
    
    # 5. 업로드용 데이터 준비
    records = prepare_relationship_data(relationships_df, companies_df)
    print(f"📋 {len(records)}개 레코드 준비됨")
    
    # 6. 업로드
    upload_relationships(supabase, records)
    
    # 7. 요약
    show_summary(supabase)
    
    print("\n" + "=" * 60)
    print("✅ 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
