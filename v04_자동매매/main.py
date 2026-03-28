"""
미장 단타 시스템 — 메인 오케스트레이터.

전체 파이프라인:
  Step 1: 매크로 + 스마트머니 수집
  Step 2: AI 역추론 + 로직체인 매칭
  Step 3: 종목 1차 필터링
  Step 4: 차트 세력 흔적 스코어링
  Step 5: 통합 스코어링 + AI 최종 판단 → 매수 추천

Usage:
  python main.py                  # 전체 파이프라인 1회 실행
  python main.py --phase0         # 로직체인 DB 초기 구축
  python main.py --loop           # 스케줄러 모드 (5분 주기)
"""

import argparse
import json
import logging
import time
from datetime import datetime

# ── 노이즈 로거 억제 ──────────────────────────────────────
logging.basicConfig(level=logging.WARNING)
for noisy in ["httpx", "httpcore", "yfinance", "peewee",
              "sentence_transformers", "transformers", "chromadb",
              "google_genai", "urllib3", "requests", "tqdm"]:
    logging.getLogger(noisy).setLevel(logging.ERROR)

logger = logging.getLogger("main")
logger.setLevel(logging.INFO)

# 심플 포맷 (시간 없음)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_handler)
logger.propagate = False


def run_phase0(count_per_category: int = 25):
    """Phase 0: 로직체인 DB 초기 구축."""
    from src.phase0.embed_chains import embed_and_store
    from src.phase0.generate_chains import generate_all_chains

    logger.info("=" * 60)
    logger.info("Phase 0: Generating Logic Chain DB...")
    logger.info("=" * 60)

    chains = generate_all_chains(count_per_category=count_per_category)
    if chains:
        total = embed_and_store(chains)
        logger.info(f"Phase 0 complete: {total} chains in ChromaDB")
    else:
        logger.error("No chains generated!")


def _print_step(n: int, title: str):
    logger.info(f"\n{'─'*50}")
    logger.info(f"  STEP {n}  {title}")
    logger.info(f"{'─'*50}")


