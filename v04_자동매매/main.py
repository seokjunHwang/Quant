"""
미장 단타 자동매매 시스템 — 메인 오케스트레이터.

전체 파이프라인:
  Step 1: 매크로 + 스마트머니 수집
  Step 2: AI 역추론 + 로직체인 매칭
  Step 3: 종목 1차 필터링
  Step 4: 차트 세력 흔적 스코어링
  Step 5: 통합 스코어링 + AI 최종 판단
  Step 6: 포지션 관리 (매수/청산)

Usage:
  python main.py                  # 전체 파이프라인 1회 실행
  python main.py --phase0         # 로직체인 DB 초기 구축
  python main.py --loop           # 스케줄러 모드 (5분 주기)
  python main.py --status         # 계좌/포지션 상태 확인
"""

import argparse
import json
import logging
import time
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


def run_phase0(count_per_category: int = 50):
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


def run_pipeline():
    """전체 파이프라인 1회 실행."""
    from src.step1_collect.macro_collector import collect_all_macro
    from src.step1_collect.smart_money import collect_smart_money_signals
    from src.step2_inference.reverse_inference import run_reverse_inference
    from src.step3_filter.stock_screener import discover_tickers_for_sectors, screen_sector_stocks
    from src.step4_chart.data_fetcher import fetch_ohlcv
    from src.step4_chart.pattern_detector import score_patterns
    from src.step4_chart.technical_score import score_technical
    from src.step5_scoring.final_judge import judge_stock
    from src.step5_scoring.score_engine import rank_stocks, score_stock
    from src.step6_execution.order_manager import (
        can_open_new_position,
        check_exit_conditions,
        get_positions,
        submit_sell_order,
    )
    from src.utils.config import MIN_SCORE

    start = time.time()

    # ── Step 1: 데이터 수집 ──────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 1: Collecting macro & smart money data...")

    macro_result = collect_all_macro()
    vix = macro_result.get("vix", {})
    logger.info(f"  VIX: {vix.get('vix', '?')} ({vix.get('zone', '?')}, bonus +{vix.get('bonus', 0)})")
    logger.info(f"  Macro anomalies: {len(macro_result.get('anomalies', []))}")

    # ── Step 2: AI 역추론 ────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 2: Running AI reverse inference...")

    # Initial smart money scan on a watchlist (can be expanded)
    # For now, skip per-ticker smart money until we have candidate tickers
    smart_money_result = {"insider_trades": [], "volume_surges": [], "short_interest": {}, "anomalies": []}

    inference_result = run_reverse_inference(macro_result, smart_money_result)
    beneficiary_sectors = inference_result.get("beneficiary_sectors", [])
    scenarios = inference_result.get("scenarios", [])
    matched_chains = inference_result.get("matched_chains", [])

    logger.info(f"  Scenarios: {len(scenarios)}")
    logger.info(f"  Matched chains: {len(matched_chains)}")
    logger.info(f"  Beneficiary sectors: {beneficiary_sectors}")

    if not beneficiary_sectors and not scenarios:
        logger.info("No actionable signals. Pipeline complete.")
        return

    # ── Step 3: 종목 필터링 ──────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 3: Filtering stocks...")

    # Discover tickers from sectors
    candidate_tickers = discover_tickers_for_sectors(beneficiary_sectors)
    logger.info(f"  Candidates from AI: {len(candidate_tickers)} tickers")

    if not candidate_tickers:
        logger.info("No candidate tickers found. Pipeline complete.")
        return

    # Screen stocks
    passed_stocks = screen_sector_stocks(beneficiary_sectors, candidate_tickers)
    logger.info(f"  Passed screening: {len(passed_stocks)}")

    if not passed_stocks:
        logger.info("No stocks passed screening. Pipeline complete.")
        return

    # Collect smart money signals for passed stocks
    passed_tickers = [s["ticker"] for s in passed_stocks]
    smart_money_result = collect_smart_money_signals(passed_tickers)

    # ── Step 4: 차트 스코어링 ────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 4: Chart & pattern scoring...")

    chart_scores = {}
    for stock in passed_stocks:
        ticker = stock["ticker"]
        df = fetch_ohlcv(ticker, interval="1d", days=365)
        if df is not None:
            tech = score_technical(df)
            pattern = score_patterns(df)
            chart_scores[ticker] = {"technical": tech, "pattern": pattern}
            logger.info(
                f"  {ticker}: tech={tech['total']}, pattern={pattern['total']}"
            )

    # ── Step 5: 통합 스코어링 ────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 5: Integrated scoring...")

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

    logger.info("\n  === FINAL RANKINGS ===")
    for s in ranked[:10]:
        bd = s["breakdown"]
        logger.info(
            f"  #{s['rank']} {s['ticker']:6s} — {s['total_score']:5.1f}pt "
            f"(LC={bd['logic_chain_score']:.0f} SM={bd['smart_money_score']:.0f} "
            f"V={bd['volume_score']:.0f} C={bd['chart_score']:.0f} "
            f"VIX=+{bd['vix_bonus']:.0f} R={bd['risk_penalty']:.0f}) "
            f"[{s['confidence']}]"
        )

    # AI final judgment on top candidates
    top_candidates = [s for s in ranked if s["total_score"] >= MIN_SCORE][:5]

    if top_candidates:
        logger.info(f"\n  AI judging {len(top_candidates)} candidates...")

        for candidate in top_candidates:
            judgment = judge_stock(candidate, scenarios, matched_chains)
            logger.info(
                f"  {candidate['ticker']}: {judgment['action'].upper()} "
                f"— {judgment.get('reasoning', '')[:80]}"
            )

            if judgment["action"] == "buy":
                logger.info(
                    f"    Target: ${judgment['target_price']:.2f}, "
                    f"Stop: ${judgment['stop_loss']:.2f}, "
                    f"Hold: {judgment.get('hold_days', '?')}d"
                )
    else:
        logger.info("  No candidates above minimum score threshold.")

    # ── Step 6: 포지션 관리 ──────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 6: Position management...")

    # Check existing positions for exit conditions
    positions = get_positions()
    for pos in positions:
        exit_signal = check_exit_conditions(pos, vix)
        if exit_signal:
            logger.info(
                f"  EXIT SIGNAL: {exit_signal['ticker']} — {exit_signal['reason']} "
                f"(PnL: {exit_signal['pnl_pct']:.1f}%)"
            )
            # In paper mode, auto-sell
            submit_sell_order(exit_signal["ticker"], int(pos["qty"]))

    duration = time.time() - start
    logger.info("=" * 60)
    logger.info(f"Pipeline complete in {duration:.1f}s")

    # Save results
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
        "anomaly_count": len(macro_result.get("anomalies", [])),
        "scenarios": inference_result.get("scenarios", []),
        "matched_chains": len(inference_result.get("matched_chains", [])),
        "beneficiary_sectors": inference_result.get("beneficiary_sectors", []),
        "rankings": ranked[:20],  # Top 20
    }

    filename = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_dir / filename, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"Results saved: {filename}")


