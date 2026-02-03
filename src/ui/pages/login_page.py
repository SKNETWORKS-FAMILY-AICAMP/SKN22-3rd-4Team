import streamlit as st
import time
import json
from datetime import datetime
from data.supabase_client import SupabaseClient
from streamlit_javascript import st_javascript


def save_session_to_local_storage(email: str, user_id: str):
    """JavaScript를 사용하여 localStorage에 세션 저장"""
    session_data = {
        "email": email,
        "id": user_id,
        "timestamp": datetime.now().isoformat()
    }
    session_json = json.dumps(session_data)
    st_javascript(f"localStorage.setItem('stock_bot_session', '{session_json}')")


def render(cookie_manager=None):
    """로그인 및 회원가입 페이지"""

    # CSS 로드
    st.markdown(
        """
        <style>
        .auth-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
            background-color: #ffffff;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .stButton button {
            width: 100%;
            border-radius: 5px;
            font-weight: bold;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown(
            "<h1 style='text-align: center;'>🔐 로그인</h1>", unsafe_allow_html=True
        )
        st.markdown(
            "<p style='text-align: center; color: gray;'>미국 주식 분석 봇에 오신 것을 환영합니다.</p>",
            unsafe_allow_html=True,
        )

        tab1, tab2 = st.tabs(["로그인", "회원가입"])

        with tab1:
            with st.form("login_form"):
                email = st.text_input("이메일", key="login_email")
                password = st.text_input("비밀번호", type="password", key="login_pw")
                submit = st.form_submit_button("로그인", type="primary")

                if submit:
                    if not email or not password:
                        st.error("이메일과 비밀번호를 입력해주세요.")
                    else:
                        with st.spinner("로그인 중..."):
                            result = SupabaseClient.login_user(email, password)
                            if result["success"]:
                                st.session_state.user = result["user"]
                                st.session_state.is_logged_in = True

                                # localStorage에 세션 저장
                                save_session_to_local_storage(
                                    email=email,
                                    user_id=result["user"]["id"]
                                )

                                # 관심 기업 로드
                                favorites = SupabaseClient.get_favorites(
                                    result["user"]["id"]
                                )
                                st.session_state.watchlist = favorites
                                st.success(f"환영합니다! {email}님")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error(result.get("message", "로그인 실패"))

        with tab2:
            with st.form("register_form"):
                reg_email = st.text_input("이메일", key="reg_email")
                reg_password = st.text_input(
                    "비밀번호",
                    type="password",
                    help="최소 6자 이상 입력해주세요.",
                    key="reg_pw",
                )
                reg_password_confirm = st.text_input(
                    "비밀번호 확인", type="password", key="reg_pw_cf"
                )
                submit_reg = st.form_submit_button("회원가입")

                if submit_reg:
                    if not reg_email or not reg_password:
                        st.error("이메일과 비밀번호를 입력해주세요.")
                    elif len(reg_password) < 6:
                        st.error("비밀번호는 최소 6자 이상이어야 합니다.")
                    elif reg_password != reg_password_confirm:
                        st.error("비밀번호가 일치하지 않습니다.")
                    else:
                        with st.spinner("계정 생성 중..."):
                            result = SupabaseClient.register_user(
                                reg_email, reg_password
                            )
                            if result["success"]:
                                st.success("회원가입이 완료되었습니다! 로그인해주세요.")
                            else:
                                st.error(result.get("message", "회원가입 실패"))
