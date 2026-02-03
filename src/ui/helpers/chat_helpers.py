"""
Chat Display Helpers - 채팅 UI 렌더링 헬퍼

insights.py의 채팅 표시 로직을 분리하여 유지보수성 향상
Plotly 차트 사용으로 웹에서 선명한 벡터 그래픽 제공
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional

# Plotly 차트 로드
PLOTLY_AVAILABLE = False
try:
    from utils.plotly_charts import (
        create_line_chart,
        create_candlestick_chart,
        create_volume_chart,
        create_financial_chart,
    )

    PLOTLY_AVAILABLE = True
except ImportError:
    pass


def render_chart_from_data(chart_data: Dict) -> bool:
    """
    Tool Call로 받은 차트 데이터 Plotly로 렌더링

    Args:
        chart_data: {"c": [closes], "t": [timestamps], "ticker": "AAPL"}

    Returns:
        차트 렌더링 성공 여부
    """
    if not chart_data:
        return False

    if "c" not in chart_data or "t" not in chart_data:
        return False

    try:
        ticker = chart_data.get("ticker", "Stock")
        closes = chart_data["c"]
        timestamps = chart_data["t"]
        dates = [datetime.fromtimestamp(t) for t in timestamps]

        st.subheader(f"📈 {ticker} 주가 추이")

        if PLOTLY_AVAILABLE:
            # Plotly 사용 - 선명한 벡터 그래픽
            import plotly.graph_objects as go

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=closes,
                    mode="lines",
                    name=ticker,
                    line=dict(color="#2196F3", width=2),
                )
            )
            fig.update_layout(
                height=400,
                xaxis_title="날짜",
                yaxis_title="주가 (USD)",
                hovermode="x unified",
                template="plotly_white",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            # Fallback - Streamlit 기본 차트
            df = pd.DataFrame({"Date": dates, "Price": closes})
            df.set_index("Date", inplace=True)
            st.line_chart(df)

        st.caption(f"최근 {len(closes)}일/구간 데이터 ({ticker})")
        return True
    except Exception:
        return False


def render_chart_from_content(
    content: str,
    user_msg: str,
    chart_utils_available: bool,
    chart_funcs: Optional[Dict] = None,
) -> bool:
    """
    보고서/레포트 콘텐츠에서 Plotly 차트 자동 생성
    """
    import re

    # 보고서 키워드 확인
    has_report_keywords = any(
        k in content for k in ["분석 보고서", "레포트", "종합 분석"]
    )

    # 차트 키워드 확인
    chart_keywords = ["캔들", "거래량", "볼륨", "매출", "순이익", "재무", "차트"]
    has_chart_keywords = any(k in user_msg.lower() for k in chart_keywords)

    if not (has_report_keywords or has_chart_keywords):
        return False

    # 티커 추출
    match = re.search(r"\(([A-Z]{1,6})\)", content)
    if not match:
        return False

    ticker = match.group(1)

    # Plotly 차트 우선 사용
    if PLOTLY_AVAILABLE:
        return _render_plotly_chart(ticker, user_msg, chart_funcs)
    elif chart_utils_available and chart_funcs:
        return _render_chart_utils_fallback(ticker, user_msg, chart_funcs)
    else:
        return _render_yfinance_fallback(ticker)


def _render_plotly_chart(
    ticker: str, user_msg: str, chart_funcs: Optional[Dict]
) -> bool:
    """Plotly를 사용한 선명한 차트 렌더링"""
    try:
        # 차트 타입 감지
        chart_type = "line"  # 기본값
        if chart_funcs and "detect_chart_type" in chart_funcs:
            chart_type = chart_funcs["detect_chart_type"](user_msg)
        else:
            user_lower = user_msg.lower()
            if any(k in user_lower for k in ["캔들", "candlestick"]):
                chart_type = "candlestick"
            elif any(k in user_lower for k in ["거래량", "볼륨", "volume"]):
                chart_type = "volume"
            elif any(k in user_lower for k in ["재무", "매출", "순이익", "financial"]):
                chart_type = "financial"

        if chart_type == "candlestick":
            fig = create_candlestick_chart([ticker])
            if fig:
                st.subheader(f"📊 {ticker} 캔들스틱 차트")
                st.plotly_chart(fig, use_container_width=True)
                st.caption("※ 캔들스틱: 상승(초록), 하락(빨강)")
                return True

        elif chart_type == "volume":
            fig = create_volume_chart([ticker])
            if fig:
                st.subheader(f"📊 {ticker} 거래량 차트")
                st.plotly_chart(fig, use_container_width=True)
                st.caption("※ 거래량 추이")
                return True

        elif chart_type == "financial":
            fig = create_financial_chart([ticker])
            if fig:
                st.subheader(f"📊 {ticker} 분기별 재무 현황")
                st.plotly_chart(fig, use_container_width=True)
                st.caption("※ 분기별 매출액")
                return True
        else:
            # 기본 라인 차트
            fig = create_line_chart([ticker])
            if fig:
                st.subheader(f"📈 {ticker} 주가 추이 (3개월)")
                st.plotly_chart(fig, use_container_width=True)
                st.caption("※ 보고서 내용 기반 자동 생성 차트")
                return True

    except Exception:
        pass

    return False


def _render_chart_utils_fallback(ticker: str, user_msg: str, funcs: Dict) -> bool:
    """chart_utils(matplotlib)를 사용한 fallback 렌더링"""
    try:
        detect_chart_type = funcs.get("detect_chart_type")
        if not detect_chart_type:
            return False

        chart_type = detect_chart_type(user_msg)

        if chart_type == "candlestick":
            buf = funcs.get("generate_candlestick_chart")(ticker)
            if buf:
                st.subheader(f"📊 {ticker} 캔들스틱 차트")
                st.image(buf, use_container_width=True)
                st.caption("※ 캔들스틱: 상승(초록), 하락(빨강)")
                return True

        elif chart_type == "volume":
            buf = funcs.get("generate_volume_chart")(ticker)
            if buf:
                st.subheader(f"📊 {ticker} 거래량 차트")
                st.image(buf, use_container_width=True)
                st.caption("※ 거래량: 상승일(초록), 하락일(빨강)")
                return True

        elif chart_type == "financial":
            buf = funcs.get("generate_financial_chart")(ticker)
            if buf:
                st.subheader(f"📊 {ticker} 분기별 재무 현황")
                st.image(buf, use_container_width=True)
                st.caption("※ Revenue(파랑), Net Income(초록)")
                return True
        else:
            buf = funcs.get("generate_line_chart")([ticker])
            if buf:
                st.subheader(f"📈 {ticker} 주가 추이 (3개월)")
                st.image(buf, use_container_width=True)
                st.caption("※ 보고서 내용 기반 자동 생성 차트")
                return True

    except Exception:
        pass

    return False


def _render_yfinance_fallback(ticker: str) -> bool:
    """yfinance를 사용한 fallback 차트 렌더링"""
    try:
        import yfinance as yf

        end_d = datetime.now()
        start_d = end_d - pd.Timedelta(days=90)
        stock = yf.Ticker(ticker)
        hist = stock.history(start=start_d, end=end_d)

        if not hist.empty:
            st.subheader(f"📈 {ticker} 주가 추이 (3개월)")
            st.line_chart(hist["Close"])
            st.caption("※ 보고서 내용 기반 자동 생성 차트")
            return True
    except Exception:
        pass

    return False


def render_download_button(msg: Dict, index: int) -> None:
    """레포트 다운로드 버튼 렌더링"""
    if not msg.get("report"):
        return

    report_type = msg.get("report_type", "md")

    if report_type == "pdf":
        report_data = msg["report"]
        mime_type = "application/pdf"
        file_ext = "pdf"
        label = "📥 분석 레포트 다운로드 (PDF)"
    else:
        report_data = (
            msg["report"].encode("utf-8")
            if isinstance(msg["report"], str)
            else msg["report"]
        )
        mime_type = "text/markdown"
        file_ext = "md"
        label = "📥 분석 레포트 다운로드 (MD)"

    st.download_button(
        label=label,
        data=report_data,
        file_name=f"analysis_report_{index}.{file_ext}",
        mime=mime_type,
        key=f"chat_dl_{index}",
    )


def render_security_warning(error_code: Optional[str]) -> None:
    """보안 관련 경고 메시지 표시"""
    if not error_code:
        return

    if error_code == "INPUT_REJECTED":
        st.warning("⚠️ 입력이 보안 정책에 의해 필터링되었습니다.")
    elif error_code == "RATE_LIMITED":
        st.warning("⏱️ 요청 제한에 도달했습니다. 잠시 후 다시 시도하세요.")


def render_session_metrics(session_info: Optional[Dict]) -> None:
    """세션 정보 메트릭 표시"""
    msg_count = session_info.get("message_count", 0) if session_info else 0
    warnings = session_info.get("warnings", 0) if session_info else 0
    is_blocked = session_info.get("is_blocked", False) if session_info else False
    status = "🔴 차단" if is_blocked else "🟢 정상"

    cols = st.columns(3)
    with cols[0]:
        st.metric("💬 대화", msg_count)
    with cols[1]:
        st.metric("⚠️ 경고", warnings)
    with cols[2]:
        st.metric("상태", status)
