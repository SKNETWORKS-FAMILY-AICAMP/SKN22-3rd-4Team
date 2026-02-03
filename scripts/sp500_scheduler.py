"""
S&P 500 기업 정보 수집 스케줄러
매일 새벽 5시(KST)에 S&P 500 기업 정보를 자동으로 수집합니다.

사용법:
    python scripts/sp500_scheduler.py          # 스케줄러 시작 (매일 05:00 KST 실행)
    python scripts/sp500_scheduler.py --test   # 즉시 1회 테스트 실행
    python scripts/sp500_scheduler.py --help   # 도움말
"""

import os
import sys
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Heavy imports moved to functions
# import pandas as pd
# import requests
# import yfinance as yf
# import pytz

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

# 로그 설정
LOG_DIR = project_root / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging():
    """로깅 설정"""
    log_file = LOG_DIR / f"scheduler_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger(__name__)


logger = setup_logging()

# Slack 알림 기능 제거됨 (User request)
# SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# def send_slack_notification(message: str, is_error: bool = False):
#     pass


def get_sp500_tickers() -> List[str]:
    """위키피디아에서 S&P 500 티커 목록 가져오기"""
    import requests
    import pandas as pd

    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        tables = pd.read_html(response.text)
        sp500_table = tables[0]

        # 티커 목록 추출 (. -> - 변환)
        tickers = sp500_table["Symbol"].str.replace(".", "-", regex=False).tolist()

        logger.info(f"✅ S&P 500 기업 {len(tickers)}개 티커 로드 완료")
        return tickers

    except Exception as e:
        logger.error(f"❌ S&P 500 티커 목록 가져오기 실패: {e}")
        return []


