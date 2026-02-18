"""Pipeline CLI Orchestrator — Manual Curation + Auto Pipeline.

3 Modes:
    python -m ai.pipeline.main test <file.pine> --asset BTC/USDT --period 2023-01-01:2024-12-31
    python -m ai.pipeline.main combine --asset BTC/USDT --period 2023-01-01:2024-12-31
    python -m ai.pipeline.main verify <file.pine> --asset BTC/USDT --recent 100

Individual stages:
    python -m ai.pipeline.main convert [file.pine] [--force]
    python -m ai.pipeline.main analyze
    python -m ai.pipeline.main status
"""

import argparse
import sys
import os
from pathlib import Path

# Ensure v02/ is on the Python path
_v02_root = Path(__file__).resolve().parent.parent.parent
if str(_v02_root) not in sys.path:
    sys.path.insert(0, str(_v02_root))

from ai.pipeline.utils.logger import get_logger
from ai.pipeline.utils.db import PipelineDB

logger = get_logger("pipeline")


def _parse_period(period_str: str) -> tuple[str, str]:
    """Parse period string like '2023-01-01:2024-12-31' into (start, end)."""
    if ":" in period_str:
        parts = period_str.split(":")
        return parts[0], parts[1]
    # Try named periods from config
    return period_str, period_str


def _resolve_pine_path(filename: str) -> Path:
    """Resolve a .pine filename to its full path."""
    from ai.pipeline.converter import PINE_DIR

    path = Path(filename)
    if path.exists():
        return path
    # Try in pine/ directory
    pine_path = PINE_DIR / filename
    if pine_path.exists():
        return pine_path
    # Try adding .pine extension
    if not filename.endswith(".pine"):
        pine_path = PINE_DIR / f"{filename}.pine"
        if pine_path.exists():
            return pine_path
    return pine_path  # Return even if not found — error handled downstream


# ═══════════════════════════════════════════════════════════
# Mode 1: Single Indicator Test
# ═══════════════════════════════════════════════════════════

def cmd_test(args):
    """Test a single Pine Script indicator end-to-end."""
    from ai.pipeline.input_manager import scan_pine_directory
    from ai.pipeline.converter import convert_pine_script, load_converted_module
    from ai.pipeline.backtester.data_fetcher import fetch_ohlcv
    from ai.pipeline.backtester.engine import run_backtest

    db = PipelineDB()
    pine_path = _resolve_pine_path(args.file)
    indicator_id = pine_path.stem
    start, end = _parse_period(args.period)

    logger.info(f"=== Mode 1: Single Indicator Test ===")
    logger.info(f"Indicator: {indicator_id}")
    logger.info(f"Asset: {args.asset}, Period: {start} ~ {end}, TF: {args.tf}")

    # Step 1: Scan & register
    logger.info("\n[1/4] Registering indicator...")
    scan_pine_directory(db)

    # Step 2: Convert (skip if already converted and not forced)
    logger.info("\n[2/4] Converting Pine Script → Python...")
    existing_module = load_converted_module(indicator_id)
    if existing_module is not None and not args.force:
        logger.info(f"Already converted: {indicator_id}.py (use --force to reconvert)")
    else:
        out_path = convert_pine_script(pine_path, force=args.force)
        if out_path is None:
            logger.error("Conversion failed. Check the Pine Script and retry.")
            return
        from datetime import datetime as dt
        db.update_indicator_status(indicator_id, "converted", converted_at=dt.now().isoformat())

    # Step 3: Load & generate signals
    logger.info("\n[3/4] Generating signals...")
    module = load_converted_module(indicator_id)
    if module is None:
        logger.error("Failed to load converted module.")
        return

    df = fetch_ohlcv(args.asset, args.tf, start, end)
    if df.empty:
        logger.error("No data fetched. Check asset/period.")
        return

    params = getattr(module, "METADATA", {}).get("default_params", {})
    try:
        df_signals = module.generate_signals(df, **params)
    except Exception as e:
        logger.error(f"Signal generation failed: {e}")
        return

    buy_count = (df_signals["signal"] == 1).sum()
    sell_count = (df_signals["signal"] == -1).sum()
    logger.info(f"Signals: {buy_count} buys, {sell_count} sells out of {len(df_signals)} bars")

    # Step 4: Backtest
    logger.info("\n[4/4] Running backtest...")
    result = run_backtest(
        df_signals,
        initial_capital=args.capital,
        commission_pct=args.commission,
        slippage_pct=args.slippage,
    )

    # Save to DB
    db.insert_backtest_result({
        "strategy_id": f"SINGLE_{indicator_id}",
        "asset": args.asset,
        "timeframe": args.tf,
        "period_start": start,
        "period_end": end,
        **result.metrics,
    })

    # Print results
    logger.info(f"\n{'='*50}")
    logger.info(f"Backtest Results: {indicator_id}")
    logger.info(f"Asset: {args.asset} | Period: {start} ~ {end} | TF: {args.tf}")
    logger.info(f"{'='*50}")
    print(result.summary())
    logger.info(f"{'='*50}")


