"""
Supabase 데이터베이스 클라이언트
앱에서 Supabase DB에 연결하여 데이터를 조회/저장합니다.
"""

import os
from typing import Optional, List, Dict, Any
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
import hashlib

load_dotenv()


class SupabaseClient:
    """Supabase 데이터베이스 클라이언트"""

    _instance: Optional[Client] = None

    @classmethod
    def get_client(cls) -> Client:
        """싱글톤 Supabase 클라이언트 반환"""
        if cls._instance is None:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_KEY")

            if not url or not key:
                raise ValueError("SUPABASE_URL과 SUPABASE_KEY가 설정되어야 합니다.")

            cls._instance = create_client(url, key)

        return cls._instance

    @classmethod
    def get_all_companies(cls) -> pd.DataFrame:
        """모든 기업 정보 조회"""
        client = cls.get_client()
        result = client.table("companies").select("*").order("ticker").execute()
        return pd.DataFrame(result.data)

    @classmethod
    def get_company_by_ticker(cls, ticker: str) -> Optional[Dict]:
        """티커로 기업 정보 조회"""
        client = cls.get_client()
        result = client.table("companies").select("*").eq("ticker", ticker).execute()
        return result.data[0] if result.data else None

    @classmethod
    def get_annual_reports(
        cls, company_id: str = None, ticker: str = None
    ) -> pd.DataFrame:
        """연간 재무 데이터 조회"""
        client = cls.get_client()

        query = client.table("annual_reports").select(
            "*, companies(ticker, company_name)"
        )

        if company_id:
            query = query.eq("company_id", company_id)

        result = query.order("fiscal_year", desc=True).execute()

        if not result.data:
            return pd.DataFrame()

        # DataFrame 생성 및 정리
        df = pd.DataFrame(result.data)

        # companies 정보 분리
        if "companies" in df.columns:
            df["ticker"] = df["companies"].apply(
                lambda x: x.get("ticker") if x else None
            )
            df["company_name"] = df["companies"].apply(
                lambda x: x.get("company_name") if x else None
            )
            df = df.drop(columns=["companies"])

        # 티커 필터
        if ticker and "ticker" in df.columns:
            df = df[df["ticker"] == ticker]

        return df

    @classmethod
    def get_financial_summary(cls, ticker: str) -> Dict:
        """특정 기업의 재무 요약 정보"""
        client = cls.get_client()

        # [FIX] 단순 get_company_by_ticker -> company_id 조회 방식은
        # 중복 회사 데이터(ID가 다른 경우)가 있을 때 빈 데이터를 참조할 수 있음.
        # 따라서 annual_reports를 주축으로 companies를 조인하여 티커로 직접 검색함.

        try:
            # [OPTIMIZED] Standard JOIN query
            # We search for reports by joining with the companies table on ticker.
            # This is the most efficient and correct way to relational data.
            reports_query = (
                client.table("annual_reports")
                .select(
                    "*, companies!inner(id, ticker, company_name, korean_name, sector, industry)"
                )
                .eq("companies.ticker", ticker)
                .order("fiscal_year", desc=True)
                .limit(50)
                .execute()
            )
            raw_reports = reports_query.data if reports_query.data else []

            # [DEBUG LOGGING]
            try:
                with open("debug_query_log.txt", "a", encoding="utf-8") as f:
                    f.write(
                        f"\n[QUERY DYNAMIC] Ticker: {ticker} -> Resolved ID: {target_company_id}\n"
                    )
                    f.write(f"Raw Count: {len(raw_reports)}\n")
                    for r in raw_reports:
                        f.write(
                            f"  FY: {r.get('fiscal_year')} | Rev: {r.get('revenue')} | ID: {r.get('company_id')}\n"
                        )
            except Exception:
                pass

            # [DEBUG LOGGING]
            try:
                with open("debug_query_log.txt", "a", encoding="utf-8") as f:
                    f.write(f"\n[QUERY] Ticker: {ticker}\n")
                    f.write(f"Raw Count: {len(raw_reports)}\n")
                    for r in raw_reports:
                        f.write(
                            f"  FY: {r.get('fiscal_year')} | Rev: {r.get('revenue')} | ID: {r.get('company_id')}\n"
                        )
            except Exception:
                pass
        except Exception as e:
            # 조인 쿼리 실패 시 Fallback
            print(f"Join query failed: {e}")
            raw_reports = []

        # 데이터가 없으면 기존 방식(Fallback)으로 회사 정보라도 조회 시도
        if not raw_reports:
            company = cls.get_company_by_ticker(ticker)
            return {"company": company, "annual_reports": []} if company else {}

        # 회사 정보는 첫 번째 리포트에서 추출 (어차피 같은 티커)
        # companies 필드가 딕셔너리로 포함됨
        first_row_company = raw_reports[0].get("companies")
        # 회사 정보 객체 구성
        company = {
            "id": raw_reports[0].get("company_id"),  # 리포트의 company_id 사용
            "ticker": first_row_company.get("ticker"),
            "company_name": first_row_company.get("company_name"),
            "korean_name": first_row_company.get("korean_name"),
            "sector": first_row_company.get("sector"),
            "industry": first_row_company.get("industry"),
        }

        final_reports = []
        if raw_reports:
            # 연도별로 데이터 분류
            reports_by_year = {}
            for row in raw_reports:
                fy = row.get("fiscal_year")
                if not fy:
                    continue

                # companies 필드는 리포트 데이터 자체에서는 제거 (깔끔하게)
                row_clean = {k: v for k, v in row.items() if k != "companies"}

                # [FIX] revenue가 없으면 (gross_profit + cost_of_revenue) 사용
                # DB 스키마상 total_revenue는 없고, 대신 gross_profit과 cost_of_revenue는 존재함.
                # Revenue = Gross Profit + Cost of Revenue
                if row_clean.get("revenue") is None:
                    gp = row_clean.get("gross_profit")
                    cor = row_clean.get("cost_of_revenue")
                    if gp is not None and cor is not None:
                        # cost_of_revenue가 보통 양수로 저장되면 더해주고, 음수면 빼줘야 함.
                        # 일반적인 DB에서는 양수로 저장됨.
                        row_clean["revenue"] = float(gp) + float(cor)

                if fy not in reports_by_year:
                    reports_by_year[fy] = row_clean
                else:
                    # 이미 있는 행보다 현재 행이 더 나은지 확인 (revenue 유무)
                    current_rev = row.get("revenue")
                    saved_rev = reports_by_year[fy].get("revenue")

                    # 저장된 것이 없고(None), 현재 것은 있으면 교체
                    if saved_rev is None and current_rev is not None:
                        reports_by_year[fy] = row_clean

            # [DEBUG LOGGING]
            try:
                with open("debug_query_log.txt", "a", encoding="utf-8") as f:
                    f.write(f"\n[QUERY FULL INSPECTOR] Ticker: {ticker}\n")
                    if reports_by_year:
                        first_year = list(reports_by_year.keys())[0]
                        first_row = reports_by_year[first_year]
                        f.write(f"First Row ({first_year}) Non-Null Data:\n")
                        for k, v in first_row.items():
                            if v is not None:
                                f.write(f"  {k}: {v}\n")
                    else:
                        f.write("No reports found to inspect.\n")
            except Exception:
                pass

            # 딕셔너리를 리스트로 변환 및 정렬 (최신순)
            final_reports = sorted(
                reports_by_year.values(), key=lambda x: x["fiscal_year"], reverse=True
            )[
                :5
            ]  # 최근 5년치만 선택

        return {"company": company, "annual_reports": final_reports}

    @classmethod
    def get_top_companies_by_revenue(
        cls, year: int = 2024, limit: int = 20
    ) -> pd.DataFrame:
        """매출 상위 기업 조회"""
        client = cls.get_client()

        result = (
            client.table("annual_reports")
            .select(
                "revenue, net_income, total_assets, companies(ticker, company_name)"
            )
            .eq("fiscal_year", year)
            .not_.is_("revenue", "null")
            .order("revenue", desc=True)
            .limit(limit)
            .execute()
        )

        if not result.data:
            return pd.DataFrame()

        df = pd.DataFrame(result.data)
        df["ticker"] = df["companies"].apply(lambda x: x.get("ticker") if x else None)
        df["company_name"] = df["companies"].apply(
            lambda x: x.get("company_name") if x else None
        )
        df = df.drop(columns=["companies"])

        return df

    @classmethod
    def get_financial_ratios(cls, year: int = 2024) -> pd.DataFrame:
        """주요 재무비율 조회"""
        client = cls.get_client()

        result = (
            client.table("annual_reports")
            .select(
                "profit_margin, roe, roa, debt_to_equity, companies(ticker, company_name)"
            )
            .eq("fiscal_year", year)
            .execute()
        )

        if not result.data:
            return pd.DataFrame()

        df = pd.DataFrame(result.data)
        df["ticker"] = df["companies"].apply(lambda x: x.get("ticker") if x else None)
        df["company_name"] = df["companies"].apply(
            lambda x: x.get("company_name") if x else None
        )
        df = df.drop(columns=["companies"])

        return df

    @classmethod
    def search_companies(cls, query: str) -> pd.DataFrame:
        """기업 검색 (티커, 영문명 또는 한글명으로)"""
        client = cls.get_client()

        result = (
            client.table("companies")
            .select("*")
            .or_(
                f"ticker.ilike.%{query}%,company_name.ilike.%{query}%,korean_name.ilike.%{query}%"
            )
            .execute()
        )

        return pd.DataFrame(result.data)

    @classmethod
    def execute_query(cls, query: str) -> pd.DataFrame:
        """RPC를 통한 사용자 정의 쿼리 실행 (제한적)"""
        # Supabase는 직접 SQL 실행을 지원하지 않음
        # 대신 저장 함수(RPC)를 통해 실행해야 함
        client = cls.get_client()
        # 여기서는 기본 테이블 조회만 지원
        return pd.DataFrame()

    @classmethod
    def register_user(cls, email, password):
        """사용자 등록 (회원가입)"""
        client = cls.get_client()
        try:
            # 1. 이메일 중복 확인
            existing = client.table("users").select("id").eq("email", email).execute()
            if existing.data:
                return {"success": False, "message": "이미 존재하는 이메일입니다."}

            # 2. 비밀번호 해싱 (간단한 SHA256 사용, 실제 프로덕션엔 bcrypt 권장)
            password_hash = hashlib.sha256(password.encode()).hexdigest()

            # 3. 사용자 생성
            data = {"email": email, "password_hash": password_hash}
            result = client.table("users").insert(data).execute()

            if result.data:
                return {"success": True, "user": result.data[0]}
            return {"success": False, "message": "사용자 등록 실패"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    def login_user(cls, email, password):
        """사용자 로그인"""
        client = cls.get_client()
        try:
            password_hash = hashlib.sha256(password.encode()).hexdigest()

            result = (
                client.table("users")
                .select("*")
                .eq("email", email)
                .eq("password_hash", password_hash)
                .execute()
            )

            if result.data:
                return {"success": True, "user": result.data[0]}
            return {
                "success": False,
                "message": "이메일 또는 비밀번호가 잘못되었습니다.",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    def change_password(cls, user_id: str, current_password: str, new_password: str):
        """비밀번호 변경"""
        client = cls.get_client()
        try:
            # 1. 현재 비밀번호 확인
            current_hash = hashlib.sha256(current_password.encode()).hexdigest()
            user = (
                client.table("users")
                .select("*")
                .eq("id", user_id)
                .eq("password_hash", current_hash)
                .execute()
            )

            if not user.data:
                return {
                    "success": False,
                    "message": "현재 비밀번호가 일치하지 않습니다.",
                }

            # 2. 새 비밀번호 해싱 및 업데이트
            new_hash = hashlib.sha256(new_password.encode()).hexdigest()
            result = (
                client.table("users")
                .update({"password_hash": new_hash})
                .eq("id", user_id)
                .execute()
            )

            if result.data:
                return {"success": True, "message": "비밀번호가 변경되었습니다."}
            return {"success": False, "message": "비밀번호 변경 실패"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    def delete_user(cls, user_id: str, password: str):
        """회원 탈퇴 - 사용자 및 관련 데이터 삭제"""
        client = cls.get_client()
        try:
            # 1. 비밀번호 확인
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            user = (
                client.table("users")
                .select("*")
                .eq("id", user_id)
                .eq("password_hash", password_hash)
                .execute()
            )

            if not user.data:
                return {"success": False, "message": "비밀번호가 일치하지 않습니다."}

            # 2. 관심 기업 데이터 삭제
            client.table("favorites").delete().eq("user_id", user_id).execute()

            # 3. 사용자 삭제
            result = client.table("users").delete().eq("id", user_id).execute()

            if result.data:
                return {"success": True, "message": "회원 탈퇴가 완료되었습니다."}
            return {"success": False, "message": "회원 탈퇴 실패"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    def add_favorite(cls, user_id, ticker):
        """관심 기업 추가"""
        client = cls.get_client()
        try:
            data = {"user_id": user_id, "ticker": ticker}
            client.table("favorites").upsert(data).execute()
            return True
        except Exception:
            return False

    @classmethod
    def remove_favorite(cls, user_id, ticker):
        """관심 기업 제거"""
        client = cls.get_client()
        try:
            # delete()는 삭제된 행을 반환함
            response = (
                client.table("favorites")
                .delete()
                .eq("user_id", user_id)
                .eq("ticker", ticker)
                .execute()
            )

            # 삭제된 데이터가 있는지 확인
            if response.data and len(response.data) > 0:
                return True, None
            else:
                return False, "삭제할 데이터가 없거나 권한이 없습니다."
        except Exception as e:
            print(f"Delete Error: {e}")  # Debug print
            return False, str(e)

    @classmethod
    def get_favorites(cls, user_id):
        """사용자의 관심 기업 목록 조회"""
        client = cls.get_client()
        try:
            result = (
                client.table("favorites")
                .select("ticker")
                .eq("user_id", user_id)
                .execute()
            )
            return [item["ticker"] for item in result.data]
        except Exception:
            return []


# 편의 함수
def get_supabase() -> Client:
    """Supabase 클라이언트 가져오기"""
    return SupabaseClient.get_client()


def get_companies() -> pd.DataFrame:
    """모든 기업 목록"""
    return SupabaseClient.get_all_companies()


def get_company_financials(ticker: str) -> Dict:
    """기업 재무 정보"""
    return SupabaseClient.get_financial_summary(ticker)


def get_top_revenue_companies(year: int = 2024, limit: int = 20) -> pd.DataFrame:
    """매출 상위 기업"""
    return SupabaseClient.get_top_companies_by_revenue(year, limit)
