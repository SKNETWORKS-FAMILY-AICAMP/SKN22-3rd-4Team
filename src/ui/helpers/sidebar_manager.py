import streamlit as st
import logging
from data.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


@st.dialog("👤 회원정보 관리")
def user_settings_dialog():
    """회원정보 관리 팝업 (비밀번호 변경, 회원 탈퇴, 로그아웃)"""
    user_email = st.session_state.user.get("email", "")
    st.write(f"📧 **{user_email}**")
    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["🔑 비밀번호 변경", "🗑️ 회원 탈퇴", "🚪 로그아웃"])
    
    with tab1:
        with st.form("change_password_form"):
            current_pw = st.text_input("현재 비밀번호", type="password", key="current_pw")
            new_pw = st.text_input("새 비밀번호", type="password", key="new_pw")
            new_pw_confirm = st.text_input("새 비밀번호 확인", type="password", key="new_pw_confirm")
            submit_pw = st.form_submit_button("변경", type="primary", use_container_width=True)
            
            if submit_pw:
                if not current_pw or not new_pw or not new_pw_confirm:
                    st.error("모든 필드를 입력해주세요.")
                elif new_pw != new_pw_confirm:
                    st.error("새 비밀번호가 일치하지 않습니다.")
                elif len(new_pw) < 6:
                    st.error("비밀번호는 최소 6자 이상이어야 합니다.")
                else:
                    user_id = st.session_state.user.get("id")
                    result = SupabaseClient.change_password(user_id, current_pw, new_pw)
                    if result["success"]:
                        st.success(result["message"])
                    else:
                        st.error(result["message"])
    
    with tab2:
        st.warning("⚠️ 탈퇴 시 모든 데이터가 삭제되며 복구할 수 없습니다.")
        with st.form("delete_account_form"):
            delete_pw = st.text_input("비밀번호 확인", type="password", key="delete_pw")
            submit_delete = st.form_submit_button("회원 탈퇴", type="primary", use_container_width=True)
            
            if submit_delete:
                if not delete_pw:
                    st.error("비밀번호를 입력해주세요.")
                else:
                    user_id = st.session_state.user.get("id")
                    result = SupabaseClient.delete_user(user_id, delete_pw)
                    
                    if result["success"]:
                        st.session_state.is_logged_in = False
                        st.session_state.user = None
                        st.session_state.watchlist = []
                        st.session_state.just_logged_out = True
                        
                        from streamlit.components.v1 import html
                        html("""
                        <script>
                            localStorage.removeItem('stock_bot_session');
                            window.top.location.reload();
                        </script>
                        """, height=0, width=0)
                    else:
                        st.error(result["message"])
    
    with tab3:
        st.info("로그아웃하면 세션이 종료됩니다.")
        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state.is_logged_in = False
            st.session_state.user = None
            st.session_state.watchlist = []
            st.session_state.just_logged_out = True
            
            from streamlit.components.v1 import html
            html("""
            <script>
                localStorage.removeItem('stock_bot_session');
                window.top.location.reload();
            </script>
            """, height=0, width=0)


def render_user_settings_button():
    """사이드바에 회원정보관리 버튼 렌더링"""
    st.sidebar.markdown("---")
    if st.sidebar.button("👤 회원정보 관리", use_container_width=True):
        user_settings_dialog()


def render_sidebar_status():
    """스케줄러 상태 및 기본 정보 표시 (placeholder if needed)"""
    pass  # app.py에서 scheduler status를 이미 처리하고 있을 수 있음. 확인 필요.


def render_watchlist_sidebar():
    """로그인 사용자용 관심 기업 사이드바 렌더링"""

    # 1. 상태 초기화
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = []

    watchlist = st.session_state.watchlist

    # 2. Add UI
    add_col1, add_col2 = st.columns([3, 1])
    with add_col1:
        new_ticker = st.text_input(
            "관심기업 추가",
            placeholder="기업명/티커 입력",
            label_visibility="collapsed",
            key="sidebar_quick_add_ticker",
        )
    with add_col2:
        add_clicked = st.button("﹢", key="sidebar_add_btn", help="관심 기업 추가")

    # 3. Add Logic
    if add_clicked and new_ticker:
        search_term = new_ticker.strip()
        try:
            df = SupabaseClient.search_companies(search_term)

            if not df.empty:
                found_ticker = df.iloc[0]["ticker"]
                found_name = df.iloc[0].get("korean_name") or df.iloc[0]["company_name"]

                if found_ticker not in st.session_state.watchlist:
                    # DB 저장
                    if st.session_state.user:
                        SupabaseClient.add_favorite(
                            st.session_state.user["id"], found_ticker
                        )

                    st.session_state.watchlist.append(found_ticker)
                    st.toast(f"✅ {found_name} ({found_ticker}) 추가됨")
                    st.rerun()
                else:
                    st.toast(f"⚠️ {found_name} ({found_ticker})은(는) 이미 등록됨")
            else:
                st.toast(f"❌ '{search_term}' 검색 결과가 없습니다")
        except Exception as e:
            st.toast(f"⚠️ DB 연결 오류: {str(e)[:30]}")
            logger.error(f"Watchlist add error: {e}")

    st.markdown("---")

    # 4. List UI (List Layout)
    if watchlist:
        st.markdown("##### ⭐ 관심 기업")
        for ticker in list(watchlist):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"📈 **{ticker}**")
            with col2:
                if st.button("x", key=f"sidebar_rm_{ticker}", help=f"{ticker} 삭제"):
                    try:
                        success = True
                        if st.session_state.user:
                            user_id = st.session_state.user["id"]
                            logger.info(
                                f"Removing favorite: User={user_id}, Ticker={ticker}"
                            )
                            success, error_msg = SupabaseClient.remove_favorite(
                                user_id, ticker
                            )
                            if not success:
                                st.toast(f"❌ DB 삭제 실패: {error_msg}")
                                logger.error(f"DB Delete Failed: {error_msg}")

                        if success:
                            st.session_state.watchlist.remove(ticker)
                            st.rerun()
                    except Exception as e:
                        st.toast(f"삭제 오류: {e}")
                        logger.error(f"Remove Error: {e}")

        st.caption(f"총 {len(watchlist)}개")
    else:
        st.caption("위 입력창에 기업명/티커를 입력하세요\n(예: 애플, MSFT)")
