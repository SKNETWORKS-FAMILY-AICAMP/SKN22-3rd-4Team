"""
Investment insights page with AI Analyst Chatbot and Report Generator
ChatConnector 통합 - 프롬프트 인젝션 방어 및 세션 관리 포함

리팩토링: 차트 렌더링 로직을 chat_helpers.py로 분리
"""

import streamlit as st
import sys
from pathlib import Path
import uuid

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 헬퍼 함수 로드
from ui.helpers.insights_helper import (
    get_suggested_questions,
    render_disclaimer,
    render_page_css,
)

# 채팅 표시 헬퍼 로드
from ui.helpers.chat_helpers import (
    render_chart_from_data,
    render_chart_from_content,
    render_download_button,
    render_security_warning,
    render_session_metrics,
)

# 차트 유틸리티 로드 (다중 차트 지원)
CHART_FUNCS = {}
CHART_UTILS_AVAILABLE = False
try:
    from utils.chart_utils import (
        detect_chart_type,
        render_chart_streamlit,
        generate_candlestick_chart,
        generate_volume_chart,
        generate_financial_chart,
        generate_line_chart,
    )

    CHART_FUNCS = {
        "detect_chart_type": detect_chart_type,
        "generate_candlestick_chart": generate_candlestick_chart,
        "generate_volume_chart": generate_volume_chart,
        "generate_financial_chart": generate_financial_chart,
        "generate_line_chart": generate_line_chart,
    }
    CHART_UTILS_AVAILABLE = True
except ImportError:
    pass


def render():
    """Render the investment insights page"""
    try:
        from core.chat_connector import (
            ChatConnector,
            ChatRequest,
            get_chat_connector,
        )
        from core.input_validator import ThreatLevel

        render_chatbot_secure(
            ChatConnector, ChatRequest, get_chat_connector, ThreatLevel
        )

    except ImportError as e:
        st.error("모듈 로드 실패: ChatConnector를 사용할 수 없습니다.")
        st.info(f"에러 상세: {e}")
        st.info("pip install openai supabase 를 실행하세요")


def render_chatbot_secure(ChatConnector, ChatRequest, get_chat_connector, ThreatLevel):
    """Render AI Analyst Chatbot with ChatConnector (secure mode)"""
    render_page_css()

    # 세션 초기화
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())[:16]

    if "chat_connector" not in st.session_state:
        try:
            st.session_state.chat_connector = get_chat_connector(strict_mode=False)
        except Exception as e:
            st.error(f"ChatConnector 초기화 실패: {e}")
            return

    connector = st.session_state.chat_connector
    session_info = connector.get_session_info(st.session_state.session_id)

    # 헤더 렌더링
    _render_header(session_info)

    # 채팅 초기화
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # 채팅 히스토리 표시
    _render_chat_history()

    # 추천 질문
    _render_suggested_questions()

    # 채팅 입력
    prompt = _render_chat_input()

    # 컨트롤 버튼
    _render_control_buttons(connector)

    # 메시지 처리
    if prompt:
        _process_message(prompt, connector, ChatRequest)

    render_disclaimer()


def _render_header(session_info):
    """헤더 및 세션 정보 렌더링"""
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.markdown(
            '<h1 class="main-header">📊 투자 인사이트</h1>', unsafe_allow_html=True
        )

    with right_col:
        st.markdown("### 🤖 AI 금융 애널리스트")
        render_session_metrics(session_info)


def _render_chat_history():
    """채팅 히스토리 렌더링"""
    if not st.session_state.chat_history:
        return

    chat_container = st.container(height=800)
    with chat_container:
        for i, msg in enumerate(st.session_state.chat_history):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

                # 보안 경고
                render_security_warning(msg.get("error_code"))

                # 차트 렌더링
                _render_message_chart(msg, i)

                # 다운로드 버튼
                render_download_button(msg, i)


def _render_message_chart(msg, index):
    """메시지에 포함된 차트 렌더링"""
    chart_rendered = False

    # 1. Tool Call 차트 데이터
    if msg.get("chart_data"):
        chart_rendered = render_chart_from_data(msg["chart_data"])

    # 2. 콘텐츠 기반 차트 생성
    if not chart_rendered and msg["role"] == "assistant":
        content_str = str(msg.get("content", ""))
        user_msg = ""
        if index > 0 and st.session_state.chat_history[index - 1]["role"] == "user":
            user_msg = st.session_state.chat_history[index - 1]["content"]

        render_chart_from_content(
            content_str,
            user_msg,
            CHART_UTILS_AVAILABLE,
            CHART_FUNCS if CHART_UTILS_AVAILABLE else None,
        )


def _render_suggested_questions():
    """추천 질문 렌더링"""
    if not st.session_state.get("chat_history"):
        return

    st.markdown("#### 💡 추천 질문")
    suggested_questions = get_suggested_questions()
    msg_count = len(st.session_state.chat_history)

    cols = st.columns(2)
    for i, question in enumerate(suggested_questions):
        # Key unique to message count to avoid stale buttons
        with cols[i % 2]:
            if st.button(
                f"💬 {question}",
                key=f"suggest_{msg_count}_{i}",
                use_container_width=True,
            ):
                # pending_question을 설정하여 _render_chat_input에서 반환하고 바로 처리되도록 함
                st.session_state["pending_question"] = question
                # 입력창 비우기 (질문이 입력창에 남지 않도록)
                st.session_state["chat_input_field"] = ""
                st.rerun()


def _render_chat_input():
    """채팅 입력 폼 렌더링"""
    with st.form(key="chat_form", clear_on_submit=True):
        input_col, send_col = st.columns([6, 1])

        with input_col:
            user_input = st.text_input(
                "질문 입력",
                placeholder="관심 있는 기업이나 시장에 대해 물어보세요 (예: 애플 실적 분석해줘, 엔비디아와 테슬라 비교)",
                label_visibility="collapsed",
                key="chat_input_field",
            )

        with send_col:
            submitted = st.form_submit_button("📤", use_container_width=True)

    pending = st.session_state.pop("pending_question", None)

    if pending:
        return pending
    elif submitted and user_input.strip():
        return user_input.strip()
    return None


def _render_control_buttons(connector):
    """컨트롤 버튼 렌더링"""
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🗑️ 대화 초기화", use_container_width=True):
            st.session_state.chat_history = []
            connector.clear_session(st.session_state.session_id)
            st.rerun()

    with col2:
        if st.button("🔄 세션 새로고침", use_container_width=True):
            st.session_state.session_id = str(uuid.uuid4())[:16]
            st.session_state.chat_history = []
            st.rerun()


def _process_message(prompt, connector, ChatRequest):
    """메시지 처리 및 응답 생성"""
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    try:
        with st.spinner("분석 중... (시간이 걸릴 수 있습니다)"):
            request = ChatRequest(
                session_id=st.session_state.session_id,
                message=prompt,
                use_rag=True,
            )
            response = connector.process_message(request)

        if response.success:
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": response.content,
                    "report": response.report,
                    "report_type": response.report_type,
                    "chart_data": response.chart_data,
                    "recommendations": response.recommendations,
                }
            )
        else:
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": response.content,
                    "error_code": response.error_code,
                }
            )

        st.rerun()

    except Exception as e:
        st.error(f"응답 생성 실패: {e}")