def run_pipeline():
    """전체 파이프라인 1회 실행."""
    from tqdm import tqdm

    from src.step1_collect.macro_collector import collect_all_macro
    from src.step1_collect.smart_money import collect_smart_money_signals
    from src.step2_inference.reverse_inference import run_reverse_inference
    from src.step3_filter.stock_screener import discover_tickers_for_sectors, screen_single_stock
    from src.step4_chart.data_fetcher import fetch_ohlcv
    from src.step4_chart.pattern_detector import score_patterns
    from src.step4_chart.technical_score import score_technical
    from src.step5_scoring.final_judge import judge_stock
    from src.step5_scoring.score_engine import rank_stocks, score_stock
    from src.utils.config import MIN_SCORE

    start = time.time()
    logger.info(f"\n{'═'*50}")
    logger.info(f"  미장 단타 분석  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"{'═'*50}")

    # ── Step 1 ───────────────────────────────────────────────
    _print_step(1, "매크로 데이터 수집")
    macro_result = collect_all_macro()
    vix = macro_result.get("vix", {})
    anomalies = macro_result.get("anomalies", [])
    logger.info(f"  VIX     : {vix.get('vix','?')}  ({vix.get('zone','?')})  보너스 +{vix.get('bonus',0)}")
    logger.info(f"  이상신호 : {len(anomalies)}개  " +
                (f"→ {', '.join(a.get('source', a.get('indicator','?')) for a in anomalies[:3])}" if anomalies else "없음"))

    # ── Step 2 ───────────────────────────────────────────────
    _print_step(2, "AI 역추론 + 로직체인 매칭")
    smart_money_result = {"insider_trades": [], "volume_surges": [], "short_interest": {}, "anomalies": []}
    inference_result = run_reverse_inference(macro_result, smart_money_result)
    beneficiary_sectors = inference_result.get("beneficiary_sectors", [])
    scenarios = inference_result.get("scenarios", [])
    matched_chains = inference_result.get("matched_chains", [])

    logger.info(f"  시나리오  : {len(scenarios)}개")
    logger.info(f"  매칭체인  : {len(matched_chains)}개")
    logger.info(f"  수혜섹터  : {', '.join(beneficiary_sectors) if beneficiary_sectors else '없음'}")
    for i, sc in enumerate(scenarios[:3], 1):
        prob = sc.get("probability", 0)
        name = sc.get("scenario", sc.get("name", "?"))
        horizon = sc.get("time_horizon", "?")
        logger.info(f"  시나리오{i} : [{prob*100:.0f}%] {name}  ({horizon})")

    if not beneficiary_sectors and not scenarios:
        logger.info("\n  ⚠ 액션 가능한 신호 없음. 종료.")
        return

    # ── Step 3 ───────────────────────────────────────────────
    _print_step(3, "종목 필터링")
    candidate_tickers = discover_tickers_for_sectors(beneficiary_sectors)
    logger.info(f"  AI 후보  : {len(candidate_tickers)}개 티커")

    if not candidate_tickers:
        logger.info("  ⚠ 후보 없음. 종료.")
        return

    passed_stocks = []
    with tqdm(candidate_tickers, desc="  스크리닝", ncols=70, leave=False) as bar:
        for ticker in bar:
            result = screen_single_stock(ticker)
            if result:
                passed_stocks.append(result)
            bar.set_postfix(passed=len(passed_stocks))

    logger.info(f"  통과     : {len(passed_stocks)}/{len(candidate_tickers)}개")

    if not passed_stocks:
        logger.info("  ⚠ 통과 종목 없음. 종료.")
        return

    passed_tickers = [s["ticker"] for s in passed_stocks]
    smart_money_result = collect_smart_money_signals(passed_tickers)

    # ── Step 4 ───────────────────────────────────────────────
    _print_step(4, "차트 스코어링")
    chart_scores = {}
    with tqdm(passed_stocks, desc="  차트분석", ncols=70, leave=False) as bar:
        for stock in bar:
            ticker = stock["ticker"]
            bar.set_postfix(ticker=ticker)
            df = fetch_ohlcv(ticker, interval="1d", days=365)
            if df is not None:
                tech = score_technical(df)
                pattern = score_patterns(df)
                chart_scores[ticker] = {"technical": tech, "pattern": pattern}

    logger.info(f"  완료     : {len(chart_scores)}/{len(passed_stocks)}개")

    # ── Step 5 ───────────────────────────────────────────────
    _print_step(5, "통합 스코어링")
    scored_stocks = []
    for stock in passed_stocks:
        ticker = stock["ticker"]
        charts = chart_scores.get(ticker, {"technical": {"total": 0}, "pattern": {"total": 0}})
        scored = score_stock(
            ticker=ticker,
            stock_info=stock,
            matched_chains=matched_chains,
            scenarios=scenarios,
            smart_money_result=smart_money_result,
            vix_data=vix,
            technical_result=charts["technical"],
            pattern_result=charts["pattern"],
        )
        scored_stocks.append(scored)

    ranked = rank_stocks(scored_stocks)

    logger.info(f"\n  {'순위':<4} {'티커':<7} {'점수':>5}  LC  SM   V   C  VIX  R   섹터/테마")
    logger.info(f"  {'─'*70}")
    for s in ranked[:10]:
        bd = s["breakdown"]
        sector = s.get("sector", s.get("matched_sector", "-"))
        logger.info(
            f"  #{s['rank']:<3} {s['ticker']:<7} {s['total_score']:>5.1f}"
            f"  {bd['logic_chain_score']:>3.0f} {bd['smart_money_score']:>3.0f}"
            f" {bd['volume_score']:>3.0f} {bd['chart_score']:>3.0f}"
            f"  +{bd['vix_bonus']:>2.0f} {bd['risk_penalty']:>3.0f}"
            f"  [{s['confidence']}]  {sector}"
        )

    # AI 최종 판단
    top_candidates = [s for s in ranked if s["total_score"] >= MIN_SCORE][:5]
    if top_candidates:
        logger.info(f"\n  AI 최종판단 ({len(top_candidates)}개)...")
        for candidate in tqdm(top_candidates, desc="  AI판단", ncols=70, leave=False):
            judgment = judge_stock(candidate, scenarios, matched_chains)
            action = judgment["action"].upper()
            reason = judgment.get("reasoning", "")[:60]
            if judgment["action"] == "buy":
                logger.info(
                    f"  ✅ {candidate['ticker']:6s} {action}"
                    f"  목표 ${judgment['target_price']:.2f}"
                    f"  손절 ${judgment['stop_loss']:.2f}"
                    f"  보유 {judgment.get('hold_days','?')}일"
                    f"\n     {reason}"
                )
            else:
                logger.info(f"  ❌ {candidate['ticker']:6s} {action}  {reason}")
    else:
        logger.info(f"\n  최소 점수({MIN_SCORE}) 미달 종목 없음.")

    duration = time.time() - start

    from src.utils.gemini_client import get_search_usage_summary
    su = get_search_usage_summary()
    logger.info(f"\n{'═'*50}")
    logger.info(f"  완료  {duration:.0f}초")
    logger.info(
        f"  검색쿼리  이번달 {su['this_month']}회"
        f" / 무료잔여 {su['free_remaining']}회"
        + (f"  ⚠ 초과 {su['overage_queries']}회 (${su['overage_cost_usd']})" if su['overage_queries'] else "")
    )
    logger.info(f"{'═'*50}\n")

    _save_run_result(ranked, macro_result, inference_result, duration)


def _save_run_result(ranked, macro_result, inference_result, duration):
    """실행 결과를 JSON으로 저장."""
    from src.utils.config import DATA_DIR

    results_dir = DATA_DIR / "collected"
    results_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "timestamp": datetime.now().isoformat(),
        "duration_sec": round(duration, 2),
        "vix": macro_result.get("vix", {}),
        "anomalies": macro_result.get("anomalies", []),
        "scenarios": inference_result.get("scenarios", []),
        "matched_chains": inference_result.get("matched_chains", []),  # 상세 포함
        "beneficiary_sectors": inference_result.get("beneficiary_sectors", []),
        "rankings": ranked[:20],  # Top 20
    }

    filename = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    json_path = results_dir / filename
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    from src.utils.report import generate_report
    generate_report(result, json_path)

    logger.info(f"  저장: {filename}  (.json + .md)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="미장 단타 분석 시스템")
    parser.add_argument("--phase0", action="store_true", help="로직체인 DB 초기 구축")
    parser.add_argument("--phase0-count", type=int, default=25, help="카테고리당 체인 수")
    parser.add_argument("--loop", action="store_true", help="스케줄러 모드 (5분 주기)")
    args = parser.parse_args()

    if args.phase0:
        run_phase0(count_per_category=args.phase0_count)
    elif args.loop:
        logger.info("Starting scheduler mode (5-min interval)...")
        while True:
            try:
                run_pipeline()
            except Exception as e:
                logger.error(f"Pipeline error: {e}", exc_info=True)
            logger.info("Sleeping 5 minutes...")
            time.sleep(300)
    else:
        run_pipeline()
