import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# PLOTLY_AVAILABLE check is handled by imports, assuming environment has it or we handle exceptions carefully.
# But distinct boolean is useful for fallback.
try:
    import plotly.express as px
    import plotly.graph_objects as go

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


def format_number(value, unit=""):
    """숫자 포맷팅 (억 단위)"""
    if pd.isna(value) or value is None:
        return "-"

    if abs(value) >= 1e12:
        return f"${value/1e12:.1f}조{unit}"
    elif abs(value) >= 1e9:
        return f"${value/1e9:.1f}B{unit}"
    elif abs(value) >= 1e6:
        return f"${value/1e6:.1f}M{unit}"
    else:
        return f"${value:,.0f}{unit}"


def render_plotly_bar_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str):
    """Plotly 바 차트 렌더링"""
    if not PLOTLY_AVAILABLE:
        st.bar_chart(df.set_index(x_col)[y_col])
        return

    fig = px.bar(
        df,
        x=x_col,
        y=y_col,
        title=title,
        text_auto=".2s",
        color=y_col,
        color_continuous_scale="Viridis",
    )
    fig.update_layout(xaxis_title="", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)


def render_plotly_pie_chart(series: pd.Series, title: str):
    """Plotly 파이 차트 렌더링"""
    if not PLOTLY_AVAILABLE:
        st.write(series)
        return

    df = series.reset_index()
    df.columns = ["label", "value"]

    fig = px.pie(df, values="value", names="label", title=title, hole=0.4)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)


def render_exchange_rates(rates: dict, update_time: str = None):
    """환율 정보 렌더링"""
    if not rates:
        return

    # 환율 정보 표시 (Ticker 스타일)
    cols = st.columns(len(rates))
    for i, (name, rate) in enumerate(rates.items()):
        with cols[i]:
            # 데이터 타입에 따른 안전한 처리
            if isinstance(rate, dict):
                price = rate.get("price", 0)
                change = rate.get("change", 0)
                st.metric(
                    label=name,
                    value=f"{price:,.2f}",
                    delta=f"{change:.2f}%",
                    delta_color="normal" if change >= 0 else "inverse",
                )
            elif isinstance(rate, (float, int)):
                st.metric(
                    label=name,
                    value=f"{rate:,.2f}",
                )
            else:
                # 문자열 등 그대로 표시
                st.metric(
                    label=name,
                    value=str(rate),
                )

    if update_time:
        st.caption(f"🕒 기준 시간: {update_time}")
    st.markdown("---")


def render_metric_cards(company_count):
    """메트릭 카드 렌더링"""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(label="📈 등록된 기업", value=f"{company_count}개")

    with col2:
        # Placeholder or real dynamic data
        st.metric(label="💵 평균 시가총액", value="$1.2T", delta="+2.5%")

    with col3:
        st.metric(label="📊 평균 PER", value="24.5", delta="-0.8%")

    with col4:
        st.metric(label="📅 실적 발표 예정", value="5개", delta="이번주")


def render_top_companies_tab(supabase_available: bool, company_count: int):
    """매출 상위 기업 탭"""
    # Circular import prevention
    from data.supabase_client import get_top_revenue_companies

    st.markdown("### 📊 2025년 매출 상위 20개 기업")

    if supabase_available and company_count > 0:
        try:
            top_df = get_top_revenue_companies(year=2025, limit=20)

            if not top_df.empty:
                # 데이터 포맷팅
                display_df = top_df[
                    ["ticker", "company_name", "revenue", "net_income", "total_assets"]
                ].copy()
                display_df.columns = ["티커", "기업명", "매출", "순이익", "총자산"]

                display_df["매출"] = display_df["매출"].apply(format_number)
                display_df["순이익"] = display_df["순이익"].apply(format_number)
                display_df["총자산"] = display_df["총자산"].apply(format_number)

                st.dataframe(display_df, use_container_width=True, hide_index=True)

                # Plotly 바 차트
                st.markdown("### 📈 매출 비교 차트")
                chart_df = top_df[["ticker", "revenue"]].dropna().head(10).copy()
                chart_df["revenue"] = chart_df["revenue"] / 1e9  # 십억 달러 단위

                render_plotly_bar_chart(
                    chart_df,
                    x_col="ticker",
                    y_col="revenue",
                    title="매출 상위 10개 기업 (십억 USD)",
                )
            else:
                st.info("2025년 데이터가 아직 없습니다.")
        except Exception as e:
            st.error(f"데이터 로드 오류: {e}")
    else:
        st.info("Supabase에 연결하여 데이터를 확인하세요.")


