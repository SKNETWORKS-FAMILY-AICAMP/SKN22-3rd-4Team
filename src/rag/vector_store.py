"""
Vector store for document embeddings and similarity search using Supabase
Uses Supabase REST API with pgvector extension
Enhanced with CrossEncoder Reranking for improved search accuracy
"""

import logging
import os
from typing import List, Dict, Optional, Tuple
from openai import OpenAI
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# CrossEncoder 모델 (Lazy Loading)
_reranker = None


class VectorStore:
    """Manages vector embeddings for financial documents using Supabase pgvector"""

    def __init__(
        self,
        table_name: str = "documents",
        embedding_model: str = "text-embedding-3-small",
        dimension: int = 1536,
    ):
        """
        Initialize vector store with Supabase

        Args:
            table_name: Name of the table in Supabase
            embedding_model: Model for generating embeddings
            dimension: Embedding dimension (1536 for text-embedding-3-small)
        """
        self.table_name = table_name
        self.embedding_model = embedding_model
        self.dimension = dimension

        # Get Supabase credentials
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL과 SUPABASE_KEY 환경 변수가 필요합니다.")

        # Initialize Supabase client
        self.supabase: Client = create_client(supabase_url, supabase_key)

        # Initialize OpenAI client for embeddings
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 필요합니다.")

        self.openai_client = OpenAI(api_key=self.openai_api_key)

        logger.info(f"Initialized Supabase vector store with table: {table_name}")

    def _get_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        response = self.openai_client.embeddings.create(
            model=self.embedding_model, input=text
        )
        return response.data[0].embedding

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        response = self.openai_client.embeddings.create(
            model=self.embedding_model, input=texts
        )
        return [item.embedding for item in response.data]

    def add_documents(self, documents: List[Dict], batch_size: int = 100) -> int:
        """
        Add documents to the vector store

        Args:
            documents: List of document dictionaries with 'id', 'text', and 'metadata'
            batch_size: Number of documents to process at once

        Returns:
            Number of documents added
        """
        total_added = 0

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]

            texts = [doc.get("text", "") for doc in batch]

            try:
                # Generate embeddings
                embeddings = self._get_embeddings(texts)

                # Prepare records for Supabase
                records = []
                for j, doc in enumerate(batch):
                    record = {
                        "content": doc.get("text", ""),
                        "embedding": embeddings[j],
                        "metadata": doc.get("metadata", {}),
                    }
                    if "id" in doc:
                        record["id"] = doc["id"]
                    records.append(record)

                # Insert to Supabase
                self.supabase.table(self.table_name).insert(records).execute()

                total_added += len(batch)
                logger.info(f"Added batch {i // batch_size + 1}, total: {total_added}")

            except Exception as e:
                logger.error(f"Error adding batch {i // batch_size + 1}: {str(e)}")

        logger.info(f"Total documents added: {total_added}")
        return total_added

    def similarity_search(
        self, query: str, k: int = 5, filter_dict: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search for similar documents using pgvector

        Args:
            query: Search query
            k: Number of results to return
            filter_dict: Optional metadata filters

        Returns:
            List of similar documents with scores
        """
        try:
            # Generate query embedding
            query_embedding = self._get_embedding(query)

            # Call the match_documents function in Supabase
            # Note: Adding match_threshold to disambiguate function overload
            response = self.supabase.rpc(
                "match_documents",
                {
                    "query_embedding": query_embedding,
                    "match_count": k,
                    "match_threshold": 0.3,  # Threshold 조정 (사용자 요청: 0.3)
                },
            ).execute()

            # 디버깅: 응답 데이터 로깅
            if not response.data:
                logger.warning(
                    f"No results from match_documents with threshold 0.3. Retrying without threshold."
                )
                # Fallback: Threshold 없이 상위 k개 강제 검색
                response = self.supabase.rpc(
                    "match_documents",
                    {
                        "query_embedding": query_embedding,
                        "match_count": k,
                        "match_threshold": 0.0,  # Threshold 제거 (Fallback)
                    },
                ).execute()

            if not response.data:
                logger.warning(
                    f"Still no results from match_documents (Fallback). Response: {response}"
                )

            # Format results
            documents = []
            for item in response.data:
                documents.append(
                    {
                        "id": item.get("id"),
                        "content": item.get("content"),
                        "metadata": item.get("metadata"),
                        "similarity": item.get("similarity"),
                    }
                )

            return documents

        except Exception as e:
            logger.error(f"Error in similarity search: {str(e)}")
            import traceback

            traceback.print_exc()
            return []

    def _load_reranker(self):
        """CrossEncoder 모델 로드 (Lazy Loading)"""
        global _reranker
        if _reranker is None:
            try:
                from sentence_transformers import CrossEncoder

                _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                logger.info("CrossEncoder reranker loaded successfully")
            except ImportError:
                logger.warning(
                    "sentence-transformers not installed. Reranking will be disabled."
                )
                return None
        return _reranker

    def rerank_results(
        self, query: str, documents: List[Dict], top_k: int = 5
    ) -> List[Dict]:
        """
        CrossEncoder를 사용하여 검색 결과 재정렬

        Args:
            query: 원본 질문
            documents: Vector Search 결과
            top_k: 반환할 문서 수

        Returns:
            재정렬된 문서 리스트
        """
        if not documents:
            return []

        reranker = self._load_reranker()
        if reranker is None:
            return documents[:top_k]

        try:
            # CrossEncoder는 (query, document) 쌍의 점수를 계산
            pairs = [(query, doc.get("content", "")[:1000]) for doc in documents]
            scores = reranker.predict(pairs)

            # 점수와 문서를 함께 정렬
            scored_docs = list(zip(documents, scores))
            scored_docs.sort(key=lambda x: x[1], reverse=True)

            # 상위 top_k 문서 반환 (rerank_score 추가 및 음수 점수 필터링)
            reranked = []
            for doc, score in scored_docs:
                # if score < 0:  # 관련성 없는 문서(음수 점수) 제거 - [Recall 개선] 필터 제거 (Top K 보장)
                #     continue

                doc["rerank_score"] = float(score)
                reranked.append(doc)

                if len(reranked) >= top_k:
                    break

            logger.info(f"Reranked {len(documents)} docs → top {top_k}")
            return reranked

        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return documents[:top_k]

    def similarity_search_with_rerank(
        self,
        query: str,
        k: int = 5,
        initial_k: int = 20,
        filter_dict: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        Vector Search + Reranking 통합 검색

        Args:
            query: 검색 질문
            k: 최종 반환 문서 수
            initial_k: 1차 Vector Search에서 가져올 문서 수
            filter_dict: 메타데이터 필터

        Returns:
            재정렬된 상위 k개 문서
        """
        # 1. 먼저 더 많은 문서를 Vector Search로 가져옴
        initial_results = self.similarity_search(query, initial_k, filter_dict)

        # 2. CrossEncoder로 재정렬
        reranked_results = self.rerank_results(query, initial_results, k)

        return reranked_results

    def search_by_company(self, query: str, company: str, k: int = 5) -> List[Dict]:
        """
        Search for documents related to a specific company

        Args:
            query: Search query
            company: Company ticker or name
            k: Number of results

        Returns:
            List of relevant documents
        """
        # [Optimization] 1. Retrieve a larger pool of documents (k=100) to ensure company-specific docs are included
        # This drastically improves Recall for specific company queries
        results = self.similarity_search(query, k=100)

        # 2. Filter by company ticker in metadata
        filtered = [
            doc for doc in results if doc.get("metadata", {}).get("ticker") == company
        ]

        if not filtered:
            logger.warning(
                f"No documents found for company {company} in top 100 results."
            )
            return []

        # 3. Rerank the filtered results using CrossEncoder
        # This improves Precision by re-scoring the candidates
        reranked = self.rerank_results(query, filtered, k)

        return reranked

    def hybrid_search(
        self,
        query: str,
        k: int = 5,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> List[Dict]:
        """
        Hybrid Search: Vector(의미) + Keyword(BM25) 결합

        Args:
            query: 검색 질문
            k: 반환할 문서 수
            vector_weight: Vector 검색 가중치 (기본 0.7)
            keyword_weight: Keyword 검색 가중치 (기본 0.3)

        Returns:
            결합된 검색 결과
        """
        try:
            # 1. Vector Search 결과
            vector_results = self.similarity_search(query, k * 2)
            vector_ids = {doc["id"]: (i, doc) for i, doc in enumerate(vector_results)}

            # 2. Keyword Search (Supabase Full-Text Search)
            # PostgreSQL의 to_tsquery를 사용하여 키워드 검색
            keywords = " | ".join(query.split()[:5])  # 상위 5개 키워드만 사용

            try:
                # Supabase Full-Text Search 대신 ILIKE 패턴 매칭 사용
                # (더 호환성이 좋음)
                search_pattern = f"%{query.split()[0]}%"  # 첫 번째 키워드로 검색
                keyword_response = (
                    self.supabase.table(self.table_name)
                    .select("id, content, metadata")
                    .ilike("content", search_pattern)
                    .limit(k * 2)
                    .execute()
                )
                keyword_results = keyword_response.data or []
            except Exception as e:
                logger.warning(f"Keyword search failed, using vector only: {e}")
                keyword_results = []

            keyword_ids = {doc["id"]: (i, doc) for i, doc in enumerate(keyword_results)}

            # 3. RRF (Reciprocal Rank Fusion) 스코어 계산
            rrf_scores = {}
            RRF_K = 60  # RRF 상수

            for doc_id, (rank, doc) in vector_ids.items():
                rrf_scores[doc_id] = {
                    "doc": doc,
                    "score": vector_weight * (1 / (RRF_K + rank)),
                }

            for doc_id, (rank, doc) in keyword_ids.items():
                if doc_id in rrf_scores:
                    rrf_scores[doc_id]["score"] += keyword_weight * (1 / (RRF_K + rank))
                else:
                    rrf_scores[doc_id] = {
                        "doc": {
                            "id": doc_id,
                            "content": doc.get("content"),
                            "metadata": doc.get("metadata"),
                            "similarity": 0,
                        },
                        "score": keyword_weight * (1 / (RRF_K + rank)),
                    }

            # 4. RRF 스코어로 정렬
            sorted_results = sorted(
                rrf_scores.values(), key=lambda x: x["score"], reverse=True
            )

            # 5. 상위 후보군 추출 (Reranking 전)
            # Reranking을 위해 k보다 조금 더 많이 가져옴
            candidates = []
            for item in sorted_results[: k * 2]:
                doc = item["doc"]
                doc["hybrid_score"] = item["score"]
                candidates.append(doc)

            # 6. CrossEncoder로 최종 재정렬 (Hybrid + Reranking)
            try:
                final_results = self.rerank_results(query, candidates, k)
                logger.info(
                    f"Hybrid Search: {len(vector_results)} vec + {len(keyword_results)} key -> {len(candidates)} cand -> {len(final_results)} reranked"
                )
                return final_results
            except Exception as e:
                logger.warning(f"Reranking in hybrid search failed: {e}")
                return candidates[:k]

            logger.info(
                f"Hybrid search: {len(vector_results)} vector + {len(keyword_results)} keyword → {len(final_results)} combined"
            )
            return final_results

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            # Fallback to reranked vector search
            return self.similarity_search_with_rerank(query, k)

    def get_stats(self) -> Dict:
        """Get statistics about the table"""
        try:
            response = (
                self.supabase.table(self.table_name)
                .select("id", count="exact")
                .execute()
            )
            count = response.count if response.count else 0
        except Exception:
            count = "Unknown"

        return {
            "table_name": self.table_name,
            "total_documents": count,
            "embedding_model": self.embedding_model,
            "dimension": self.dimension,
        }


# RAG Tool function for LangGraph
def rag_search_tool(query: str, ticker: str = None, k: int = 5) -> str:
    """
    Supabase Vector Store에서 질문과 관련된 문서를 검색합니다.
    LangGraph Tool로 사용될 함수입니다.
    """
    try:
        vector_store = VectorStore()

        if ticker:
            results = vector_store.search_by_company(query, ticker, k)
        else:
            results = vector_store.similarity_search(query, k)

        if not results:
            return "관련 문서를 찾을 수 없습니다."

        context = "\n---\n".join(
            [
                f"내용: {doc.get('content', 'N/A')[:500]}...\n메타데이터: {doc.get('metadata', {})}"
                for doc in results
            ]
        )

        return context

    except Exception as e:
        logger.error(f"RAG search error: {str(e)}")
        return f"검색 오류: {str(e)}"


if __name__ == "__main__":
    # 테스트: Vector Store 초기화 및 통계 확인
    try:
        print("🔄 Vector Store 연결 중...")
        store = VectorStore()
        stats = store.get_stats()
        print(f"✅ Vector Store 연결 성공!")
        print(f"   Table: {stats['table_name']}")
        print(f"   Documents: {stats['total_documents']}")
        print(f"   Embedding Model: {stats['embedding_model']}")
    except Exception as e:
        print(f"❌ 오류: {e}")
