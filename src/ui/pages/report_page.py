"""
Investment Report Generation Page - 투자 레포트 생성 페이지 (Ticker Autocomplete Version)
"""

import streamlit as st
from utils.pdf_utils import create_pdf
from streamlit_searchbox import st_searchbox
from utils.supabase_helper import search_tickers

# ============================================================
# 차트 유틸리티 로드
# ============================================================

# Plotly 차트 (Streamlit 표시용 - 벡터 기반 선명)
PLOTLY_FUNCS = {}
PLOTLY_AVAILABLE = False
try:
    from utils.plotly_charts import (
        generate_line_chart_plotly,
        generate_candlestick_chart_plotly,
        generate_volume_chart_plotly,
        generate_financial_chart_plotly,
    )

    PLOTLY_FUNCS = {
        "generate_line_chart_plotly": generate_line_chart_plotly,
        "generate_candlestick_chart_plotly": generate_candlestick_chart_plotly,
        "generate_volume_chart_plotly": generate_volume_chart_plotly,
        "generate_financial_chart_plotly": generate_financial_chart_plotly,
    }
    PLOTLY_AVAILABLE = True
except ImportError:
    pass

# Matplotlib 차트 (PDF 내보내기용)
MPL_FUNCS = {}
CHART_UTILS_AVAILABLE = False
try:
    from utils.chart_utils import (
        generate_line_chart,
        generate_candlestick_chart,
        generate_volume_chart,
        generate_financial_chart,
    )

    MPL_FUNCS = {
        "generate_line_chart": generate_line_chart,
        "generate_candlestick_chart": generate_candlestick_chart,
        "generate_volume_chart": generate_volume_chart,
        "generate_financial_chart": generate_financial_chart,
    }
    CHART_UTILS_AVAILABLE = True
except ImportError:
    pass

# 헬퍼 함수 로드
try:
    from ui.helpers.chart_helpers import (
        render_charts_plotly,
        render_charts_matplotlib,
        resolve_tickers,
        generate_report_with_spinner,
        create_download_button,
        render_chart_selection,
    )

    HELPERS_AVAILABLE = True
except ImportError:
    HELPERS_AVAILABLE = False


# ============================================================
# CSS 스타일
# ============================================================

FORM_CSS = """
<style>
/* Searchbox 스타일 조정 */
.stSearchbox > div {
    margin-top: 0px;
}
</style>
"""


# ============================================================
# 차트 렌더링 (헬퍼 사용)
# ============================================================


def render_charts(tickers: list) -> list:
    """선택된 차트 렌더링 및 PDF용 이미지 수집"""

    # 헬퍼 함수 사용
    if HELPERS_AVAILABLE:
        if PLOTLY_AVAILABLE:
            return render_charts_plotly(
                tickers,
                PLOTLY_FUNCS,
                MPL_FUNCS if CHART_UTILS_AVAILABLE else None,
            )
        elif CHART_UTILS_AVAILABLE:
            return render_charts_matplotlib(tickers, MPL_FUNCS)

    # 헬퍼가 없거나 차트 라이브러리가 없는 경우 Fallback
    try:
        from ui.helpers.chart_helpers import render_stock_chart_fallback

        render_stock_chart_fallback(tickers)
    except ImportError:
        st.warning("차트 헬퍼 모듈을 로드할 수 없습니다.")

    return []


# ============================================================
# 메인 렌더 함수
# ============================================================


