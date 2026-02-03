import sys
from typing import Optional, Dict, Any


def add_to_favorites_tool(ticker: str) -> str:
    """
    관심 기업 추가 도구 함수

    Args:
        ticker (str): 추가할 기업 티커 (예: AAPL)

    Returns:
        str: 실행 결과 메시지
    """
    try:
        # Streamlit 환경 확인
        if "streamlit" not in sys.modules:
            return "이 기능은 Streamlit 웹 인터페이스에서만 사용할 수 있습니다."

        import streamlit as st
        import logging

        logger = logging.getLogger(__name__)

        # Import robustness
        try:
            from data.supabase_client import SupabaseClient
        except ImportError:
            try:
                from src.data.supabase_client import SupabaseClient
            except ImportError as e:
                logger.error(f"Failed to import SupabaseClient: {e}")
                return f"시스템 오류: DB 클라이언트를 로드할 수 없습니다. ({str(e)})"

        # 로그인 및 세션 확인
        if not hasattr(st, "session_state"):
            return "세션 상태를 확인할 수 없습니다."

        if not st.session_state.get("is_logged_in") or not st.session_state.get("user"):
            return "로그인이 필요한 기능입니다. 먼저 로그인해주세요."

        user = st.session_state.user
        user_id = user.get("id")

        if not user_id:
            return "사용자 정보를 찾을 수 없습니다."

        ticker = ticker.strip().upper()

        # 1. DB에 추가
        result = SupabaseClient.add_favorite(user_id, ticker)

        if result:
            # 2. 로컬 세션(Watchlist) 즉시 동기화
            if "watchlist" not in st.session_state:
                st.session_state.watchlist = []

            if ticker not in st.session_state.watchlist:
                st.session_state.watchlist.append(ticker)

            return f"✅ {ticker}가 관심 기업(Favorites)에 성공적으로 추가되었습니다!"
        else:
            return f"❌ {ticker} 추가 중 문제가 발생했습니다. (DB 오류)"

    except Exception as e:
        return f"시스템 오류가 발생했습니다: {str(e)}"


def remove_from_favorites_tool(ticker: str) -> str:
    """
    관심 기업 삭제 도구 함수

    Args:
        ticker (str): 삭제할 기업 티커 (예: AAPL)

    Returns:
        str: 실행 결과 메시지
    """
    try:
        # Streamlit 환경 확인
        if "streamlit" not in sys.modules:
            return "이 기능은 Streamlit 웹 인터페이스에서만 사용할 수 있습니다."

        import streamlit as st
        import logging

        logger = logging.getLogger(__name__)

        # Import robustness
        try:
            from data.supabase_client import SupabaseClient
        except ImportError:
            try:
                from src.data.supabase_client import SupabaseClient
            except ImportError as e:
                logger.error(f"Failed to import SupabaseClient: {e}")
                return f"시스템 오류: DB 클라이언트를 로드할 수 없습니다. ({str(e)})"

        # 로그인 및 세션 확인
        if not hasattr(st, "session_state"):
            return "세션 상태를 확인할 수 없습니다."

        if not st.session_state.get("is_logged_in") or not st.session_state.get("user"):
            return "로그인이 필요한 기능입니다. 먼저 로그인해주세요."

        user = st.session_state.user
        user_id = user.get("id")

        if not user_id:
            return "사용자 정보를 찾을 수 없습니다."

        ticker = ticker.strip().upper()

        # 1. 로컬 세션에서 확인
        if "watchlist" not in st.session_state:
            st.session_state.watchlist = []

        if ticker not in st.session_state.watchlist:
            return f"❌ {ticker}는 관심 기업 목록에 없습니다."

        # 2. DB에서 삭제
        success, error_msg = SupabaseClient.remove_favorite(user_id, ticker)

        if success:
            # 3. 로컬 세션(Watchlist) 즉시 동기화
            if ticker in st.session_state.watchlist:
                st.session_state.watchlist.remove(ticker)

            return f"✅ {ticker}가 관심 기업(Favorites)에서 성공적으로 삭제되었습니다!"
        else:
            return f"❌ {ticker} 삭제 중 문제가 발생했습니다. ({error_msg})"

    except Exception as e:
        return f"시스템 오류가 발생했습니다: {str(e)}"

