"""
실적 발표 캘린더 페이지
yfinance를 사용하여 관심 기업(Watchlist)의 실적 발표 일정만 표시
(무료/무제한/정확성 보장)
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

# 경로 설정
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


@st.cache_data(ttl=3600, show_spinner=False)
def get_earnings_dates_yf(ticker: str) -> pd.DataFrame:
    try:
        import yfinance as yf

        stock = yf.Ticker(ticker)
        dates_df = stock.earnings_dates
        if dates_df is None or dates_df.empty:
            return pd.DataFrame()
        return dates_df
    except Exception:
        return pd.DataFrame()


def render():
    """실적 발표 캘린더 페이지 렌더링"""

    st.markdown(
        '<h1 class="main-header">🗓️ 실적 발표 캘린더</h1>',
        unsafe_allow_html=True,
    )
    st.caption("관심 기업(Watchlist) 전용 | Yahoo Finance 데이터 기반")

    st.markdown("---")

    # --- 날짜 및 분기 선택 섹션 ---
    current_year = datetime.now().year
    current_month = datetime.now().month
    current_q = (current_month - 1) // 3 + 1

    # col1(연도)과 col2(분기)의 비율을 조절하여 배치
    col1, col2 = st.columns([1, 3])

    with col1:
        selected_year = st.number_input(
            "연도",
            min_value=current_year - 5,
            max_value=current_year + 1,
            value=current_year,
            key="calendar_year",
        )

    with col2:
        # 연도 입력창의 레이블(Label) 높이만큼 여백을 주어 수평 정렬
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)

        if "selected_quarter_idx" not in st.session_state:
            st.session_state.selected_quarter_idx = current_q

        quarter_cols = st.columns(4)
        # 레이블을 간결하게 수정하여 높이 불일치 방지
        quarters = [
            ("1분기", 1),
            ("2분기", 2),
            ("3분기", 3),
            ("4분기", 4),
        ]

        for q_col, (label, q_num) in zip(quarter_cols, quarters):
            with q_col:
                is_selected = st.session_state.selected_quarter_idx == q_num

                if is_selected:
                    # 선택된 박스: st.button과 동일한 높이(38.4px) 유지
                    st.markdown(
                        f"""
                        <div style="
                            background: linear-gradient(135deg, #FF6B6B 0%, #FF5252 100%);
                            color: white;
                            height: 38.4px;
                            line-height: 34.4px;
                            text-align: center;
                            border-radius: 8px;
                            font-weight: bold;
                            font-size: 14px;
                            border: 2px solid #FF4444;
                            box-sizing: border-box;
                            cursor: default;
                        ">
                            {label}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    if st.button(
                        label, key=f"quarter_{q_num}", use_container_width=True
                    ):
                        st.session_state.selected_quarter_idx = q_num
                        st.rerun()

    selected_quarter_idx = st.session_state.selected_quarter_idx

    # --- 날짜 계산 로직 ---
    q_map = {
        1: ("01-01", "03-31"),
        2: ("04-01", "06-30"),
        3: ("07-01", "09-30"),
        4: ("10-01", "12-31"),
    }
    start_md, end_md = q_map[selected_quarter_idx]
    start_date = datetime.strptime(f"{selected_year}-{start_md}", "%Y-%m-%d").date()
    end_date = datetime.strptime(f"{selected_year}-{end_md}", "%Y-%m-%d").date()

    st.info(
        f"📅 조회 기간: {selected_year}년 {selected_quarter_idx}분기 ({start_date} ~ {end_date})"
    )

    # --- 관심 기업 데이터 처리 ---
    watchlist = st.session_state.get("watchlist", [])

    st.warning(
        """
        📢 **안내: 관심 기업(Watchlist)에 등록된 종목의 일정만 조회가 가능합니다.**
        """
    )

    if not watchlist:
        st.error("⚠️ 관심 기업이 없습니다. 사이드바에서 기업을 추가해주세요.")
        return

    if st.button("📅 일정 조회 (관심 기업)", type="primary", use_container_width=True):
        with st.spinner(f"관심 기업 {len(watchlist)}개의 실적 일정을 조회 중입니다..."):
            results = []
            progress_bar = st.progress(0)

            for idx, ticker in enumerate(watchlist):
                progress_bar.progress((idx + 1) / len(watchlist))
                e_df = get_earnings_dates_yf(ticker)

                if not e_df.empty:
                    for date_idx, row in e_df.iterrows():
                        e_date = date_idx.date()
                        if start_date <= e_date <= end_date:
                            eps_est = row.get("EPS Estimate")
                            eps_act = row.get("Reported EPS")
                            surprise = row.get("Surprise(%)")

                            results.append(
                                {
                                    "발표일": e_date.strftime("%Y-%m-%d"),
                                    "티커": ticker,
                                    "EPS 예상": (
                                        f"{eps_est:.2f}" if pd.notna(eps_est) else "-"
                                    ),
                                    "EPS 실제": (
                                        f"{eps_act:.2f}" if pd.notna(eps_act) else "-"
                                    ),
                                    "서프라이즈": (
                                        f"{surprise * 100:.1f}%"
                                        if pd.notna(surprise)
                                        else "-"
                                    ),
                                }
                            )

            progress_bar.empty()

            if not results:
                st.info("선택한 기간에 관심 기업의 실적 발표가 없습니다.")
            else:
                df = pd.DataFrame(results).sort_values("발표일")
                st.success(f"📊 총 {len(df)}건의 실적 일정이 검색되었습니다.")

                for d in sorted(df["발표일"].unique()):
                    with st.expander(f"📅 {d}", expanded=True):
                        day_df = df[df["발표일"] == d].copy()
                        st.dataframe(day_df, use_container_width=True, hide_index=True)

    # --- 관심 기업 관리 섹션 ---
    st.markdown("---")
    st.markdown(f"### ⭐ 내 관심 기업 ({len(watchlist)}개)")
    if watchlist:
        cols = st.columns(6)
        for i, ticker in enumerate(watchlist):
            with cols[i % 6]:
                if st.button(f"✕ {ticker}", key=f"rm_cal_{ticker}"):
                    st.session_state.watchlist.remove(ticker)
                    st.rerun()


if __name__ == "__main__":
    render()
