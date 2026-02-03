"""
GraphRAG implementation using existing Supabase schema
Uses: companies, company_relationships, documents tables
"""

import os
import json
import logging
from typing import List, Dict, Optional
import networkx as nx
from openai import OpenAI
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class GraphRAG:
    """
    Graph-based RAG using existing Supabase tables:
    - companies: 회사 정보
    - company_relationships: 회사 간 관계
    - documents: 벡터 문서
    """

    def __init__(
        self, embedding_model: str = "text-embedding-3-small", llm_model: str = "gpt-4.1-mini"
    ):
        """Initialize GraphRAG with Supabase"""

        # OpenAI client
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 필요합니다.")

        self.openai_client = OpenAI(api_key=self.openai_api_key)
        self.embedding_model = embedding_model
        self.llm_model = llm_model

        # Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL과 SUPABASE_KEY 환경 변수가 필요합니다.")

        self.supabase: Client = create_client(supabase_url, supabase_key)

        # Local graph for analysis
        self.local_graph = nx.DiGraph()

        logger.info("GraphRAG initialized with Supabase")

    def _get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        response = self.openai_client.embeddings.create(model=self.embedding_model, input=text)
        return response.data[0].embedding

    def _chat_completion(self, system_prompt: str, user_prompt: str) -> str:
        """Get chat completion from OpenAI"""
        response = self.openai_client.chat.completions.create(
            model=self.llm_model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content

    def extract_relationships(self, text: str, source_ticker: Optional[str] = None) -> List[Dict]:
        """Extract company relationships from text using LLM"""

        system_prompt = """You are a financial analyst. Extract company relationships from text.

Relationship types: partnership, acquisition, supplier, customer, competitor, subsidiary, investment

Return JSON only:
[{"source_company": "...", "source_ticker": "...", "target_company": "...", "target_ticker": "...", 
  "relationship_type": "...", "confidence": 0.8}]"""

        user_prompt = f"Source Company Ticker: {source_ticker or 'Unknown'}\n\nText:\n{text[:3000]}"

        try:
            response = self._chat_completion(system_prompt, user_prompt)

            # Clean JSON
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            return json.loads(response.strip())

        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return []

    def save_relationships(
        self, relationships: List[Dict], extracted_from: str = None, filing_date: str = None
    ) -> int:
        """Save relationships to company_relationships table"""
        if not relationships:
            return 0

        records = []
        for rel in relationships:
            records.append(
                {
                    "source_company": rel.get("source_company", ""),
                    "source_ticker": rel.get("source_ticker", ""),
                    "target_company": rel.get("target_company", ""),
                    "target_ticker": rel.get("target_ticker", ""),
                    "relationship_type": rel.get("relationship_type", "related"),
                    "confidence": rel.get("confidence", 0.5),
                    "extracted_from": extracted_from,
                    "filing_date": filing_date,
                }
            )

        try:
            self.supabase.table("company_relationships").insert(records).execute()
            return len(records)
        except Exception as e:
            logger.error(f"Error saving relationships: {e}")
            return 0

    def find_relationships(self, ticker: str, relationship_type: Optional[str] = None) -> Dict:
        """Find relationships for a company by ticker"""
        try:
            # Outgoing relationships (source)
            query = (
                self.supabase.table("company_relationships").select("*").eq("source_ticker", ticker)
            )
            if relationship_type:
                query = query.eq("relationship_type", relationship_type)
            outgoing = query.execute().data

            # Incoming relationships (target)
            query = (
                self.supabase.table("company_relationships").select("*").eq("target_ticker", ticker)
            )
            if relationship_type:
                query = query.eq("relationship_type", relationship_type)
            incoming = query.execute().data

            return {
                "ticker": ticker,
                "outgoing": outgoing,
                "incoming": incoming,
                "total": len(outgoing) + len(incoming),
            }

        except Exception as e:
            logger.error(f"Error finding relationships: {e}")
            return {"ticker": ticker, "outgoing": [], "incoming": [], "error": str(e)}

    def get_company(self, ticker: str) -> Optional[Dict]:
        """Get company info by ticker"""
        try:
            result = self.supabase.table("companies").select("*").eq("ticker", ticker).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting company: {e}")
            return None

    def search_companies(self, query: str, limit: int = 10) -> List[Dict]:
        """Search companies by name"""
        try:
            result = (
                self.supabase.table("companies")
                .select("*")
                .ilike("company_name", f"%{query}%")
                .limit(limit)
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error(f"Error searching companies: {e}")
            return []

    def get_company_network(self, ticker: str, depth: int = 1) -> Dict:
        """Get company relationship network"""
        visited = set()
        network = {"nodes": [], "edges": []}

        def traverse(current_ticker: str, current_depth: int):
            if current_depth > depth or current_ticker in visited:
                return
            visited.add(current_ticker)

            # Add node
            company = self.get_company(current_ticker)
            if company:
                network["nodes"].append(
                    {
                        "id": current_ticker,
                        "name": company.get("company_name", current_ticker),
                        "sector": company.get("sector", ""),
                    }
                )

            # Get relationships
            rels = self.find_relationships(current_ticker)

            for rel in rels.get("outgoing", []):
                target = rel.get("target_ticker")
                if target:
                    network["edges"].append(
                        {
                            "source": current_ticker,
                            "target": target,
                            "type": rel.get("relationship_type", "related"),
                        }
                    )
                    traverse(target, current_depth + 1)

            for rel in rels.get("incoming", []):
                source = rel.get("source_ticker")
                if source:
                    network["edges"].append(
                        {
                            "source": source,
                            "target": current_ticker,
                            "type": rel.get("relationship_type", "related"),
                        }
                    )
                    traverse(source, current_depth + 1)

        traverse(ticker, 0)
        return network

    def query_with_context(self, query: str, ticker: Optional[str] = None) -> Dict:
        """Query with relationship context"""

        # Get context
        context_parts = []

        if ticker:
            # Company info
            company = self.get_company(ticker)
            if company:
                context_parts.append(f"Company: {company.get('company_name')} ({ticker})")
                context_parts.append(f"Sector: {company.get('sector', 'N/A')}")
                context_parts.append(f"Industry: {company.get('industry', 'N/A')}")

            # Relationships
            rels = self.find_relationships(ticker)
            if rels["total"] > 0:
                context_parts.append("\nRelationships:")
                for rel in rels.get("outgoing", [])[:10]:
                    context_parts.append(
                        f"  → {rel['relationship_type']}: {rel['target_company']} ({rel.get('target_ticker', '')})"
                    )
                for rel in rels.get("incoming", [])[:10]:
                    context_parts.append(
                        f"  ← {rel['relationship_type']}: {rel['source_company']} ({rel.get('source_ticker', '')})"
                    )

        context_str = (
            "\n".join(context_parts) if context_parts else "No specific context available."
        )

        # Generate response
        system_prompt = """You are a financial analyst assistant. Answer based on the company and relationship context.
Be specific and cite relationships when relevant. Answer in Korean."""

        user_prompt = f"Context:\n{context_str}\n\nQuestion: {query}"

        response = self._chat_completion(system_prompt, user_prompt)

        return {"query": query, "ticker": ticker, "response": response, "context": context_str}

    def build_local_graph(self) -> int:
        """
        Supabase의 관계 데이터를 NetworkX 그래프로 로드합니다.
        Returns: 로드된 엣지 수
        """
        try:
            # 모든 관계 가져오기
            result = self.supabase.table("company_relationships").select("*").execute()
            relationships = result.data or []
            
            # 그래프 초기화
            self.local_graph.clear()
            
            for rel in relationships:
                source = rel.get("source_ticker")
                target = rel.get("target_ticker")
                rel_type = rel.get("relationship_type", "related")
                confidence = rel.get("confidence", 0.5)
                
                if source and target:
                    # 노드 추가 (자동으로 중복 방지)
                    self.local_graph.add_node(source, name=rel.get("source_company", source))
                    self.local_graph.add_node(target, name=rel.get("target_company", target))
                    
                    # 엣지 추가 (관계 유형과 신뢰도를 속성으로)
                    self.local_graph.add_edge(
                        source, target,
                        relationship_type=rel_type,
                        confidence=confidence,
                        weight=1 - confidence  # 신뢰도가 높을수록 거리가 짧음
                    )
            
            logger.info(f"Built local graph: {self.local_graph.number_of_nodes()} nodes, {self.local_graph.number_of_edges()} edges")
            return self.local_graph.number_of_edges()
            
        except Exception as e:
            logger.error(f"Error building local graph: {e}")
            return 0

    def get_centrality(self, top_n: int = 10) -> Dict:
        """
        중심성 분석 - 가장 영향력 있는 기업 찾기
        Returns: 다양한 중심성 지표별 상위 기업
        """
        if self.local_graph.number_of_nodes() == 0:
            self.build_local_graph()
        
        if self.local_graph.number_of_nodes() == 0:
            return {"error": "그래프에 데이터가 없습니다."}
        
        try:
            # 연결 중심성 (Degree Centrality) - 직접 연결된 관계 수
            degree_cent = nx.degree_centrality(self.local_graph)
            
            # 매개 중심성 (Betweenness Centrality) - 다리 역할
            betweenness_cent = nx.betweenness_centrality(self.local_graph)
            
            # 근접 중심성 (Closeness Centrality) - 다른 노드와의 평균 거리
            # DiGraph에서는 연결되지 않은 노드가 있을 수 있어 예외 처리
            try:
                closeness_cent = nx.closeness_centrality(self.local_graph)
            except:
                closeness_cent = {}
            
            # 상위 N개 추출
            top_degree = sorted(degree_cent.items(), key=lambda x: x[1], reverse=True)[:top_n]
            top_betweenness = sorted(betweenness_cent.items(), key=lambda x: x[1], reverse=True)[:top_n]
            top_closeness = sorted(closeness_cent.items(), key=lambda x: x[1], reverse=True)[:top_n]
            
            return {
                "degree_centrality": [{"ticker": k, "score": round(v, 4)} for k, v in top_degree],
                "betweenness_centrality": [{"ticker": k, "score": round(v, 4)} for k, v in top_betweenness],
                "closeness_centrality": [{"ticker": k, "score": round(v, 4)} for k, v in top_closeness],
                "total_nodes": self.local_graph.number_of_nodes(),
                "total_edges": self.local_graph.number_of_edges(),
            }
            
        except Exception as e:
            logger.error(f"Error calculating centrality: {e}")
            return {"error": str(e)}

    def find_shortest_path(self, source_ticker: str, target_ticker: str) -> Dict:
        """
        두 기업 간의 최단 경로 찾기
        Returns: 경로와 관계 유형
        """
        if self.local_graph.number_of_nodes() == 0:
            self.build_local_graph()
        
        try:
            # 방향 무시하고 경로 찾기 (undirected view)
            undirected = self.local_graph.to_undirected()
            
            if source_ticker not in undirected or target_ticker not in undirected:
                return {"error": f"'{source_ticker}' 또는 '{target_ticker}'가 그래프에 없습니다."}
            
            # 최단 경로 찾기
            path = nx.shortest_path(undirected, source=source_ticker, target=target_ticker)
            
            # 경로의 각 엣지 관계 유형 추출
            path_details = []
            for i in range(len(path) - 1):
                node1, node2 = path[i], path[i + 1]
                
                # 원래 방향 그래프에서 관계 찾기
                if self.local_graph.has_edge(node1, node2):
                    edge_data = self.local_graph.get_edge_data(node1, node2)
                    direction = "→"
                elif self.local_graph.has_edge(node2, node1):
                    edge_data = self.local_graph.get_edge_data(node2, node1)
                    direction = "←"
                else:
                    edge_data = {}
                    direction = "—"
                
                path_details.append({
                    "from": node1,
                    "to": node2,
                    "direction": direction,
                    "relationship": edge_data.get("relationship_type", "related"),
                })
            
            return {
                "source": source_ticker,
                "target": target_ticker,
                "path": path,
                "path_length": len(path) - 1,
                "details": path_details,
            }
            
        except nx.NetworkXNoPath:
            return {"error": f"'{source_ticker}'와 '{target_ticker}' 사이에 경로가 없습니다."}
        except Exception as e:
            logger.error(f"Error finding shortest path: {e}")
            return {"error": str(e)}

    def get_connected_companies(self, ticker: str, max_depth: int = 2) -> Dict:
        """
        특정 기업과 연결된 모든 기업 찾기 (BFS)
        Returns: depth별 연결된 기업 목록
        """
        if self.local_graph.number_of_nodes() == 0:
            self.build_local_graph()
        
        if ticker not in self.local_graph:
            return {"error": f"'{ticker}'가 그래프에 없습니다."}
        
        try:
            undirected = self.local_graph.to_undirected()
            
            # BFS로 depth별 노드 찾기
            connected_by_depth = {}
            visited = {ticker}
            current_level = {ticker}
            
            for depth in range(1, max_depth + 1):
                next_level = set()
                for node in current_level:
                    neighbors = set(undirected.neighbors(node)) - visited
                    next_level.update(neighbors)
                    visited.update(neighbors)
                
                if next_level:
                    connected_by_depth[f"depth_{depth}"] = list(next_level)
                current_level = next_level
            
            return {
                "ticker": ticker,
                "connected": connected_by_depth,
                "total_connected": len(visited) - 1,  # 자기 자신 제외
            }
            
        except Exception as e:
            logger.error(f"Error finding connected companies: {e}")
            return {"error": str(e)}

    def get_stats(self) -> Dict:
        """Get statistics"""
        stats = {}

        try:
            companies = self.supabase.table("companies").select("id", count="exact").execute()
            relationships = (
                self.supabase.table("company_relationships").select("id", count="exact").execute()
            )
            documents = self.supabase.table("documents").select("id", count="exact").execute()

            stats = {
                "companies": companies.count or 0,
                "relationships": relationships.count or 0,
                "documents": documents.count or 0,
            }
        except Exception as e:
            stats["error"] = str(e)

        return stats


# LangGraph Tool function
def graph_search_tool(query: str, ticker: str = None) -> str:
    """
    회사 관계 그래프에서 정보를 검색합니다.
    LangGraph Tool로 사용됩니다.
    """
    try:
        graph_rag = GraphRAG()
        result = graph_rag.query_with_context(query, ticker)
        return result.get("response", "관련 정보를 찾을 수 없습니다.")
    except Exception as e:
        logger.error(f"Graph search error: {e}")
        return f"검색 오류: {e}"


if __name__ == "__main__":
    print("🔄 GraphRAG 초기화 중...")

    try:
        graph_rag = GraphRAG()
        stats = graph_rag.get_stats()

        print(f"✅ GraphRAG 초기화 성공!")
        print(f"   Companies: {stats.get('companies', 'N/A')}")
        print(f"   Relationships: {stats.get('relationships', 'N/A')}")
        print(f"   Documents: {stats.get('documents', 'N/A')}")

        if "error" in stats:
            print(f"   ⚠️ Error: {stats['error']}")

    except Exception as e:
        print(f"❌ 오류: {e}")
