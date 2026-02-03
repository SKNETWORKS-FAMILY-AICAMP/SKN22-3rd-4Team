# 01. 데이터 수집 및 전처리 (Data Preprocessing)

## 📌 개요
이 디렉토리는 프로젝트에서 사용하는 금융 데이터의 수집, 전처리, 그리고 지식 그래프(Knowledge Graph) 구축 과정에 대한 문서를 관리합니다.

## 🔄 데이터 파이프라인 (Data Pipeline)

### 1. Raw 데이터 수집
- **소스**: SEC 공시 자료(10-K, 10-Q), 금융 뉴스 기사
- **저장소**: Supabase `documents` 테이블
- **주요 컬럼**: `id`, `content` (본문), `metadata` (티커, 날짜 등)

### 2. 관계 데이터 추출 (ETL)
비정형 텍스트에서 구조화된 기업 관계 데이터를 추출하는 과정입니다.
- **실행 스크립트**: `scripts/build_company_relationships.py`
- **사용 모델**: OpenAI GPT-4.1-mini
- **추출 방식**: 
  - 텍스트 본문 분석 -> `(Source Company, Target Company, Relationship Type)` 트리플렛 추출
  - 병렬 처리(Parallel Processing)를 통해 대량의 문서 처리

### 3. 데이터 적재 (Loading)
- **저장소**: Supabase `company_relationships` 테이블
- **활용**: GraphRAG 엔진에서 `NetworkX` 그래프로 변환하여 분석에 사용

## 📊 데이터 스키마

### `documents` (원본 문서)
| Column | Type | Description |
|--------|------|-------------|
| id | uuid | 고유 ID |
| content | text | 문서 본문 |
| metadata | jsonb | `{"ticker": "AAPL", "date": "2024-01-01"}` |
| embedding | vector | 벡터 검색용 임베딩 (1536 dim) |

### `company_relationships` (관계 데이터)
| Column | Type | Description |
|--------|------|-------------|
| id | int8 | 고유 ID |
| source_ticker | text | 기준 기업 티커 (예: AAPL) |
| target_ticker | text | 대상 기업 티커 (예: TSM) |
| relationship_type | text | 관계 유형 (supplier, customer, competitor 등) |
| confidence | float | 신뢰도 점수 (0.0 ~ 1.0) |
| extracted_from | uuid | 출처 문서 ID (`documents.id` FK) |
