
import os
import sys
import logging
import time
from pathlib import Path
from tqdm import tqdm

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.graph_rag import GraphRAG
from data.supabase_client import SupabaseClient

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def build_relationships(batch_size=50, limit=1000, offset=0):
    """
    documents 테이블에서 텍스트를 읽어와 관계를 추출하고 저장합니다.
    
    Args:
        batch_size: 한 번에 처리할 문서 수
        limit: 전체 처리할 문서 수 제한
        offset: 시작 위치 (페이지네이션)
    """
    logger.info(f"🚀 기업 관계 구축 시작... (Offset: {offset}, Limit: {limit})")
    
    try:
        graph_rag = GraphRAG()
        supabase = graph_rag.supabase
        
        # 0. 이미 처리된 문서 ID 가져오기
        logger.info("🔍 기처리 문서 확인 중...")
        processed_docs = set()
        try:
            # 병렬 처리를 위해 extracted_from 체크는 로컬 메모리보단 건너뛰기 전략이 낫지만
            # 일단 안전을 위해 체크합니다. 
            # (주의: 병렬 실행 시 processed_docs가 실시간 동기화되진 않지만, 중복 저장은 큰 문제 없습니다)
            rels = supabase.table("company_relationships").select("extracted_from").execute()
            for r in rels.data:
                if r.get("extracted_from"):
                    processed_docs.add(r["extracted_from"])
            logger.info(f"✅ 이미 처리된 문서: {len(processed_docs)}개")
        except Exception as e:
            logger.warning(f"⚠️ 기처리 문서 확인 실패: {e}")

        # 1. 처리할 문서 가져오기
        logger.info("📚 문서 가져오는 중...")
        # range를 사용하여 병렬 처리 지원
        query = supabase.table("documents").select("id, content, metadata").range(offset, offset + limit - 1)
        
        result = query.execute()
        documents = result.data
        
        if not documents:
            logger.warning("❌ 처리할 문서가 없습니다.")
            return

        logger.info(f"✅ {len(documents)}개의 문서를 분석합니다. (ID: {documents[0]['id'][:8]}... ~ {documents[-1]['id'][:8]}...)")
        
        total_extracted = 0
        skipped_count = 0
        
        # 2. 문서별 관계 추출
        for i, doc in enumerate(tqdm(documents, desc="Processing Documents")):
            doc_id = doc.get("id")
            
            # 이미 처리된 문서면 건너뛰기
            if str(doc_id) in processed_docs:
                skipped_count += 1
                continue
                
            content = doc.get("content", "")
            metadata = doc.get("metadata") or {}
            
            # 메타데이터에서 티커 정보가 있으면 힌트로 활용
            source_ticker = None
            if isinstance(metadata, dict):
                source_ticker = metadata.get("ticker")
            
            # 텍스트가 너무 짧으면 스킵
            if len(content) < 100:
                continue
                
            # 관계 추출 (LLM 호출)
            # 비용 절약을 위해 텍스트 앞부분 2000자만 사용
            relationships = graph_rag.extract_relationships(content[:2000], source_ticker=source_ticker)
            
            if relationships:
                # 저장
                saved_count = graph_rag.save_relationships(
                    relationships, 
                    extracted_from=str(doc_id),
                    filing_date=doc.get("metadata", {}).get("date")
                )
                total_extracted += saved_count
                
            # Rate Limit 방지
            time.sleep(0.5)
            
            if (i + 1) % batch_size == 0:
                logger.info(f"🔄 중간 집계: {i+1}/{len(documents)} 처리, {total_extracted}개 관계 저장")

        logger.info("="*50)
        logger.info(f"🎉 완료! 총 {total_extracted}개의 새로운 기업 관계가 추출되었습니다. (Skipped: {skipped_count})")
        logger.info("="*50)

    except Exception as e:
        logger.error(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    # 실행 시 인자로 limit, offset 조절 가능
    # usage: python script.py [limit] [offset]
    limit = 1000
    offset = 0
    
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except:
            pass
            
    if len(sys.argv) > 2:
        try:
            offset = int(sys.argv[2])
        except:
            pass
            
    print(f"🔧 설정: 문서 {limit}개 처리 (Offset: {offset})")
    build_relationships(limit=limit, offset=offset)