def run_status():
    """현재 상태 확인."""
    from src.feedback.trade_logger import get_performance_summary
    from src.step6_execution.order_manager import get_account_info, get_positions

    account = get_account_info()
    positions = get_positions()
    perf = get_performance_summary()

    print("\n=== ACCOUNT ===")
    if account:
        print(f"  Equity: ${account['equity']:,.2f}")
        print(f"  Cash: ${account['cash']:,.2f}")
        print(f"  Buying Power: ${account['buying_power']:,.2f}")
    else:
        print("  Not connected (check API keys)")

    print(f"\n=== POSITIONS ({len(positions)}) ===")
    for p in positions:
        print(
            f"  {p['ticker']:6s} x{p['qty']:.0f} @ ${p['avg_entry']:.2f} "
            f"→ ${p['current_price']:.2f} ({p['unrealized_pnl_pct']:+.1f}%)"
        )

    print("\n=== PERFORMANCE ===")
    print(f"  Total trades: {perf.get('total_trades', 0)}")
    print(f"  Win rate: {perf.get('win_rate', 0):.1f}%")
    print(f"  Avg PnL: {perf.get('avg_pnl_pct', 0):+.2f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="미장 단타 자동매매 시스템")
    parser.add_argument("--phase0", action="store_true", help="로직체인 DB 초기 구축")
    parser.add_argument("--phase0-count", type=int, default=50, help="카테고리당 체인 수")
    parser.add_argument("--loop", action="store_true", help="스케줄러 모드 (5분 주기)")
    parser.add_argument("--status", action="store_true", help="계좌/포지션 상태 확인")

    args = parser.parse_args()

    if args.phase0:
        run_phase0(count_per_category=args.phase0_count)
    elif args.status:
        run_status()
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
