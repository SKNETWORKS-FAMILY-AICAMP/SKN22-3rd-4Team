import os
import sys
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from datasets import Dataset
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# Add project root to path (SKN22-3rd-4Team)
# Current file: SKN22-3rd-4Team/03_test_report/evaluate_rag.py
# .parent -> 03_test_report
# .parent.parent -> SKN22-3rd-4Team
root_path = Path(__file__).resolve().parent.parent
# Add project root to path
root_path = Path(__file__).resolve().parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from src.rag.analyst_chat import AnalystChatbot

try:
    # To fix TypeError: All metrics must be initialised metric objects
    # We revert to the simple import which provides instantiated metrics by default in this version.
    from ragas import evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_recall,
        context_precision,
    )
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
except ImportError:
    print("❌ Ragas library not found. Please install it: pip install ragas")
    sys.exit(1)

# Load environment variables
load_dotenv()


def evaluate_rag():
    print("🧪 RAG 성능 평가를 시작합니다 (Ragas Metrics)...")

    # 1. 데이터셋 로드
    # 1. 데이터셋 로드
    # evaluate_rag.py는 03_test_report 폴더 안에 있음
    current_dir = Path(__file__).resolve().parent
    dataset_path = current_dir / "data" / "evaluation_dataset.csv"

    if not dataset_path.exists():
        print(f"❌ 데이터셋을 찾을 수 없습니다: {dataset_path}")
        print("💡 먼저 generate_dataset.py를 실행하여 데이터셋을 생성해주세요.")
        return

    df = pd.read_csv(dataset_path)
    print(f"📄 총 {len(df)}개의 데이터 로드 완료.")

    # 2. 챗봇 초기화
    print("🤖 챗봇 초기화 중...")
    bot = AnalystChatbot()

    # 3. 답변 생성 (Inference)
    print("🚀 답변 생성 및 컨텍스트 추출 중...")

    answers = []
    contexts = []

    # Cost saving: Limit evaluation if dataset is huge, but usually it's small (50)
    # df = df.head(3)  # Uncomment to test with small subset

    for idx, row in df.iterrows():
        question = row.get("question")
        if not question:
            answers.append("")
            contexts.append([])
            continue

        print(f"Processing [{idx+1}/{len(df)}]: {question[:30]}...")

        try:
            # Extract ticker from context (Ground Truth) to simulate user selection
            # Context format: "['Target Company: Name (TICKER)...']"
            gt_context = row.get("contexts", "")
            ticker = None
            if gt_context and isinstance(gt_context, str):
                import re

                match = re.search(r"Target Company: .*? \((\w+)\)", gt_context)
                if match:
                    ticker = match.group(1)

            # Chatbot call
            response = bot.chat(question, ticker=ticker)

            # Extract answer
            answer_text = response.get("content", "")
            answers.append(answer_text)

            # Extract contexts (AnalystChatbot returns sources or we need to extract them)
            # Assuming bot output structure or we need to capture retrieved docs.
            # AnalystChatbot typically returns a dict. We need to check if it returns retrieved docs.
            # If not, we might need to modify AnalystChatbot or just use what we have.
            # For now, let's assume 'context' key or similar, or empty list if not available.
            # Ideally Ragas needs retrieved contexts.

            # If AnalystChatbot doesn't return contexts explicitly, Ragas metrics like Context Recall won't work well.
            # Let's try to grab 'sources' or 'context' from response if available.
            # Extract contexts
            # AnalystChatbot returns a single joined string with '##' headers.
            # Ragas performs better when given a list of individual document chunks.
            raw_context = response.get("context", "")
            if isinstance(raw_context, str) and raw_context:
                # Split by headers to create a list of context segments
                retrieved_ctx = [
                    segment.strip()
                    for segment in raw_context.split("##")
                    if segment.strip()
                ]
                # Re-add '##' if needed, or just leave as text. Ragas handles text.
                retrieved_ctx = [f"## {s}" for s in retrieved_ctx]
            else:
                retrieved_ctx = [] if not raw_context else [raw_context]

            contexts.append(retrieved_ctx)

        except Exception as e:
            print(f"Error generating response: {e}")
            answers.append("Error")
            contexts.append([])

    # 4. Ragas 평가 데이터 준비
    # Ragas expects: question, answer, contexts, ground_truth

    # Prepare HuggingFace Dataset
    eval_data = {
        "question": df["question"].tolist(),
        "answer": answers,
        "contexts": contexts,
        "ground_truth": df["ground_truth"].tolist(),
    }

    # Remove rows with empty answers or errors for cleaner evaluation
    # (Optional, but Ragas might crash on empty inputs)

    ragas_dataset = Dataset.from_dict(eval_data)

    # 5. 평가 실행 in Ragas
    print("📊 Ragas 메트릭 평가 실행 중...")

    # Configure LLM for Judge
    judge_llm = ChatOpenAI(model="gpt-4.1-mini")
    judge_embeddings = OpenAIEmbeddings()

    # Wrap for Ragas
    # newer Ragas versions might not need wrapper if passed directly, but safer with wrapper
    # metrics usually take 'llm' argument in their init or evaluate takes 'llm'

    # Note: providing llm to evaluate() is the modern way

    result = evaluate(
        ragas_dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_recall,
            context_precision,
        ],
        llm=judge_llm,
        embeddings=judge_embeddings,
    )

    print("\n📈 평가 결과:")
    print(result)

    # 6. 저장
    output_df = result.to_pandas()
    output_path = "03_test_report/data/evaluation_results_ragas.csv"
    output_df.to_csv(output_path, index=False)
    print(f"✅ 결과 저장 완료: {output_path}")


if __name__ == "__main__":
    evaluate_rag()
