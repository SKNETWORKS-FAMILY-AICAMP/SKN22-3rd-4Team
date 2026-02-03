"""
Chart Rendering Helpers - 차트 렌더링 로직을 분리한 헬퍼 모듈
중복 코드 제거 및 유지보수성 향상
"""

from typing import List, Optional, Callable, Any
from io import BytesIO
import streamlit as st

# 차트 타입 설정 정의
CHART_CONFIGS = [
    {
        "key": "chart_line",
        "default": True,
        "plotly_func": "generate_line_chart_plotly",
        "mpl_func": "generate_line_chart",
    },
    {
        "key": "chart_candle",
        "default": False,
        "plotly_func": "generate_candlestick_chart_plotly",
        "mpl_func": "generate_candlestick_chart",
    },
    {
        "key": "chart_volume",
        "default": False,
        "plotly_func": "generate_volume_chart_plotly",
        "mpl_func": "generate_volume_chart",
    },
    {
        "key": "chart_financial",
        "default": False,
        "plotly_func": "generate_financial_chart_plotly",
        "mpl_func": "generate_financial_chart",
    },
]


def render_chart_selection():
    """차트 선택 옵션 렌더링"""
    st.markdown("### 📊 차트 선택")
    cols = st.columns(len(CHART_CONFIGS))
    for i, config in enumerate(CHART_CONFIGS):
        with cols[i]:
            st.checkbox(
                config["key"].replace("chart_", "").title(),
                value=config["default"],
                key=config["key"],
            )


def render_charts_plotly(
    tickers: List[str],
    plotly_funcs: dict,
    mpl_funcs: Optional[dict] = None,
) -> List[BytesIO]:
    """
    Plotly 차트 렌더링 및 PDF용 matplotlib 이미지 수집

    Args:
        tickers: 티커 목록
        plotly_funcs: Plotly 차트 생성 함수 딕셔너리
        mpl_funcs: Matplotlib 차트 생성 함수 딕셔너리 (PDF용)

    Returns:
        PDF용 차트 이미지 BytesIO 목록
    """
    chart_images = []

    for config in CHART_CONFIGS:
        if not st.session_state.get(config["key"], config["default"]):
            continue

        # Plotly 차트 표시
        plotly_func = plotly_funcs.get(config["plotly_func"])
        if plotly_func:
            fig = plotly_func(tickers)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

        # PDF용 matplotlib 이미지 생성
        if mpl_funcs:
            mpl_func = mpl_funcs.get(config["mpl_func"])
            if mpl_func:
                buf = mpl_func(tickers)
                if buf:
                    chart_images.append(buf)

    return chart_images


def render_charts_matplotlib(
    tickers: List[str],
    mpl_funcs: dict,
) -> List[BytesIO]:
    """
    Matplotlib 차트 렌더링 (Plotly 없을 때 fallback)

    Args:
        tickers: 티커 목록
        mpl_funcs: Matplotlib 차트 생성 함수 딕셔너리

    Returns:
        차트 이미지 BytesIO 목록
    """
    chart_images = []

    for config in CHART_CONFIGS:
        if not st.session_state.get(config["key"], config["default"]):
            continue

        mpl_func = mpl_funcs.get(config["mpl_func"])
        if mpl_func:
            buf = mpl_func(tickers)
            if buf:
                st.image(buf, use_container_width=True)
                buf.seek(0)
                chart_images.append(buf)

    return chart_images


def resolve_tickers(
    raw_input: str, resolver_func: Callable[[str], tuple[str, str | None]]
) -> List[dict]:
    """
    입력 문자열을 티커 정보 목록으로 변환

    Args:
        raw_input: 사용자 입력 (단일 또는 콤마 구분)
        resolver_func: 티커 해석 함수 (returns (ticker, reason))

    Returns:
        List[dict]: [{'ticker': 'MSFT', 'reason': '...'}, ...]
    """
    results = []

    if "," in raw_input:
        raw_terms = [t.strip() for t in raw_input.split(",") if t.strip()]
    else:
        raw_terms = [raw_input.strip()]

    for term in raw_terms:
        ticker, reason = resolver_func(term)
        results.append({"ticker": ticker, "reason": reason, "original": term})

    return results


def generate_report_with_spinner(
    generator,
    tickers: List[str],
) -> tuple:
    """
    레포트 생성 (단일/비교 자동 판별)

    Args:
        generator: ReportGenerator 인스턴스
        tickers: 티커 목록

    Returns:
        (report_text, file_prefix) 튜플
    """
    if len(tickers) > 1:
        with st.spinner(f"⚖️ {', '.join(tickers)} 비교 분석 레포트 생성 중..."):
            report = generator.generate_comparison_report(tickers)
            file_prefix = f"comparison_{'_'.join(tickers)}"
    else:
        ticker = tickers[0]
        with st.spinner(f"📊 {ticker} 분석 레포트 생성 중..."):
            report = generator.generate_report(ticker)
            file_prefix = f"{ticker}_analysis_report"

    return report, file_prefix


def create_download_button(
    report: str,
    file_prefix: str,
    chart_images: List[BytesIO],
    pdf_create_func: Callable,
) -> None:
    """
    다운로드 버튼 생성 (PDF 우선, 실패 시 Markdown)

    Args:
        report: 레포트 텍스트
        file_prefix: 파일명 접두사
        chart_images: 차트 이미지 목록
        pdf_create_func: PDF 생성 함수
    """
    try:
        pdf_bytes = pdf_create_func(report, chart_images=chart_images)
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


def render_stock_chart_fallback(tickers: List[str]) -> None:
    """
    Fallback: yfinance로 기본 Streamlit 차트 렌더링 (리스트 지원)
    """
    try:
        import yfinance as yf
        import pandas as pd
        from datetime import datetime, timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)

        chart_data = {}
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(start=start_date, end=end_date)
                if not hist.empty:
                    chart_data[ticker] = hist["Close"]
            except Exception:
                continue

        if chart_data:
            df = pd.DataFrame(chart_data)
            st.subheader("📈 주가 추이 (최근 3개월)")
            st.line_chart(df)

    except ImportError:
        st.warning(
            "차트를 표시하려면 yfinance 패키지가 필요합니다: `pip install yfinance`"
        )
    except Exception as e:
        st.warning(f"차트 로딩 실패: {e}")
