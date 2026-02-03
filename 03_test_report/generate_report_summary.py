import pandas as pd
import os


def generate_markdown_summary():
    dataset_path = "03_test_report/data/evaluation_dataset.csv"
    results_path = "03_test_report/data/evaluation_results_ragas.csv"

    print("# 📊 테스트 결과 자동 요약\n")

    # 1. 데이터셋 요약
    if os.path.exists(dataset_path):
        df_ds = pd.read_csv(dataset_path)
        print("## [데이터셋 생성 현황]")
        print(f"- 생성된 총 질문 수: {len(df_ds)}개")
        print("- 문서 원천: data/10k_documents (S&P 500)")
        print("\n")
    else:
        print("⚠️ evaluation_dataset.csv 파일이 아직 생성되지 않았습니다.")

    # 2. 평가 결과 요약 (Ragas)
    if os.path.exists(results_path):
        df_res = pd.read_csv(results_path)
        print("## [Ragas 성능 평가 결과]")
        print(f"- 테스트 수행 건수: {len(df_res)}개")

        # Ragas 지표 평균 계산
        metrics = [
            "faithfulness",
            "answer_relevancy",
            "context_recall",
            "context_precision",
        ]
        for metric in metrics:
            if metric in df_res.columns:
                avg_val = df_res[metric].mean()
                print(f"- 평균 {metric.replace('_', ' ').title()}: {avg_val:.4f}")

        print("\n### 상세 결과 (샘플 5건)")
        # user_input, response, reference 등의 컬럼명이 Ragas 결과에 있음
        display_cols = ["user_input", "faithfulness", "answer_relevancy"]
        available_cols = [c for c in display_cols if c in df_res.columns]
        if available_cols:
            sample = df_res[available_cols].head(5)
            print(sample.to_markdown(index=False))
    else:
        print(f"\n⚠️ {results_path} 파일이 아직 생성되지 않았습니다.")
        print("💡 `python 03_test_report/evaluate_rag.py`를 먼저 실행해주세요.")


if __name__ == "__main__":
    generate_markdown_summary()