# ═══════════════════════════════════════════════════════════
# Mode 2: Multi-Indicator Fusion
# ═══════════════════════════════════════════════════════════

def cmd_combine(args):
    """Combine all indicators and run backtesting pipeline."""
    from ai.pipeline.input_manager import scan_pine_directory
    from ai.pipeline.converter import convert_all
    from ai.pipeline.analyzer import analyze_all
    from ai.pipeline.combiner import generate_combinations
    from ai.pipeline.backtester.data_fetcher import fetch_ohlcv
    from ai.pipeline.backtester.engine import run_backtest

    db = PipelineDB()
    start, end = _parse_period(args.period)

    logger.info(f"=== Mode 2: Multi-Indicator Fusion ===")
    logger.info(f"Asset: {args.asset}, Period: {start} ~ {end}, TF: {args.tf}")

    # Step 1: Scan
    logger.info("\n[1/6] Scanning pine/ directory...")
    scan_stats = scan_pine_directory(db)

    # Step 2: Convert all
    logger.info("\n[2/6] Converting Pine Scripts...")
    convert_stats = convert_all(force=args.force)

    # Auto-verify converted indicators (skip manual verify in combine mode)
    converted = db.get_indicators_by_status("converted")
    for ind in converted:
        db.update_indicator_status(ind["id"], "verified")
    if converted:
        logger.info(f"Auto-verified {len(converted)} indicators for combine mode")

    # Step 3: Analyze roles
    logger.info("\n[3/6] Analyzing indicator roles...")
    analyze_stats = analyze_all(db=db)

    # Step 4: Generate combinations
    logger.info("\n[4/6] Generating strategy combinations...")
    strategies = generate_combinations(db=db, max_strategies=args.max_strategies)

    if not strategies:
        logger.warning("No strategies generated. Need at least 2 indicators with different roles.")
        return

    # Step 5: Fetch data
    logger.info("\n[5/6] Fetching market data...")
    df = fetch_ohlcv(args.asset, args.tf, start, end)
    if df.empty:
        logger.error("No data fetched.")
        return

    # Step 6: Backtest all strategies
    logger.info(f"\n[6/6] Backtesting {len(strategies)} strategies...")
    results = []
    for i, strategy in enumerate(strategies):
        try:
            df_signals = strategy.generate_signals(df)
            bt_result = run_backtest(
                df_signals,
                initial_capital=args.capital,
                commission_pct=args.commission,
                slippage_pct=args.slippage,
            )

            db.insert_backtest_result({
                "strategy_id": strategy.strategy_id,
                "asset": args.asset,
                "timeframe": args.tf,
                "period_start": start,
                "period_end": end,
                **bt_result.metrics,
            })

            results.append((strategy, bt_result))

            if (i + 1) % 50 == 0:
                logger.info(f"  Progress: {i+1}/{len(strategies)}")

        except Exception as e:
            logger.warning(f"  Failed {strategy.strategy_id}: {e}")

    # Rank by composite score
    results.sort(key=lambda x: x[1].metrics.get("composite_score", 0), reverse=True)

    # Print top results
    logger.info(f"\n{'='*70}")
    logger.info(f"Top 10 Strategies (out of {len(results)} tested)")
    logger.info(f"{'='*70}")
    logger.info(f"{'Rank':<5} {'ID':<15} {'Return%':<10} {'Sharpe':<8} {'MDD%':<8} {'WinRate%':<10} {'Score':<8} Description")
    logger.info("-" * 100)

    for rank, (strategy, bt) in enumerate(results[:10], 1):
        m = bt.metrics
        print(
            f"{rank:<5} {strategy.strategy_id:<15} "
            f"{m['total_return_pct']:>8.2f}% "
            f"{m['sharpe_ratio']:>7.4f} "
            f"{m['max_drawdown_pct']:>7.2f}% "
            f"{m['win_rate_pct']:>8.2f}% "
            f"{m['composite_score']:>7.2f} "
            f"{strategy.description[:40]}"
        )

    logger.info(f"{'='*70}")


# ═══════════════════════════════════════════════════════════
# Mode 3: Verify Conversion
# ═══════════════════════════════════════════════════════════

