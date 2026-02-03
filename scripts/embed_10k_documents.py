"""
10-K 문서 임베딩 및 Supabase 업로드 (Vector Store)

수집된 10-K 텍스트 파일(data/10k_documents/)을 읽어와서
청킹(Chunking) 후 OpenAI 임베딩을 생성하여 Supabase에 저장합니다.
"""

import os
import time
import uuid
from pathlib import Path
from typing import List, Dict
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client
from langchain_classic.text_splitter import RecursiveCharacterTextSplitter

load_dotenv()

# 설정
DATA_DIR = Path("data/10k_documents")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY]):
    raise ValueError("필수 환경 변수(.env)가 설정되지 않았습니다.")

# 클라이언트 초기화
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# 텍스트 분할기 설정
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
)


def get_embedding(text: str) -> List[float]:
    """OpenAI 임베딩 생성"""
    text = text.replace("\n", " ")
    return (
        openai_client.embeddings.create(input=[text], model="text-embedding-3-small")
        .data[0]
        .embedding
    )


def process_company_documents(ticker: str, directory: Path):
    """특정 기업의 문서를 처리하여 업로드"""
    print(f"\n📄 {ticker} 문서 처리 중...")

    # 처리할 파일 목록
    files = {
        "business": directory / "business.txt",
        "risk_factors": directory / "risk_factors.txt",
        "mda": directory / "mda.txt",
    }

    documents = []

    for section, file_path in files.items():
        if not file_path.exists():
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        if not text:
            continue

        # 1. 텍스트 청킹
        chunks = text_splitter.split_text(text)
        print(f"   - {section}: {len(chunks)} chunks")

        # 2. 임베딩 및 데이터 준비
        for i, chunk in enumerate(chunks):
            documents.append(
                {
                    "content": chunk,
                    "metadata": {
                        "ticker": ticker,  # ticker를 metadata에 포함
                        "section": section,
                        "chunk_index": i,
                        "source": "10-K",
                    },
                }
            )

    if not documents:
        print("   ⚠️ 처리할 문서가 없습니다.")
        return

    # 3. 배치 업로드 (OpenAI Rate Limit 및 네트워크 고려)
    batch_size = 20  # 임베딩 배치 크기
    total_uploaded = 0

    print(f"   🚀 업로드 시작 (총 {len(documents)}개 청크)")

    # 기존 데이터 삭제 (metadata->ticker 기반)
    try:
        supabase.table("documents").delete().eq("metadata->>ticker", ticker).execute()
    except:
        pass  # 기존 데이터 없으면 무시

    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]

        try:
            # 임베딩 생성
            embeddings_response = openai_client.embeddings.create(
                input=[doc["content"] for doc in batch], model="text-embedding-3-small"
            )

            # 레코드에 id와 임베딩 추가
            records = []
            for j, doc in enumerate(batch):
                records.append(
                    {
                        "id": str(uuid.uuid4()),  # UUID 직접 생성
                        "content": doc["content"],
                        "metadata": doc["metadata"],
                        "embedding": embeddings_response.data[j].embedding,
                    }
                )

            # Supabase 저장
            supabase.table("documents").insert(records).execute()

            total_uploaded += len(batch)
            print(f"      Running... ({total_uploaded}/{len(documents)})", end="\r")

            # Rate limit 방지
            time.sleep(0.5)

        except Exception as e:
            print(f"\n   ❌ 오류 발생 (Batch {i}): {e}")
            time.sleep(5)

    print(f"\n   ✅ {ticker} 완료: {total_uploaded}개 청크 저장됨")


def main():
    print("=" * 60)
    print("🧠 10-K 문서 임베딩 및 Supabase 업로드")
    print("=" * 60)

    if not DATA_DIR.exists():
        print(f"❌ 데이터 디렉토리가 없습니다: {DATA_DIR}")
        return

    # 처리된 기업 목록 로드
    processed_companies_path = DATA_DIR / "processed_companies.csv"
    if processed_companies_path.exists():
        companies_df = pd.read_csv(processed_companies_path)
        tickers = companies_df["ticker"].tolist()
    else:
        # 디렉토리에서 직접 확인
        tickers = [d.name for d in DATA_DIR.iterdir() if d.is_dir()]

    print(f"📋 처리 대상: {len(tickers)}개 기업")

    for ticker in tickers:
        company_dir = DATA_DIR / ticker
        if company_dir.exists():
            try:
                process_company_documents(ticker, company_dir)
            except Exception as e:
                print(f"❌ {ticker} 처리 중 치명적 오류: {e}")


if __name__ == "__main__":
    main()
