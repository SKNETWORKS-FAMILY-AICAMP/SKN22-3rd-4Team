import os
import sys
from pathlib import Path
import json
import pandas as pd
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from dotenv import load_dotenv

# Add src to path
# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from ragas.testset import TestsetGenerator
    from ragas.testset.synthesizers import (
        SingleHopSpecificQuerySynthesizer,
        MultiHopSpecificQuerySynthesizer,
        MultiHopAbstractQuerySynthesizer,
    )
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper

    # Load environment variables
    load_dotenv()
except ImportError as e:
    print(f"❌ ImportError: {e}")
    print(
        "💡 Please run 'pip install ragas pandas langchain_openai' to use this script."
    )
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)


from src.data.supabase_client import SupabaseClient

def load_documents_with_context(limit=50, offset=0):
    """Load documents and enrich with company info, financials, and relationships from Supabase."""
    print("⏳ Supabase에서 데이터 로딩 중...")

    # Initialize Supabase
    try:
        supabase = SupabaseClient.get_client()
    except Exception as e:
        print(f"❌ Supabase Client init failed: {e}")
        return []

    # 1. 문서 가져오기 (Limit sample size)
    print(f"📄 문서 샘플링 Limit: {limit}, Offset: {offset}")
    
    try:
        # Fetch documents using range for offset
        # limit() applies to the result set size, range() is for pagination
        res = supabase.table("documents").select("*").range(offset, offset + limit - 1).execute()
        documents = res.data
        if not documents:
            print("❌ 문서가 없습니다.")
            return []
        print(f"✅ {len(documents)}개의 문서를 가져왔습니다.")

        # 2. 관련 데이터 가져오기 (배치 처리가 좋지만 간단히 개별 조회 or 전체 조회)
        # 전체 회사 정보 가져오기 (캐싱)
        print("🏢 회사 정보 로딩...")
        res_comp = supabase.table("companies").select("*").execute()
        companies = {c['ticker']: c for c in res_comp.data}
        
        # 관계 정보 (Top relations)
        # 모든 관계를 가져오기엔 무거울 수 있으니 필요한 티커에 대해서만 추후 조회하거나
        # 지금은 간단히 최근 관계 1000개를 가져와서 매핑
        print("🕸️ 관계 정보 로딩...")
        res_rel = supabase.table("company_relationships").select("*").limit(2000).execute()
        relationships = {}
        for r in res_rel.data:
            src = r.get('source_ticker')
            if src:
                if src not in relationships:
                    relationships[src] = []
                relationships[src].append(f"{r.get('relationship_type')}: {r.get('target_company')}")
        
    except Exception as e:
        print(f"❌ 데이터 조회 실패: {e}")
        return []

    # 3. 문서 Enrich (Context 추가)
    langchain_docs = []

    for doc_data in documents:
        content = doc_data.get("content", "")
        metadata = doc_data.get("metadata") or {}
        
        ticker = metadata.get("ticker")
        
        context_parts = []
        
        # 회사 정보 추가
        if ticker and ticker in companies:
            comp = companies[ticker]
            k_name = comp.get("company_name", ticker) # company_name이 한국어라고 가정
            context_parts.append(f"Target Company: {k_name} ({ticker})")
            if comp.get("sector"):
                context_parts.append(f"Sector: {comp['sector']}")
        
        # 관계 정보 추가
        if ticker and ticker in relationships:
            # 상위 5개만
            top_rels = relationships[ticker][:5]
            context_parts.append("Relationships: " + ", ".join(top_rels))
            
        # Context 결합
        enrichment = "\n".join(context_parts) + "\n\n" if context_parts else ""
        full_content = enrichment + content
        
        # Metadata 업데이트
        if ticker in companies:
             metadata["korean_name"] = companies[ticker].get("company_name", ticker)

        doc = Document(page_content=full_content, metadata=metadata)
        langchain_docs.append(doc)
    
    return langchain_docs


