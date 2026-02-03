"""
Model Settings - 중앙 집중식 모델 설정
모든 AI 모델 관련 설정을 여기서 관리
"""

import os
from dotenv import load_dotenv

load_dotenv()


# =============================================================================
# EMBEDDING MODELS
# =============================================================================

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSIONS = 1536


# =============================================================================
# CHAT MODELS
# =============================================================================

# Analyst Chatbot (대화형 분석)
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4.1-mini")
CHAT_MAX_TOKENS = 2000

# Graph RAG (관계 분석)
GRAPH_MODEL = os.getenv("GRAPH_MODEL", "gpt-4.1-mini")
GRAPH_MAX_TOKENS = 1500


# =============================================================================
# REPORT MODELS (Standardized to gpt-4.1-mini)
# =============================================================================

REPORT_MODEL = os.getenv("REPORT_MODEL", "gpt-4.1-mini")
REPORT_MAX_TOKENS = 3000
COMPARISON_MAX_TOKENS = 4000

# gpt-5-nano 전용 설정
REPORT_MODEL_CONFIG = {
    "response_format": {"type": "text"},
    "verbosity": "medium",
    "reasoning_effort": "medium",
    "store": False,
}


# =============================================================================
# API KEYS
# =============================================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")


# =============================================================================
# MODEL HELPERS
# =============================================================================


def get_report_params(max_tokens: int = None) -> dict:
    """gpt-5-nano API 호출용 파라미터 반환"""
    params = {
        "model": REPORT_MODEL,
        "max_completion_tokens": max_tokens or REPORT_MAX_TOKENS,
        **REPORT_MODEL_CONFIG,
    }
    return params


def get_chat_params() -> dict:
    """챗봇 API 호출용 파라미터 반환"""
    return {
        "model": CHAT_MODEL,
        "max_completion_tokens": CHAT_MAX_TOKENS,
    }


# =============================================================================
# VALIDATION
# =============================================================================


def validate_api_keys() -> dict:
    """API 키 상태 확인"""
    return {
        "openai": bool(OPENAI_API_KEY),
        "finnhub": bool(FINNHUB_API_KEY)
        and FINNHUB_API_KEY != "your_finnhub_api_key_here",
    }


if __name__ == "__main__":
    print("📊 Model Settings")
    print("=" * 40)
    print(f"Embedding: {EMBEDDING_MODEL}")
    print(f"Chat: {CHAT_MODEL}")
    print(f"Report: {REPORT_MODEL}")
    print(f"Graph: {GRAPH_MODEL}")
    print()
    print("API Keys:", validate_api_keys())