def render_search_tab(supabase_available: bool, SupabaseClient, toggle_callback):
    """기업 검색 탭"""
    st.markdown("### 🔍 기업 검색")

    if "search_query" not in st.session_state:
        st.session_state.search_query = ""

    def update_search():
        st.session_state.search_query = st.session_state.search_input

    search_query = st.text_input(
        "티커 또는 기업명으로 검색",
        placeholder="예: AAPL, Apple, Microsoft",
        value=st.session_state.search_query,
        key="search_input",
        on_change=update_search,
    )

    if search_query and supabase_available and SupabaseClient:
        try:
            results = SupabaseClient.search_companies(search_query)

            if not results.empty:
                st.success(f"{len(results)}개 기업 검색됨")

                for _, company in results.iterrows():
                    col_exp, col_star = st.columns([10, 1])
                    ticker = company["ticker"]
                    is_watched = ticker in st.session_state.watchlist

                    with col_star:
                        btn_label = "⭐" if is_watched else "☆"
                        st.button(
                            btn_label,
                            key=f"star_search_{ticker}",
                            help="관심 기업 추가/제거",
                            on_click=toggle_callback,
                            args=(ticker,),
                        )

                    with col_exp:
                        with st.expander(
                            f"📊 {company['ticker']} - {company['company_name']}"
                        ):
                            financials = SupabaseClient.get_financial_summary(
                                company["ticker"]
                            )

                            if financials and financials.get("annual_reports"):
                                reports = financials["annual_reports"]
                                c1, c2, c3 = st.columns(3)
                                latest = reports[0] if reports else {}

                                with c1:
                                    st.metric(
                                        "매출", format_number(latest.get("revenue"))
                                    )
                                with c2:
                                    st.metric(
                                        "순이익",
                                        format_number(latest.get("net_income")),
                                    )
                                with c3:
                                    st.metric(
                                        "총자산",
                                        format_number(latest.get("total_assets")),
                                    )

                                reports_df = pd.DataFrame(reports)
                                if not reports_df.empty:
                                    display_cols = [
                                        "fiscal_year",
                                        "revenue",
                                        "net_income",
                                        "eps",
                                    ]
                                    available_cols = [
                                        c
                                        for c in display_cols
                                        if c in reports_df.columns
                                    ]
                                    st.dataframe(
                                        reports_df[available_cols], hide_index=True
                                    )
                            else:
                                st.info("재무 데이터가 없습니다.")
            else:
                st.warning("검색 결과가 없습니다.")
        except Exception as e:
            st.error(f"검색 오류: {e}")


def render_db_status_tab(
    supabase_available: bool, companies_df: pd.DataFrame, company_count: int
):
    """DB 현황 탭"""
    st.markdown("### 💾 데이터베이스 현황")

    if supabase_available and company_count > 0:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**등록된 기업 (일부)**")
            if not companies_df.empty:
                st.dataframe(
                    companies_df[["ticker", "company_name"]].head(10),
                    hide_index=True,
                    use_container_width=True,
                )

        with col2:
            st.markdown("**섹터별 분포**")
            if (
                "sector" in companies_df.columns
                and companies_df["sector"].notna().any()
            ):
                sector_counts = companies_df["sector"].value_counts()

                # 유효하지 않은 섹터 필터링
                valid_sectors = [
                    s
                    for s in sector_counts.index
                    if s
                    and not str(s).strip().isdigit()
                    and str(s).strip() != "11"
                    and str(s).lower() != "nan"
                ]
                sector_counts = sector_counts[valid_sectors]

                # Plotly 파이 차트
                if not sector_counts.empty:
                    render_plotly_pie_chart(sector_counts, title="섹터별 기업 분포")
                else:
                    st.info("유효한 섹터 정보가 없습니다.")
            else:
                st.info("섹터 정보가 아직 없습니다.")
    else:
        st.info("데이터베이스에 연결되지 않았거나 데이터가 없습니다.")


def render_quick_start_tab():
    """빠른 시작 가이드 탭"""
    st.markdown("### 💡 빠른 시작 가이드")
    st.markdown(
        """
#### 🎯 주요 기능 안내

**1. 📊 홈 (Home)**
- **매출 상위 기업**: 2024년 기준 매출 Top 20 기업의 재무 현황 조회
- **기업 검색**: 티커/기업명으로 검색 및 관심 기업 등록
- **DB 현황**: 수집된 데이터 및 섹터별 분포 확인

**2. 📝 레포트 생성 (Reports)**
- **AI 투자 레포트**: 특정/복수 기업에 대한 심층 분석 보고서 생성
- **비교 분석**: 여러 경쟁사를 동시에 비교 분석 (최대 3개 권장)
- **차트 포함**: 주가, 거래량, 재무 차트가 포함된 PDF 레포트 다운로드

**3. 🤖 투자 인사이트 (Insights)**
- **AI 애널리스트**: 챗봇과 대화하며 투자 궁금증 해결
- **실시간 데이터**: "애플 주가 어때?", "테슬라 재무 보여줘" 등 자연어 질문
- **맞춤형 분석**: 사용자의 관심사에 맞춘 투자 조언 제공

**4. 🗓️ 실적 캘린더 (Calendar)**
- **관심 기업 일정**: 내가 등록한 관심 기업의 실적 발표일 확인
- **시장 예측**: EPS 예상치와 실제 발표치(Surprise) 비교
    """
    )