def translate_to_korean(df, llm):
    """Translate Question and Ground Truth to Korean."""
    print("🇰🇷 생성된 질문과 답변을 한국어로 번역 중입니다...")

    # Translate to Korean
    try:
        from langchain_core.prompts import ChatPromptTemplate
    except ImportError:
        try:
            from langchain.prompts import ChatPromptTemplate
        except:
            print("❌ langchain.prompts import failed.")
            # Fallback or exit

    # Updated prompt to handle list/json formats if they appear
    translate_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful assistant that translates English text to natural Korean for a financial Q&A dataset. Preserve technical terms if appropriate.",
            ),
            ("user", "Translate the following to Korean:\n\n{text}"),
        ]
    )

    chain = translate_prompt | llm

    translated_questions = []
    translated_grounds = []

    total = len(df)
    for i, row in df.iterrows():
        # Robust column access for different Ragas versions
        question = row.get("question") or row.get("user_input") or ""
        ground_truth = row.get("ground_truth") or row.get("reference") or ""

        if i % 10 == 0:
            print(f"[{i+1}/{total}] 번역 중...")

        try:
            # Check if empty
            if not question:
                translated_questions.append("")
            else:
                q_trans = chain.invoke({"text": question}).content
                translated_questions.append(q_trans)
        except Exception as e:
            print(f"Translation failed for Q {i}: {e}")
            translated_questions.append(question)

        try:
            if not ground_truth:
                translated_grounds.append("")
            else:
                g_trans = chain.invoke({"text": ground_truth}).content
                translated_grounds.append(g_trans)
        except Exception as e:
            print(f"Translation failed for GT {i}: {e}")
            translated_grounds.append(ground_truth)

    df["question_korean"] = translated_questions
    df["ground_truth_korean"] = translated_grounds

    # Determine target columns for original storage (handle case where 'question' might not be in index yet)
    q_col = (
        "question"
        if "question" in df.columns
        else ("user_input" if "user_input" in df.columns else "question")
    )
    gt_col = (
        "ground_truth"
        if "ground_truth" in df.columns
        else ("reference" if "reference" in df.columns else "ground_truth")
    )

    df["question_korean"] = translated_questions
    df["ground_truth_korean"] = translated_grounds

    # Store original for reference, use Korean as main
    df[f"{q_col}_original"] = df[q_col]
    df[f"{gt_col}_original"] = df[gt_col]

    # Always ensure 'question' and 'ground_truth' exist for evaluators
    df["question"] = df["question_korean"]
    df["ground_truth"] = df["ground_truth_korean"]

    return df


def generate_dataset(limit=50, testset_size=20, offset=0, output_name="evaluation_dataset.csv"):
    print(f"🚀 데이터셋 생성 시작 (Limit: {limit}, Size: {testset_size}, Offset: {offset}, Out: {output_name})...")

    # 1. 문서 로드 (Offset/Limit 적용)
    documents = load_documents_with_context(limit=limit, offset=offset)
    if not documents:
        print("❌ 로드된 문서가 없습니다.")
        return

    # Generator 설정
    try:
        model_name = "gpt-4.1-mini"
        print(f"🤖 사용 모델: {model_name}")

        generator_llm = ChatOpenAI(model=model_name)
        critic_llm = ChatOpenAI(model=model_name)
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

        # Ragas Wrapper
        generator_llm_wrapped = LangchainLLMWrapper(generator_llm)
        critic_llm_wrapped = LangchainLLMWrapper(critic_llm)
        embeddings_wrapped = LangchainEmbeddingsWrapper(embeddings)

        generator = TestsetGenerator(
            llm=generator_llm_wrapped, embedding_model=embeddings_wrapped
        )

        print("⏳ Ragas 데이터셋 생성 (영어)...")

        # Synthesizer 설정
        syn_simple = SingleHopSpecificQuerySynthesizer(llm=generator_llm_wrapped)
        syn_multi = MultiHopSpecificQuerySynthesizer(llm=generator_llm_wrapped)
        syn_abstract = MultiHopAbstractQuerySynthesizer(llm=generator_llm_wrapped)

        syn_simple.embeddings = embeddings_wrapped
        syn_multi.embeddings = embeddings_wrapped
        syn_abstract.embeddings = embeddings_wrapped

        testset = generator.generate_with_langchain_docs(
            documents,
            testset_size=testset_size,
            query_distribution=[
                (syn_simple, 0.5),
                (syn_multi, 0.3),
                (syn_abstract, 0.2),
            ],
        )

        # 저장 준비
        project_root = Path(__file__).resolve().parent.parent
        output_dir = project_root / "data"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / output_name

        df = testset.to_pandas()

        # Rename columns 
        column_mapping = {
            "user_input": "question",
            "reference": "ground_truth",
            "reference_contexts": "contexts",
        }
        df = df.rename(
            columns={k: v for k, v in column_mapping.items() if k in df.columns}
        )

        # Translate to Korean
        df = translate_to_korean(df, generator_llm)

        df.to_csv(output_path, index=False)
        print(f"✅ 데이터셋 저장 완료: {output_path}")
        print(f"📊 생성된 데이터 개수: {len(df)}")

    except Exception as e:
        print(f"❌ 데이터셋 생성 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate evaluation dataset")
    parser.add_argument("--limit", type=int, default=50, help="Number of documents to load")
    parser.add_argument("--size", type=int, default=10, help="Size of testset to generate")
    parser.add_argument("--offset", type=int, default=0, help="Offset for document loading")
    parser.add_argument("--output", type=str, default="evaluation_dataset.csv", help="Output filename")
    
    args = parser.parse_args()
    
    generate_dataset(
        limit=args.limit, 
        testset_size=args.size, 
        offset=args.offset, 
        output_name=args.output
    )