def cmd_verify(args):
    """Verify a converted indicator's signals visually."""
    from ai.pipeline.verifier import verify_indicator, approve_indicator, reject_indicator

    indicator_id = Path(args.file).stem

    if args.approve:
        approve_indicator(indicator_id)
        return

    if args.reject:
        reject_indicator(indicator_id, reason=args.reason or "")
        return

    stats = verify_indicator(
        indicator_id,
        asset=args.asset,
        timeframe=args.tf,
        recent_bars=args.recent,
    )

    if "error" in stats:
        logger.error(stats["error"])
        return

    logger.info(f"\nVerification complete for {indicator_id}")
    if "chart_path" in stats:
        logger.info(f"Chart: {stats['chart_path']}")
    logger.info(f"Use --approve or --reject to finalize")


# ═══════════════════════════════════════════════════════════
# Individual Stage Commands
# ═══════════════════════════════════════════════════════════

def cmd_convert(args):
    """Convert Pine Script(s) to Python."""
    from ai.pipeline.converter import convert_pine_script, convert_all

    if args.file:
        pine_path = _resolve_pine_path(args.file)
        result = convert_pine_script(pine_path, force=args.force)
        if result:
            logger.info(f"Converted: {result}")
        else:
            logger.error("Conversion failed")
    else:
        stats = convert_all(force=args.force)
        logger.info(f"Batch conversion: {stats}")


def cmd_analyze(args):
    """Analyze and classify all verified indicators."""
    from ai.pipeline.analyzer import analyze_all, get_indicators_by_role

    stats = analyze_all()
    logger.info(f"Analysis: {stats}")

    by_role = get_indicators_by_role()
    for role, indicators in by_role.items():
        if indicators:
            logger.info(f"\n{role}: {len(indicators)} indicators")
            for ind in indicators:
                logger.info(f"  - {ind['id']}: {ind.get('analysis_description', '')[:60]}")


def cmd_status(args):
    """Show pipeline status report."""
    from ai.pipeline.input_manager import scan_pine_directory, get_status_report

    db = PipelineDB()
    scan_pine_directory(db)
    report = get_status_report(db)
    print(report)


# ═══════════════════════════════════════════════════════════
# CLI Setup
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Pine Script Strategy Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m ai.pipeline.main test supertrend.pine --asset BTC/USDT --period 2023-01-01:2024-12-31
  python -m ai.pipeline.main combine --asset BTC/USDT --period 2023-01-01:2024-12-31
  python -m ai.pipeline.main verify supertrend.pine --asset BTC/USDT --recent 100
  python -m ai.pipeline.main convert --force supertrend.pine
  python -m ai.pipeline.main status
        """,
    )
    subparsers = parser.add_subparsers(dest="command")

    # Common args helper
    def add_common_args(p):
        p.add_argument("--asset", default="BTC/USDT", help="Asset symbol (default: BTC/USDT)")
        p.add_argument("--period", default="2023-01-01:2024-12-31", help="Period start:end")
        p.add_argument("--tf", default="1d", help="Timeframe (default: 1d)")
        p.add_argument("--capital", type=float, default=10000, help="Initial capital")
        p.add_argument("--commission", type=float, default=0.05, help="Commission pct")
        p.add_argument("--slippage", type=float, default=0.1, help="Slippage pct")

    # ── test ──
    p_test = subparsers.add_parser("test", help="Test single indicator")
    p_test.add_argument("file", help=".pine filename")
    p_test.add_argument("--force", action="store_true", help="Force reconversion")
    add_common_args(p_test)
    p_test.set_defaults(func=cmd_test)

    # ── combine ──
    p_combine = subparsers.add_parser("combine", help="Combine all indicators and backtest")
    p_combine.add_argument("--force", action="store_true", help="Force reconversion")
    p_combine.add_argument("--max-strategies", type=int, default=1000)
    add_common_args(p_combine)
    p_combine.set_defaults(func=cmd_combine)

    # ── verify ──
    p_verify = subparsers.add_parser("verify", help="Verify converted indicator")
    p_verify.add_argument("file", help=".pine filename")
    p_verify.add_argument("--asset", default="BTC/USDT")
    p_verify.add_argument("--tf", default="1d")
    p_verify.add_argument("--recent", type=int, default=100, help="Recent bars to show")
    p_verify.add_argument("--approve", action="store_true", help="Approve conversion")
    p_verify.add_argument("--reject", action="store_true", help="Reject conversion")
    p_verify.add_argument("--reason", default="", help="Rejection reason")
    p_verify.set_defaults(func=cmd_verify)

    # ── convert ──
    p_convert = subparsers.add_parser("convert", help="Convert Pine Script(s)")
    p_convert.add_argument("file", nargs="?", default=None, help=".pine filename (omit for all)")
    p_convert.add_argument("--force", action="store_true", help="Force reconversion")
    p_convert.set_defaults(func=cmd_convert)

    # ── analyze ──
    p_analyze = subparsers.add_parser("analyze", help="Analyze indicator roles")
    p_analyze.set_defaults(func=cmd_analyze)

    # ── status ──
    p_status = subparsers.add_parser("status", help="Show pipeline status")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