def fetch_company_info(ticker: str) -> Optional[Dict]:
    """yfinance로 기업 정보 수집 (단일 시도)"""
    import yfinance as yf

    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        if not info or "symbol" not in info:
            return None

        return {
            "ticker": ticker,
            "company_name": info.get("longName") or info.get("shortName", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "market_cap": info.get("marketCap", 0),
            "current_price": info.get("currentPrice")
            or info.get("regularMarketPrice", 0),
            "previous_close": info.get("previousClose", 0),
            "52_week_high": info.get("fiftyTwoWeekHigh", 0),
            "52_week_low": info.get("fiftyTwoWeekLow", 0),
            "pe_ratio": info.get("trailingPE"),
            "eps": info.get("trailingEps"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "volume": info.get("volume", 0),
            "avg_volume": info.get("averageVolume", 0),
            "website": info.get("website", ""),
            "description": (
                info.get("longBusinessSummary", "")[:500]
                if info.get("longBusinessSummary")
                else ""
            ),
            "country": info.get("country", ""),
            "exchange": info.get("exchange", ""),
            "currency": info.get("currency", "USD"),
            "collected_at": datetime.now(pytz.timezone("Asia/Seoul")).isoformat(),
        }

    except Exception as e:
        raise e


def fetch_company_info_with_retry(ticker: str) -> Optional[Dict]:
    """yfinance로 기업 정보 수집 (재시도 로직 포함)"""
    for attempt in range(MAX_RETRIES):
        try:
            result = fetch_company_info(ticker)
            if result:
                return result
            # 결과가 None이면 재시도하지 않음 (유효하지 않은 티커)
            return None
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY_BASE * (2**attempt)  # 지수 백오프
                logger.warning(
                    f"  ⚠️ {ticker}: 재시도 {attempt + 1}/{MAX_RETRIES} ({delay}초 후)"
                )
                time.sleep(delay)
            else:
                logger.warning(f"  ❌ {ticker}: 최종 실패 - {e}")
                return None
    return None


def save_to_supabase(data: List[Dict]) -> int:
    """Supabase에 데이터 저장 (upsert)"""
    import pytz

    try:
        from src.data.supabase_client import SupabaseClient

        client = SupabaseClient.get_client()

        success_count = 0

        for company in data:
            try:
                # company 테이블에 upsert (updated_at 포함)
                upsert_data = {
                    "ticker": company["ticker"],
                    "company_name": company["company_name"],
                    "sector": company["sector"],
                    "industry": company["industry"],
                    "market_cap": company["market_cap"],
                    "website": company["website"],
                    "exchange": company["exchange"],
                    "updated_at": datetime.now(pytz.timezone("Asia/Seoul")).isoformat(),
                }

                # upsert (ticker 기준)
                result = (
                    client.table("companies")
                    .upsert(upsert_data, on_conflict="ticker")
                    .execute()
                )

                if result.data:
                    success_count += 1

            except Exception as e:
                logger.warning(f"  ⚠️ {company['ticker']} DB 저장 실패: {e}")

        return success_count

    except Exception as e:
        logger.error(f"❌ Supabase 연결 오류: {e}")
        return 0


def save_to_csv(data: List[Dict], output_dir: Path = None):
    """데이터를 CSV로 저장 (백업용)"""
    import pandas as pd

    if not data:
        return

    output_dir = output_dir or (project_root / "data" / "processed")
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(data)

    # 날짜별 파일명
    date_str = datetime.now().strftime("%Y%m%d")
    csv_file = output_dir / f"sp500_data_{date_str}.csv"

    df.to_csv(csv_file, index=False, encoding="utf-8-sig")
    logger.info(f"💾 CSV 저장됨: {csv_file}")

    # JSON도 저장
    json_file = output_dir / f"sp500_data_{date_str}.json"
    df.to_json(json_file, orient="records", force_ascii=False, indent=2)
    logger.info(f"💾 JSON 저장됨: {json_file}")


def collect_sp500_data():
    """S&P 500 기업 정보 수집 메인 함수"""
    import pytz

    kst = pytz.timezone("Asia/Seoul")
    start_time = datetime.now(kst)

    logger.info("=" * 60)
    logger.info(
        f"🚀 S&P 500 데이터 수집 시작: {start_time.strftime('%Y-%m-%d %H:%M:%S KST')}"
    )
    logger.info("=" * 60)

    # 1. S&P 500 티커 목록 가져오기
    tickers = get_sp500_tickers()
    if not tickers:
        logger.error("❌ 티커 목록을 가져올 수 없습니다.")
        return

    # 2. 각 기업 정보 수집
    all_data = []
    success_count = 0
    failed_tickers = []  # 실패한 티커 목록

    logger.info(f"\n📊 {len(tickers)}개 기업 정보 수집 중...\n")

    for i, ticker in enumerate(tickers, 1):
        info = fetch_company_info_with_retry(ticker)

        if info:
            all_data.append(info)
            success_count += 1
            if i % 50 == 0:  # 50개마다 진행상황 출력
                logger.info(
                    f"  [{i:3d}/{len(tickers)}] 진행 중... (성공: {success_count})"
                )
        else:
            failed_tickers.append(ticker)

        # Rate limit 방지 (0.2초 딜레이)
        time.sleep(0.2)

    # 2-1. 실패한 티커들 마지막 재시도 (5분 후)
    if failed_tickers:
        logger.info(f"\n🔄 실패한 {len(failed_tickers)}개 티커 재시도 중...")
        time.sleep(5)  # 5초 대기 후 재시도

        retry_success = 0
        still_failed = []

        for ticker in failed_tickers:
            info = fetch_company_info_with_retry(ticker)
            if info:
                all_data.append(info)
                retry_success += 1
                logger.info(f"  ✅ {ticker}: 재시도 성공")
            else:
                still_failed.append(ticker)
            time.sleep(0.3)

        success_count += retry_success
        logger.info(
            f"  🔄 재시도 결과: 성공 {retry_success}개, 최종 실패 {len(still_failed)}개"
        )

        if still_failed:
            logger.info(
                f"  ❌ 최종 실패 티커: {', '.join(still_failed[:10])}{'...' if len(still_failed) > 10 else ''}"
            )

        failed_tickers = still_failed

    fail_count = len(failed_tickers)

    # 3. 결과 저장
    logger.info(f"\n{'=' * 60}")
    logger.info(f"📊 수집 완료: 성공 {success_count}개, 실패 {fail_count}개")

    # CSV/JSON 백업 저장
    save_to_csv(all_data)

    # Supabase 저장 (옵션)
    if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"):
        db_count = save_to_supabase(all_data)
        logger.info(f"🗄️ Supabase 저장: {db_count}개 기업")
    else:
        logger.info("⚠️ Supabase 설정 없음 - CSV/JSON만 저장됨")

    end_time = datetime.now(kst)
    duration = (end_time - start_time).total_seconds()

    logger.info(f"\n⏱️ 소요 시간: {duration:.1f}초")
    logger.info(f"✅ 수집 완료: {end_time.strftime('%Y-%m-%d %H:%M:%S KST')}")
    logger.info("=" * 60)

    # Slack 알림 발송 (제거됨)
    # if fail_count == 0:
    #     send_slack_notification(...)
    # else:
    #     send_slack_notification(...)


def run_scheduler():
    """스케줄러 시작"""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error("❌ APScheduler가 설치되지 않았습니다.")
        logger.error("   설치: pip install APScheduler")
        return

    kst = pytz.timezone("Asia/Seoul")
    scheduler = BlockingScheduler(timezone=kst)

    # 매일 새벽 5시(KST) 실행
    scheduler.add_job(
        collect_sp500_data,
        CronTrigger(hour=5, minute=0, timezone=kst),
        id="sp500_daily_collection",
        name="S&P 500 Daily Data Collection",
        replace_existing=True,
    )

    logger.info("=" * 60)
    logger.info("📅 S&P 500 스케줄러 시작")
    logger.info("   실행 시간: 매일 05:00 KST")
    logger.info("   종료: Ctrl+C")
    logger.info("=" * 60)

    # 다음 실행 시간 표시
    job = scheduler.get_job("sp500_daily_collection")
    try:
        # APScheduler 3.x 호환
        next_run_time = getattr(job, "next_run_time", None) or getattr(
            job, "next_run", None
        )
        if next_run_time:
            logger.info(
                f"\n⏰ 다음 실행: {next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            )
        else:
            logger.info("\n⏰ 스케줄러 시작 후 다음 실행 시간이 설정됩니다.")
    except Exception:
        logger.info("\n⏰ 스케줄러가 시작되었습니다.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("\n🛑 스케줄러 종료됨")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="S&P 500 기업 정보 수집 스케줄러",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python scripts/sp500_scheduler.py          # 스케줄러 시작 (매일 05:00 KST)
  python scripts/sp500_scheduler.py --test   # 즉시 1회 테스트 실행
        """,
    )

    parser.add_argument(
        "--test", "-t", action="store_true", help="즉시 1회 테스트 실행 (스케줄러 없이)"
    )

    args = parser.parse_args()

    if args.test:
        logger.info("🧪 테스트 모드: 즉시 실행")
        collect_sp500_data()
    else:
        run_scheduler()


if __name__ == "__main__":
    main()