def render():
    """Render Report Generator Page"""
    st.markdown(FORM_CSS, unsafe_allow_html=True)

    st.markdown('<h1 class="main-header">📊 레포트 생성</h1>', unsafe_allow_html=True)
    st.caption("gpt-4.1-mini 기반 | 단일 기업 분석 & 비교 분석 레포트 생성")

    st.markdown("---")
    st.info(
        "💡 **검색 팁**: 회사명(한글/영어)이나 티커를 입력하면 자동완성 목록이 나타납니다. (예: '테' → '테슬라')"
    )

    # 차트 선택 UI
    if HELPERS_AVAILABLE:
        render_chart_selection()

    col1, col2 = st.columns([4, 1])

    from streamlit_searchbox import st_searchbox
    from utils.supabase_helper import search_tickers

    # -------------------------------------------------------------
    # Multi-Select State Manager
    # -------------------------------------------------------------
    if "selected_tickers" not in st.session_state:
        st.session_state.selected_tickers = []

    # Counter for unique keys (fixes resurrection bug)
    if "search_key_id" not in st.session_state:
        st.session_state.search_key_id = 0

    def remove_ticker(t):
        if t in st.session_state.selected_tickers:
            st.session_state.selected_tickers.remove(t)
            # Increment key ID to force searchbox reset
            st.session_state.search_key_id += 1

    # -------------------------------------------------------------
    # 1. Selected Tags Display Area
    # -------------------------------------------------------------
    st.markdown("### 🎯 분석 대상 (선택됨)")

    # Custom CSS for flexbox layout of tags
    st.markdown(
        """
    <style>
    .favorite-tag-container {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 20px;
    }
    .stButton button {
        height: auto !important;
        padding: 4px 12px !important;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    if st.session_state.selected_tickers:
        # Use a container for flex layout if possible, but st.button is tricky.
        # Fallback to dense columns or just flowing markdown if they were links.
        # Since they are buttons, we'll use a dense column layout but with dynamic sizing.
        # Actually, standard columns with hardcoded 6 is what caused the gap.
        # Let's try flexible columns based on count, max 8.

        tags = st.session_state.selected_tickers
        cols = st.columns(8)  # More columns = tighter packing for small items

        for i, t in enumerate(tags):
            col_idx = i % 8
            with cols[col_idx]:
                if st.button(t, key=f"rm_{t}", help="클릭하여 삭제"):
                    remove_ticker(t)
                    st.rerun()
    else:
        st.caption("비어 있음. 아래에서 검색하여 추가하세요.")

    st.markdown("---")

    # -------------------------------------------------------------
    # 2. Search & Add Interface
    # -------------------------------------------------------------
    with col1:
        # Searchbox: Returns the selected value (ticker or raw input)
        # clear_on_submit=True ensures it resets after selection
        # Unique key forces reset when list changes, fixing the state persistence bug
        unique_key = f"ticker_search_{st.session_state.search_key_id}"

        new_selection = st_searchbox(
            search_tickers,
            key=unique_key,
            placeholder="티커(TSLA)나 이름(테슬라) 검색 또는 직접입력...",
            label="분석할 회사 검색 및 추가",
            clear_on_submit=True,
        )

        # Logic: If something is selected, add to state and rerun to update tags
        if new_selection:
            # Avoid duplicates
            if new_selection not in st.session_state.selected_tickers:
                st.session_state.selected_tickers.append(new_selection)
                # Increment key ID for the next render
                st.session_state.search_key_id += 1
                st.rerun()
            else:
                st.toast(f"이미 추가된 항목입니다: {new_selection}")

    with col2:
        st.markdown("<div style='margin-top: 29px'></div>", unsafe_allow_html=True)
        generate_btn = st.button(
            "📝 레포트 생성",
            type="primary",
            use_container_width=True,
            key="gen_btn_main",
        )

    # -------------------------------------------------------------
    # 3. Report Generation
    # -------------------------------------------------------------
    if generate_btn:
        final_list = st.session_state.selected_tickers
        if final_list:
            joined_tags = ", ".join(final_list)
            _handle_report_generation(joined_tags)
        else:
            st.warning("분석할 회사를 하나 이상 추가해주세요.")


def _handle_report_generation(ticker: str):
    """레포트 생성 처리 로직"""
    try:
        from rag.report_generator import ReportGenerator
        from ui.helpers.insights_helper import resolve_to_ticker

        generator = ReportGenerator()

        # UI에서 이미 정확한 티커를 선택했으므로 resolve 로직 필요성 감소하지만
        # 비교 분석(콤마 입력)을 수동으로 입력했을 경우 등을 대비해 유지
        if HELPERS_AVAILABLE:
            # resolve_tickers returns List[dict] {'ticker': ..., 'reason': ..., 'original': ...}
            resolved_results = resolve_tickers(ticker, resolve_to_ticker)

            tickers = []
            for item in resolved_results:
                t = item["ticker"]
                r = item.get("reason")
                orig = item.get("original")

                tickers.append(t)

                # Display reason if substitution happened via web search
                if r:
                    st.info(
                        f"ℹ️ **'{orig}'** → **'{t}'** 로 분석됩니다.\n   (이유: {r})"
                    )
        else:
            # Fallback (Legacy)
            if "," in ticker:
                raw_terms = [t.strip() for t in ticker.split(",") if t.strip()]
                tickers = [
                    resolve_to_ticker(t)[0] for t in raw_terms
                ]  # handle tuple return
            else:
                tickers = [resolve_to_ticker(ticker.strip())[0]]

        # 레포트 생성
        if HELPERS_AVAILABLE:
            report, file_prefix = generate_report_with_spinner(generator, tickers)
        else:
            if len(tickers) > 1:
                with st.spinner(f"⚖️ {', '.join(tickers)} 비교 분석 레포트 생성 중..."):
                    report = generator.generate_comparison_report(tickers)
                    file_prefix = f"comparison_{'_'.join(tickers)}"
            else:
                with st.spinner(f"📊 {tickers[0]} 분석 레포트 생성 중..."):
                    report = generator.generate_report(tickers[0])
                    file_prefix = f"{tickers[0]}_analysis_report"

        st.markdown("---")

        # 차트 렌더링
        chart_images = render_charts(tickers)

        # 레포트 표시
        st.markdown(report)

        # 다운로드 버튼
        if HELPERS_AVAILABLE:
            create_download_button(report, file_prefix, chart_images, create_pdf)
        else:
            try:
                pdf_bytes = create_pdf(report, chart_images=chart_images)
                st.download_button(
                    label="📥 레포트 다운로드 (PDF)",
                    data=pdf_bytes,
                    file_name=f"{file_prefix}.pdf",
                    mime="application/pdf",
                )
            except Exception as pdf_err:
                st.warning(f"PDF 생성 실패, Markdown으로 대체: {pdf_err}")
                st.download_button(
                    label="📥 레포트 다운로드 (MD)",
                    data=report.encode("utf-8"),
                    file_name=f"{file_prefix}.md",
                    mime="text/markdown",
                )

    except Exception as e:
        st.error(f"레포트 생성 실패: {e}")
