"""
RAG 관련 모듈 공통 베이스 클래스
OpenAI, Supabase, Finnhub 및 RAG 엔진(VectorStore, GraphRAG, DataRetriever)의 공통 초기화 로직을 관리합니다.
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client, Client

# 로깅 설정
logger = logging.getLogger(__name__)
load_dotenv()

# RAG 모듈 임포트
try:
    from rag.vector_store import VectorStore
    from rag.graph_rag import GraphRAG
    from rag.data_retriever import DataRetriever

    RAG_AVAILABLE = True
except ImportError:
    try:
        from src.rag.vector_store import VectorStore
        from src.rag.graph_rag import GraphRAG
        from src.rag.data_retriever import DataRetriever

        RAG_AVAILABLE = True
    except ImportError:
        RAG_AVAILABLE = False
        logger.warning("RAG core modules not found. Some features may be disabled.")

# Stock API 클라이언트 임포트 (tools 우선 사용)
try:
    from src.tools.stock_api_client import get_stock_api_client

    STOCK_API_AVAILABLE = True
except ImportError:
    try:
        from data.stock_api_client import get_stock_api_client

        STOCK_API_AVAILABLE = True

        STOCK_API_AVAILABLE = True
    except ImportError:
        STOCK_API_AVAILABLE = False

# 환율 클라이언트 임포트
try:
    from tools.exchange_rate_client import get_exchange_client

    EXCHANGE_AVAILABLE = True
except ImportError:
    try:
        from src.tools.exchange_rate_client import get_exchange_client

        EXCHANGE_AVAILABLE = True
    except ImportError:
        EXCHANGE_AVAILABLE = False


class RAGBase:
    """RAG 시스템의 공통 클라이언트 및 데이터베이스 연결을 관리하는 베이스 클래스"""

    def __init__(self, model_name: str = "gpt-4.1-mini"):
        # 1. OpenAI 초기화
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 필요합니다.")
        self.openai_client = OpenAI(api_key=self.openai_api_key)
        self.model = model_name
        self.embedding_model = "text-embedding-3-small"

        # 2. Supabase 초기화
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL과 SUPABASE_KEY 환경 변수가 필요합니다.")
        self.supabase: Client = create_client(supabase_url, supabase_key)

        # 3. Stock API 초기화
        self.finnhub = None
        if STOCK_API_AVAILABLE:
            try:
                self.finnhub = get_stock_api_client()
                if not self.finnhub.api_key:
                    self.finnhub = None
            except Exception as e:
                logger.warning(f"Stock API init failed: {e}")

        # 4. RAG 엔진 초기화
        self.vector_store = None
        self.graph_rag = None
        self.data_retriever = None

        if RAG_AVAILABLE:
            try:
                self.vector_store = VectorStore()
                self.graph_rag = GraphRAG()
                self.data_retriever = DataRetriever(
                    supabase=self.supabase,
                    vector_store=self.vector_store,
                    graph_rag=self.graph_rag,
                    finnhub=self.finnhub,
                )
                logger.info(
                    "RAG Engine (VectorStore, GraphRAG, DataRetriever) initialized"
                )
            except Exception as e:
                logger.warning(f"RAG Engine init failed: {e}")

    def _load_prompt(self, filename: str) -> str:
        """프롬프트 파일 로드"""
        prompts_dir = Path(__file__).parent.parent / "prompts"
        prompt_path = prompts_dir / filename

        if not prompt_path.exists():
            # Alternative path check
            prompt_path = (
                Path(__file__).parent.parent.parent / "src" / "prompts" / filename
            )

        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        logger.error(f"Prompt file not found: {filename}")
        return ""
