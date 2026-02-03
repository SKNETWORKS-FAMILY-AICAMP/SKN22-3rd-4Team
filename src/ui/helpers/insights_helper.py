"""
Insights 페이지 헬퍼 함수 모듈
화면단에서 분리된 유틸리티 함수들
"""

import streamlit as st


# 기업명 매핑 테이블
COMPANY_MAP = {
    "apple": "AAPL",
    "aapl": "AAPL",
    "애플": "AAPL",
    "tesla": "TSLA",
    "tsla": "TSLA",
    "테슬라": "TSLA",
    "nvidia": "NVDA",
    "nvda": "NVDA",
    "엔비디아": "NVDA",
    "microsoft": "MSFT",
    "msft": "MSFT",
    "마이크로소프트": "MSFT",
    "google": "GOOGL",
    "googl": "GOOGL",
    "구글": "GOOGL",
    "알파벳": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "amzn": "AMZN",
    "아마존": "AMZN",
    "meta": "META",
    "메타": "META",
    "페이스북": "META",
    "netflix": "NFLX",
    "넷플릭스": "NFLX",
}


def resolve_to_ticker(term: str) -> tuple[str, str | None]:
    """한글명이나 영문명을 티커로 변환 (공용 함수)

    Returns:
        tuple: (ticker, reason)
        reason은 웹 검색으로 찾은 경우에만 제공됨 (UI 표시용)
    """
    term = term.strip()

    # 이미 티커 형식이면 반환
    if term.isupper() and term.isalpha() and len(term) <= 5:
        return term, None

    # 매핑 테이블에서 검색
    lower_term = term.lower()
    if lower_term in COMPANY_MAP:
        return COMPANY_MAP[lower_term], None

    # DB에서 검색 (lazy import)
    try:
        from src.data.supabase_client import SupabaseClient

        df = SupabaseClient.search_companies(term)
        if df is not None and not df.empty:
            return df.iloc[0]["ticker"], None
    except Exception:
        pass

    # [NEW] Web Search for Unknown Tickers (Tavily)
    try:
        from src.utils.ticker_search_agent import find_ticker_from_web

        # Only search if it looks like a potential company name (not too long)
        if len(term) < 20:
            found_ticker, reason = find_ticker_from_web(term)
            if found_ticker != "UNKNOWN":
                return found_ticker, reason
    except Exception as e:
        print(f"Web search failed: {e}")

    return term.upper(), None


def extract_ticker_from_context(context: str) -> str | None:
    """대화 내용에서 기업명/티커 추출"""
    context_lower = context.lower()
    for keyword, ticker in COMPANY_MAP.items():
        if keyword in context_lower:
            return ticker
    return None


def analyze_discussed_topics(context: str) -> set:
    """대화에서 이미 다룬 주제 분석"""
    context_lower = context.lower()
    discussed_topics = set()

    topic_keywords = {
        "price": ["주가", "가격", "price", "시세", "현재가"],
        "target": ["목표", "target", "전망"],
        "earnings": ["실적", "매출", "revenue", "수익", "이익"],
        "chart": ["차트", "chart", "추이", "그래프"],
        "strategy": ["투자", "전략", "매수", "사도"],
        "compare": ["비교", "경쟁", "vs"],
        "report": ["보고서", "리포트", "pdf"],
    }

    for topic, keywords in topic_keywords.items():
        if any(word in context_lower for word in keywords):
            discussed_topics.add(topic)

    return discussed_topics


def get_last_messages() -> tuple[str, str]:
    """마지막 사용자 질문과 AI 응답 추출"""
    chat_history = st.session_state.get("chat_history", [])

    last_user_msg = ""
    last_ai_msg = ""

    for msg in reversed(chat_history):
        if msg["role"] == "user" and not last_user_msg:
            last_user_msg = msg["content"]
        elif msg["role"] == "assistant" and not last_ai_msg:
            last_ai_msg = msg["content"]
        if last_user_msg and last_ai_msg:
            break

    return last_user_msg, last_ai_msg


def get_suggested_questions() -> list[str]:
    """대화 기록 기반 동적 추천 질문 생성"""
    if not st.session_state.get("chat_history"):
        return []

    # 1. AI가 생성한 추천 검색어가 있으면 우선 사용
    last_msg = st.session_state["chat_history"][-1]
    if last_msg["role"] == "assistant" and last_msg.get("recommendations"):
        return last_msg["recommendations"][:4]

    # 2. 없으면 기존 로직(대화 분석) 사용
    last_user_msg, last_ai_msg = get_last_messages()
    context = f"{last_user_msg} {last_ai_msg}"

    # 기업명 추출
    ticker_str = extract_ticker_from_context(context)

    # 이미 다룬 주제 파악
    discussed_topics = analyze_discussed_topics(context)

    suggestions = []

    if ticker_str:
        # 해당 기업 관련 후속 질문 (아직 안 다룬 주제만)
        topic_questions = {
            "price": f"{ticker_str} 현재 주가는?",
            "target": f"{ticker_str} 목표가는?",
            "earnings": f"{ticker_str} 실적 요약해줘",
            "chart": f"{ticker_str} 차트 보여줘",
            "strategy": f"{ticker_str} 투자 전략은?",
            "compare": f"{ticker_str} 경쟁사 비교해줘",
            "report": f"{ticker_str} 보고서 만들어줘",
        }

        for topic, question in topic_questions.items():
            if topic not in discussed_topics:
                suggestions.append(question)
    else:
        # 기업명이 없으면 기업 지정 유도
        suggestions = [
            "애플 분석해줘",
            "테슬라 주가 알려줘",
            "엔비디아 실적 요약해줘",
            "마이크로소프트 등록해줘",
        ]

    return suggestions[:4]


def render_disclaimer():
    """면책 조항 렌더링"""
    st.markdown(
        "<div style='text-align: center; color: #888; font-size: 0.75rem; padding: 1rem 0; margin-top: 2rem;'>"
        "📌 본 정보는 투자 참고용이며, 특정 종목의 매수/매도를 권유하는 것이 아닙니다. "
        "투자에 대한 최종 결정과 책임은 투자자 본인에게 있습니다."
        "</div>",
        unsafe_allow_html=True,
    )


def render_page_css():
    """페이지 CSS 스타일 렌더링"""
    st.markdown(
        """
        <style>
            /* 페이지 로드 시 자동 스크롤 방지 */
            [data-testid="stChatInput"] textarea {
                scroll-margin-top: 100vh;
            }
            /* 첫 로드 시 맨 위 유지 */
            html {
                scroll-behavior: auto !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
