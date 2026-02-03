"""
Chart Utilities - 최적화된 차트 생성 모듈
- Streamlit 캐싱으로 중복 데이터 요청 방지
- 데이터 fetching과 렌더링 분리
- 한글 차트 제목 지원
- 비교 분석용 멀티 티커 지원
"""

import logging
from io import BytesIO
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from functools import lru_cache

# 스타일 설정
import matplotlib.style as mpl_style

try:
    mpl_style.use("seaborn-v0_8-whitegrid")
except Exception:
    pass

logger = logging.getLogger(__name__)

# 색상 팔레트 (Professional)
COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
UP_COLOR = "#00C805"  # Bright Green (Rising)
DOWN_COLOR = "#FF333A"  # Bright Red (Falling)
GRID_COLOR = "#E0E0E0"

# ============================================================
# 🔧 DATA FETCHING LAYER (캐싱 적용)
# ============================================================


@lru_cache(maxsize=50)
def _fetch_stock_history(ticker: str, days: int) -> Optional[Tuple]:
    """주가 데이터 캐싱"""
    try:
        import yfinance as yf

        end_d = datetime.now()
        start_d = end_d - timedelta(days=days)
        stock = yf.Ticker(ticker)
        df = stock.history(start=start_d, end=end_d)
        if df.empty:
            return None
        return (
            tuple(df.index.tolist()),
            tuple(df["Open"].tolist()),
            tuple(df["High"].tolist()),
            tuple(df["Low"].tolist()),
            tuple(df["Close"].tolist()),
            tuple(df["Volume"].tolist()),
        )
    except Exception as e:
        logger.warning(f"Stock data fetch failed for {ticker}: {e}")
        return None


@lru_cache(maxsize=20)
def _fetch_quarterly_financials(ticker: str) -> Optional[Tuple]:
    """분기별 재무 데이터 캐싱"""
    try:
        import yfinance as yf

        stock = yf.Ticker(ticker)
        quarterly = stock.quarterly_financials
        if quarterly.empty:
            return None

        revenue_row = net_income_row = None
        for idx in quarterly.index:
            idx_lower = str(idx).lower()
            if "revenue" in idx_lower or "total revenue" in idx_lower:
                revenue_row = idx
            if "net income" in idx_lower:
                net_income_row = idx

        if revenue_row is None:
            return None

        quarters = quarterly.columns[:8][::-1]
        revenue = quarterly.loc[revenue_row, quarters].values / 1e9
        net_income = (
            quarterly.loc[net_income_row, quarters].values / 1e9
            if net_income_row
            else None
        )
        quarter_labels = tuple(
            q.strftime("%Y Q").replace("Q", f"Q{(q.month-1)//3+1}") for q in quarters
        )
        return (
            quarter_labels,
            tuple(revenue),
            tuple(net_income) if net_income is not None else None,
        )
    except Exception as e:
        logger.warning(f"Financial data fetch failed for {ticker}: {e}")
        return None


def clear_cache():
    """모든 캐시 초기화"""
    _fetch_stock_history.cache_clear()
    _fetch_quarterly_financials.cache_clear()


# ============================================================
# 📊 CHART RENDERING LAYER (한글 제목 + 비교 지원)
# ============================================================


def _setup_matplotlib():
    """matplotlib 백엔드 및 한글 폰트 설정"""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # 한글 폰트 설정 시도
    try:
        from matplotlib import font_manager
        import platform

        if platform.system() == "Windows":
            plt.rcParams["font.family"] = "Malgun Gothic"
        elif platform.system() == "Darwin":
            plt.rcParams["font.family"] = "AppleGothic"
        else:
            plt.rcParams["font.family"] = "NanumGothic"

        plt.rcParams["axes.unicode_minus"] = False
    except Exception:
        pass  # 폰트 없으면 기본 사용

    return plt


