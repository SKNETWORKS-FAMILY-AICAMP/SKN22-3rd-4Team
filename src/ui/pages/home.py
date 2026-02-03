"""
홈 페이지 - Main Page
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime

# 경로 설정
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Helpers
from ui.helpers import home_dashboard
from data.supabase_client import SupabaseClient


# -----------------------------------------------------------------------------
# Callbacks
# -----------------------------------------------------------------------------
def delete_favorite_callback(ticker):
    """관심 기업 삭제 콜백"""
    try:
        success = True
        if st.session_state.get("user"):
            success, _ = SupabaseClient.remove_favorite(
                st.session_state.user["id"], ticker
            )

        if success:
            if ticker in st.session_state.watchlist:
                st.session_state.watchlist.remove(ticker)
                st.toast(f"🗑️ {ticker} 삭제 완료")
        else:
            st.toast("❌ 삭제 실패")
    except Exception as e:
        st.toast(f"오류 발생: {e}")


def toggle_favorite_callback(ticker):
    """관심 기업 토글 콜백"""
    try:
        is_watched = ticker in st.session_state.watchlist
        if is_watched:
            # 삭제
            success = True
            if st.session_state.get("user"):
                success, _ = SupabaseClient.remove_favorite(
                    st.session_state.user["id"], ticker
                )
            if success:
                st.session_state.watchlist.remove(ticker)
                st.toast(f"🗑️ {ticker} 삭제됨")
        else:
            # 추가
            success = True
            if st.session_state.get("user"):
                success = SupabaseClient.add_favorite(
                    st.session_state.user["id"], ticker
                )
            if success:
                st.session_state.watchlist.append(ticker)
                st.toast(f"⭐ {ticker} 추가됨")
            else:
                st.toast("추가 실패")
    except Exception as e:
        st.toast(f"오류: {e}")


# -----------------------------------------------------------------------------
# Caching Functions
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def _get_cached_companies(supabase_client):
    """모든 기업 목록 캐싱 (1시간)"""
    return supabase_client.get_all_companies()


@st.cache_data(ttl=3600, show_spinner=False)
def _get_cached_annual_reports(supabase_client):
    """연간 재무 데이터 캐싱 (1시간)"""
    return supabase_client.get_annual_reports()


@st.cache_data(ttl=3600, show_spinner=False)
def _get_cached_top_revenue_companies(supabase_client, year=2024, limit=20):
    """매출 상위 기업 캐싱 (1시간)"""
    return supabase_client.get_top_companies_by_revenue(year, limit)


@st.cache_data(ttl=3600, show_spinner=False)
def _get_cached_exchange_rates():
    """환율 정보 캐싱 (1시간)"""
    from tools.exchange_rate_client import get_exchange_client

    try:
        client = get_exchange_client()
        return client.get_major_rates_summary()
    except Exception:
        return {}


def _get_data_period(supabase_client) -> str:
    """DB에서 실제 데이터 기간 조회"""
    try:
        annual_df = supabase_client.get_annual_reports()
        if not annual_df.empty and "fiscal_year" in annual_df.columns:
            min_year = int(annual_df["fiscal_year"].min())
            max_year = int(annual_df["fiscal_year"].max())
            return f"{min_year}-{max_year}"
    except:
        pass
    return "2020-2024"


def _get_last_update() -> str:
    """마지막 업데이트 시간"""
    now = datetime.now()
    return now.strftime("%m/%d %H:%M")


# -----------------------------------------------------------------------------
# Main Render
# -----------------------------------------------------------------------------
def render():
    """홈 페이지 렌더링"""
    global SUPABASE_AVAILABLE

    # Lazy Imports Check
    try:
        from data.supabase_client import (
            SupabaseClient,
            get_companies,
            get_top_revenue_companies,
        )

        SUPABASE_AVAILABLE = True
    except ImportError:
        SUPABASE_AVAILABLE = False

    try:
        from tools.exchange_rate_client import get_exchange_client

        EXCHANGE_AVAILABLE = True
    except ImportError:
        EXCHANGE_AVAILABLE = False

    # Header
    st.markdown(
        '<h1 class="main-header">📊 미국 재무제표 분석 및 투자 인사이트 봇</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="sub-header">AI 기반 미국 상장사 재무제표 분석 도구</p>',
        unsafe_allow_html=True,
    )

    # 데이터베이스 연결 상태 확인 및 데이터 로드
    companies_df = pd.DataFrame()
    company_count = 0

    if SUPABASE_AVAILABLE:
        try:
            # Cached Call
            companies_df = _get_cached_companies(SupabaseClient)
            company_count = len(companies_df)
        except Exception as e:
            st.warning(f"⚠️ 데이터 로드 중 오류: {e}")
    else:
        st.warning("⚠️ Supabase 연결이 설정되지 않았습니다. .env 파일을 확인하세요.")

    st.markdown("---")

    # 환율 정보 표시
    if EXCHANGE_AVAILABLE:
        exchange_rates = _get_cached_exchange_rates()
        # display_rates만 전달 ("update_time" 등 제외)
        if exchange_rates:
            home_dashboard.render_exchange_rates(
                exchange_rates.get("display_rates", {}),
                update_time=exchange_rates.get("update_time"),
            )

    # 관심 기업 초기화
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = []

    # 관심 기업 섹션 (있을 때만 표시)
    if st.session_state.watchlist:
        st.markdown("### ⭐ 관심 기업")
        cols = st.columns(8)
        for i, ticker in enumerate(st.session_state.watchlist):
            if i < 8:
                with cols[i]:
                    st.button(
                        f"🗑️ {ticker}",
                        key=f"home_rm_{ticker}",
                        help="제거",
                        on_click=delete_favorite_callback,
                        args=(ticker,),
                    )

        if len(st.session_state.watchlist) > 8:
            st.caption(f"... +{len(st.session_state.watchlist) - 8}개 더")
        st.markdown("---")

    # 메트릭 카드 - 동적 데이터
    home_dashboard.render_metric_cards(company_count)

    # 탭 구성
    if "home_tab_selection" not in st.session_state:
        st.session_state.home_tab_selection = "🏆 매출 상위 기업"

    tabs = ["🏆 매출 상위 기업", "🔍 기업 검색", "💾 DB 현황", "💡 빠른 시작"]
    tab1, tab2, tab3, tab4 = st.tabs(tabs)

    with tab1:
        home_dashboard.render_top_companies_tab(SUPABASE_AVAILABLE, company_count)

    with tab2:
        home_dashboard.render_search_tab(
            SUPABASE_AVAILABLE,
            SupabaseClient if SUPABASE_AVAILABLE else None,
            toggle_favorite_callback,
        )

    with tab3:
        home_dashboard.render_db_status_tab(
            SUPABASE_AVAILABLE, companies_df, company_count
        )

    with tab4:
        home_dashboard.render_quick_start_tab()


if __name__ == "__main__":
    render()
