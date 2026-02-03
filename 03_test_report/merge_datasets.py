import pandas as pd
from pathlib import Path
import sys

def merge_csvs():
    # 프로젝트 루트 기준 data 폴더 찾기
    # 현재 파일 위치: 03_test_report/merge_datasets.py
    # data 폴더 위치: 03_test_report/data/ (같은 디렉토리 내의 data 폴더)
    current_dir = Path(__file__).resolve().parent
    data_dir = current_dir / "data"
    
    print(f"📂 데이터 폴더: {data_dir}")
    
    # part_*.csv 패턴의 모든 파일 찾기
    files = sorted(list(data_dir.glob("part_*.csv")))
    
    if not files:
        print("❌ 병합할 파일(part_*.csv)이 없습니다.")
        return

    print(f"📦 {len(files)}개의 파일을 발견했습니다: {[f.name for f in files]}")
    
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f)
            print(f"  - {f.name}: {len(df)}개 데이터")
            dfs.append(df)
        except Exception as e:
            print(f"⚠️ {f.name} 읽기 실패: {e}")

    if not dfs:
        print("❌ 병합할 유효한 데이터가 없습니다.")
        return

    # 하나로 합치기
    merged_df = pd.concat(dfs, ignore_index=True)
    
    # 중복 제거 (혹시 모르니 question 기준으로)
    initial_len = len(merged_df)
    merged_df.drop_duplicates(subset=["question"], inplace=True)
    final_len = len(merged_df)
    
    if initial_len != final_len:
        print(f"🧹 중복 제거: {initial_len} -> {final_len} ({initial_len - final_len}개 삭제됨)")

    output_path = data_dir / "evaluation_dataset.csv"
    
    merged_df.to_csv(output_path, index=False)
    print("="*50)
    print(f"✅ 병합 완료! 총 {len(merged_df)}개의 데이터가 저장되었습니다.")
    print(f"📂 저장 위치: {output_path}")
    print("="*50)

if __name__ == "__main__":
    merge_csvs()