def generate_line_chart(tickers: List[str], days: int = 180) -> Optional[BytesIO]:
    """Stock Price Line Chart (Improved Layout)"""
    try:
        if isinstance(tickers, str):
            tickers = [tickers]

        plt = _setup_matplotlib()
        fig, ax = plt.subplots(figsize=(10, 5))

        has_data = False
        for i, ticker in enumerate(tickers):
            data = _fetch_stock_history(ticker, days)
            if data:
                dates, _, _, _, closes, _ = data
                color = COLORS[i % len(COLORS)]
                # Add Shadow/Glow effect by plotting lines twice if possible, or just thicker line
                ax.plot(
                    dates,
                    closes,
                    label=f"{ticker}",
                    linewidth=2,
                    color=color,
                    alpha=0.9,
                )
                ax.fill_between(
                    dates, closes, min(closes), color=color, alpha=0.1
                )  # Area under curve
                has_data = True

        if not has_data:
            plt.close(fig)
            return None

        title = (
            f"주가 추이 ({', '.join(tickers)})"
            if len(tickers) > 1
            else f"{tickers[0]} 주가 추이 (최근 {days}일)"
        )
        ax.set_title(title, fontsize=16, fontweight="bold", pad=20)
        ax.set_ylabel("가격 (USD)", fontsize=12)
        ax.legend(loc="upper left", frameon=True, fontsize=10)
        ax.grid(True, color=GRID_COLOR, linestyle="-", linewidth=0.5)

        # Remove top and right spines
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        fig.autofmt_xdate()
        plt.tight_layout()

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
        buf.seek(0)
        plt.close(fig)
        return buf
    except Exception as e:
        logger.warning(f"Line chart failed: {e}")
        return None


def generate_candlestick_chart(tickers: List[str], days: int = 60) -> Optional[BytesIO]:
    """Candlestick Chart (Improved Layout)"""
    try:
        if isinstance(tickers, str):
            tickers = [tickers]

        plt = _setup_matplotlib()
        from matplotlib.patches import Rectangle

        n_tickers = len(tickers)
        # Dynamic height based on number of tickers
        fig, axes = plt.subplots(
            n_tickers, 1, figsize=(12, 6 * n_tickers), squeeze=False
        )
        has_any_data = False

        for idx, ticker in enumerate(tickers):
            ax = axes[idx, 0]
            data = _fetch_stock_history(ticker, days)

            if not data:
                continue

            has_any_data = True
            dates, opens, highs, lows, closes, volumes = data

            # Draw Candles
            width = 0.6
            width2 = 0.1

            for i in range(len(dates)):
                open_p, high, low, close = opens[i], highs[i], lows[i], closes[i]
                color = UP_COLOR if close >= open_p else DOWN_COLOR

                # High-Low Line
                ax.plot([i, i], [low, high], color=color, linewidth=1)

                # Open-Close Body
                body_bottom = min(open_p, close)
                body_height = abs(close - open_p)
                if body_height == 0:
                    body_height = 0.01

                rect = Rectangle(
                    (i - width / 2, body_bottom),
                    width,
                    body_height,
                    facecolor=color,
                    edgecolor=color,
                )
                ax.add_patch(rect)

            # Settings
            ax.set_title(
                f"{ticker} 캔들스틱 (최근 {days}일)",
                fontsize=14,
                fontweight="bold",
                pad=10,
            )
            ax.set_ylabel("주가 (USD)")
            ax.grid(True, color=GRID_COLOR, linestyle="--", linewidth=0.5)
            ax.set_xlim(-1, len(dates))

            # X-axis formatting
            step = max(1, len(dates) // 8)
            tick_pos = list(range(0, len(dates), step))
            ax.set_xticks(tick_pos)
            ax.set_xticklabels(
                [dates[i].strftime("%m/%d") for i in tick_pos], rotation=0
            )

        if not has_any_data:
            plt.close(fig)
            return None

        plt.tight_layout()
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
        buf.seek(0)
        plt.close(fig)
        return buf
    except Exception as e:
        logger.warning(f"Candlestick chart failed: {e}")
        return None


def generate_volume_chart(tickers: List[str], days: int = 60) -> Optional[BytesIO]:
    """Trading Volume Chart (comparison: overlay lines)"""
    try:
        # 단일 티커 문자열이 들어올 경우 리스트로 변환
        if isinstance(tickers, str):
            tickers = [tickers]

        plt = _setup_matplotlib()
        fig, ax = plt.subplots(figsize=(10, 4))  # PDF용 컴팩트 사이즈
        has_data = False

        for i, ticker in enumerate(tickers):
            data = _fetch_stock_history(ticker, days)
            if not data:
                continue

            has_data = True
            dates, _, _, _, _, volumes = data
            color = COLORS[i % len(COLORS)]

            # 라인 차트로 비교용 거래량 표시
            ax.plot(
                range(len(dates)),
                [v / 1e6 for v in volumes],
                label=ticker,
                linewidth=1.5,
                color=color,
                alpha=0.8,
            )

        if not has_data:
            plt.close(fig)
            return None

        # X축 설정
        if data:
            n = len(dates)
            step = max(1, n // 8)
            tick_pos = list(range(0, n, step))
            ax.set_xticks(tick_pos)
            ax.set_xticklabels(
                [dates[i].strftime("%m/%d") for i in tick_pos], rotation=45, fontsize=8
            )

        title = (
            f"거래량 비교 ({', '.join(tickers)})"
            if len(tickers) > 1
            else f"{tickers[0]} 거래량"
        )
        ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
        ax.set_ylabel("거래량 (백만)", fontsize=11)
        ax.legend(loc="upper right", fontsize=10)
        ax.grid(True, alpha=0.3, linestyle="--")

        # Title 잘림 방지
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=300, facecolor="white")
        buf.seek(0)
        plt.close(fig)
        return buf
    except Exception as e:
        logger.warning(f"Volume chart failed: {e}")
        return None


def generate_financial_chart(tickers: List[str]) -> Optional[BytesIO]:
    """Quarterly Financial Chart (comparison: grouped bars)"""
    try:
        # 단일 티커 문자열이 들어올 경우 리스트로 변환
        if isinstance(tickers, str):
            tickers = [tickers]

        plt = _setup_matplotlib()
        import numpy as np

        # 데이터 수집
        all_data = {}
        for ticker in tickers:
            data = _fetch_quarterly_financials(ticker)
            if data:
                all_data[ticker] = data

        if not all_data:
            return None

        # 공통 분기 수 결정 (가장 적은 분기 수 사용)
        min_quarters = min(len(data[0]) for data in all_data.values())

        # 첫 번째 티커의 분기 레이블 사용 (공통 분기 수만큼)
        first_ticker = list(all_data.keys())[0]
        quarter_labels = all_data[first_ticker][0][:min_quarters]
        n_quarters = len(quarter_labels)
        n_tickers = len(all_data)

        fig, ax = plt.subplots(figsize=(10, 4))  # PDF용 컴팩트 사이즈
        x = np.arange(n_quarters)
        width = 0.8 / n_tickers  # 티커 수에 따라 막대 너비 조정

        for i, (ticker, (_, revenue, _)) in enumerate(all_data.items()):
            # 분기 수 맞추기
            revenue_trimmed = revenue[:min_quarters]
            offset = (i - n_tickers / 2 + 0.5) * width
            color = COLORS[i % len(COLORS)]
            ax.bar(
                x + offset, revenue_trimmed, width, label=ticker, color=color, alpha=0.8
            )

        ax.set_xticks(x)
        ax.set_xticklabels(quarter_labels, rotation=45, ha="right", fontsize=9)

        title = (
            f"분기별 매출 비교 ({', '.join(tickers)})"
            if n_tickers > 1
            else f"{first_ticker} 분기별 매출"
        )
        ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
        ax.set_ylabel("매출 (십억 USD)", fontsize=11)
        ax.legend(loc="upper left", fontsize=10)
        ax.grid(True, alpha=0.3, axis="y", linestyle="--")

        # Title 잘림 방지
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=300, facecolor="white")
        buf.seek(0)
        plt.close(fig)
        return buf
    except Exception as e:
        logger.warning(f"Financial chart failed: {e}")
        return None


# ============================================================
# 🔍 UTILITY FUNCTIONS
# ============================================================


def detect_chart_type(user_input: str) -> str:
    """사용자 입력에서 차트 타입 감지"""
    text = user_input.lower()
    if any(kw in text for kw in ["캔들", "캔들스틱", "candlestick", "candle"]):
        return "candlestick"
    if any(kw in text for kw in ["거래량", "볼륨", "volume", "매매량"]):
        return "volume"
    if any(
        kw in text
        for kw in ["매출", "순이익", "재무", "revenue", "income", "financial", "실적"]
    ):
        return "financial"
    return "line"


def render_chart_streamlit(chart_type: str, ticker: str, tickers: List[str] = None):
    """Streamlit에서 차트 렌더링"""
    import streamlit as st

    ticker_list = tickers or [ticker]

    if chart_type == "candlestick":
        buf = generate_candlestick_chart(ticker_list)
        if buf:
            st.image(buf, use_container_width=True)
    elif chart_type == "volume":
        buf = generate_volume_chart(ticker_list)
        if buf:
            st.image(buf, use_container_width=True)
    elif chart_type == "financial":
        buf = generate_financial_chart(ticker_list)
        if buf:
            st.image(buf, use_container_width=True)
    else:  # line
        buf = generate_line_chart(ticker_list)
        if buf:
            st.image(buf, use_container_width=True)
