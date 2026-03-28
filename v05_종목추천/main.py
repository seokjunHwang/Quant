from __future__ import annotations
"""
v05 종목추천 메인 파이프라인.

실행:
  python main.py                     # 기본 (전체 시장)
  python main.py --market kr         # 국장만
  python main.py --market us         # 미장만
  python main.py --from step3        # step3부터 재실행 (캐시 활용)
  python main.py --dry-run           # 데이터 수집만, AI 호출 없음
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# ── 로깅 설정 ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
# 노이즈 억제
for noisy in ["httpx", "httpcore", "yfinance", "urllib3", "requests"]:
    logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

from src.utils.config import DATA_DIR
from src.utils.gemini_client import get_search_usage
from src.utils.claude_cli import get_claude_usage


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _load_cache(today: str, market: str, step: str) -> dict | None:
    path = DATA_DIR / today / market / f"{step}.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_cache(data: dict | list, today: str, market: str, step: str) -> None:
    out_dir = DATA_DIR / today / market
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{step}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"  캐시 저장 → {path}")


def _save_step1_md(data: dict, today: str, market: str) -> None:
    """Step 1 수집 결과를 사람이 읽기 좋은 MD로 저장."""
    out_dir = DATA_DIR / today / market
    path = out_dir / "step1_summary.md"

    lines = [f"# Step 1 수집 결과 — {today} ({market.upper()})", ""]

    # 매크로
    lines += ["## 매크로 지표", ""]
    macro = data.get("macro", {})
    for k, v in macro.items():
        if isinstance(v, dict) and "price" in v:
            chg = v.get("change_pct", 0)
            sign = "+" if chg >= 0 else ""
            lines.append(f"- **{k}**: {v['price']} ({sign}{chg:.1f}%)")
    vix_zone = macro.get("vix_zone", "")
    if vix_zone:
        lines.append(f"- **VIX 상태**: {vix_zone}")

    # 뉴스
    news = data.get("news", {})
    for mkt, ndata in news.items():
        label = "국장 (KR)" if mkt == "kr" else "미장 (US)"
        lines += ["", f"## {label} 뉴스", ""]

        macro_env = ndata.get("macro_environment", {})
        if macro_env.get("summary"):
            lines.append(f"> {macro_env['summary']}")
            lines.append("")

        themes = ndata.get("hot_themes", [])
        if themes:
            lines += ["### 핫 테마", ""]
            for t in themes:
                lines.append(f"- **{t.get('theme','')}** ({t.get('trading_type','')}): {t.get('reason','')}")

        risks = ndata.get("risk_factors", [])
        if risks:
            lines += ["", "### 리스크 요인", ""]
            for r in risks:
                lines.append(f"- [{r.get('severity','').upper()}] {r.get('factor','')}: {r.get('description','')}")

    # 프리마켓
    premarket = data.get("premarket", {})
    movers = premarket.get("premarket_movers", [])
    if movers:
        lines += ["", "## 미장 프리마켓 주요 종목", ""]
        for m in movers[:10]:
            chg = m.get("change_pct", 0)
            sign = "+" if chg >= 0 else ""
            lines.append(f"- **{m.get('ticker','')}** {m.get('name','')}: {sign}{chg}% — {m.get('reason','')}")

    events = premarket.get("economic_events", [])
    if events:
        lines += ["", "## 오늘 경제 이벤트", ""]
        for e in events:
            imp = e.get("importance", "")
            if imp == "high":
                lines.append(f"- 🔴 **{e.get('event','')}** ({e.get('time_et','')}) 예상: {e.get('forecast','')}")
            elif imp == "medium":
                lines.append(f"- 🟡 {e.get('event','')} ({e.get('time_et','')})")

    # DART
    dart = data.get("dart", {})
    rights = dart.get("rights_offerings", [])
    lockup = dart.get("lockup_releases", [])
    if rights or lockup:
        lines += ["", "## DART 리스크 공시", ""]
        if rights:
            lines.append(f"### 유상증자 결정 ({len(rights)}건)")
            for r in rights[:10]:
                lines.append(f"- {r.get('corp_name','')} ({r.get('rcept_dt','')})")
            if len(rights) > 10:
                lines.append(f"- ... 외 {len(rights)-10}건")
        if lockup:
            lines += ["", f"### 보호예수 해제 예정 ({len(lockup)}건)"]
            for l in lockup:
                lines.append(f"- {l.get('corp_name','')} (해제일: {l.get('release_date','')})")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    logger.info(f"  MD 저장 → {path}")


def _save_step2_md(data: dict, today: str, market: str) -> None:
    """Step 2 테마 분석 결과 MD 저장."""
    out_dir = DATA_DIR / today / market
    path = out_dir / "step2_themes.md"

    lines = [f"# Step 2 테마 분석 — {today} ({market.upper()})", ""]
    lines.append(f"> {data.get('market_summary', '')}")
    lines.append(f"> **전략:** {data.get('overall_strategy', '')}")
    lines += [""]

    for t in data.get("themes", []):
        lines += [
            f"## [{t.get('strength','?')}] {t.get('theme_name','')}",
            f"- **유형**: {t.get('trading_type','')} / {t.get('duration','')}",
            f"- **근거**: {t.get('reason','')}",
            f"- **국장 섹터**: {', '.join(t.get('sectors_kr', []))}",
            f"- **미장 섹터**: {', '.join(t.get('sectors_us', []))}",
            f"- **국장 종목 힌트**: {', '.join(t.get('tickers_hint_kr', []))}",
            f"- **미장 종목 힌트**: {', '.join(t.get('tickers_hint_us', []))}",
            f"- **리스크**: {t.get('risk','')}",
            "",
        ]

    avoid = data.get("avoid_sectors", [])
    if avoid:
        lines += ["## 피해야 할 섹터", ""]
        for a in avoid:
            lines.append(f"- **{a.get('sector','')}**: {a.get('reason','')}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    logger.info(f"  MD 저장 → {path}")


def _print_step(n: int, title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  STEP {n}: {title}")
    print(f"{'─'*60}")


# ── 파이프라인 단계 ──────────────────────────────────────────────────────────

def run_step1(market: str, today: str, dry_run: bool) -> dict:
    """Step 1: 데이터 수집 (뉴스 + 매크로 + DART)."""
    _print_step(1, "데이터 수집")

    cache = _load_cache(today, market, "step1")
    if cache:
        print("  [캐시] step1 데이터 로드")
        return cache

    from src.step1_collect.news_gemini import fetch_market_news, fetch_us_premarket
    from src.step1_collect.market_data import fetch_macro
    from src.step1_collect.dart import get_rights_offerings, get_lockup_releases, get_today_disclosures

    result = {}

    # 매크로
    print("  매크로 지표 수집...")
    result["macro"] = fetch_macro()
    vix = result["macro"].get("vix", {}).get("price", 0)
    vix_zone = result["macro"].get("vix_zone", "?")
    print(f"  VIX: {vix} ({vix_zone})")

    if not dry_run:
        # 뉴스 (Gemini Search)
        markets_to_fetch = []
        if market in ("kr", "all"):
            markets_to_fetch.append("kr")
        if market in ("us", "all"):
            markets_to_fetch.append("us")

        result["news"] = {}
        for m in markets_to_fetch:
            print(f"  [{m.upper()}] 뉴스 수집 중...")
            result["news"][m] = fetch_market_news(m)

        if market in ("us", "all"):
            print("  [US] 프리마켓 데이터 수집...")
            result["premarket"] = fetch_us_premarket()

    # DART (국장만)
    if market in ("kr", "all"):
        print("  DART 공시 수집...")
        result["dart"] = {
            "rights_offerings": get_rights_offerings(days_back=30),
            "lockup_releases": get_lockup_releases(days_ahead=30),
            "today_disclosures": get_today_disclosures(),
        }
        print(f"  유상증자: {len(result['dart']['rights_offerings'])}건, "
              f"보호예수: {len(result['dart']['lockup_releases'])}건")

    _save_cache(result, today, market, "step1")
    _save_step1_md(result, today, market)
    return result


def run_step2(step1_data: dict, market: str, today: str, dry_run: bool) -> dict:
    """Step 2: Claude CLI 테마 분석."""
    _print_step(2, "테마 분석 (Claude)")

    cache = _load_cache(today, market, "step2")
    if cache:
        print("  [캐시] step2 데이터 로드")
        return cache

    if dry_run:
        print("  [dry-run] 스킵")
        return {}

    from src.step2_theme.theme_claude import analyze_themes, format_themes_summary

    news_data = step1_data.get("news", {})
    macro_data = step1_data.get("macro", {})

    result = analyze_themes(news_data, macro_data, market)

    if result:
        summary = format_themes_summary(result)
        print(summary)
        themes_count = len(result.get("themes", []))
        print(f"\n  → 테마 {themes_count}개 도출")

    _save_cache(result, today, market, "step2")
    _save_step2_md(result, today, market)
    return result


def run_step3(
    step1_data: dict,
    step2_data: dict,
    market: str,
    today: str,
    dry_run: bool,
) -> dict:
    """Step 3: 종목 리서치 + 필터링."""
    _print_step(3, "종목 리서치 + 필터링")

    cache = _load_cache(today, market, "step3")
    if cache:
        print("  [캐시] step3 데이터 로드")
        return cache

    from src.step3_research.filter import (
        build_candidate_pool, apply_dart_filter,
        score_candidates, save_filter_results,
    )

    # 후보 풀 생성
    candidates = build_candidate_pool(step2_data, market=market)
    print(f"  후보 풀: {len(candidates)}개")

    # DART 필터 (국장)
    rights_list = step1_data.get("dart", {}).get("rights_offerings", [])
    lockup_list = step1_data.get("dart", {}).get("lockup_releases", [])
    passed, dart_excluded = apply_dart_filter(candidates, rights_list, lockup_list)
    if dart_excluded:
        print(f"  DART 제외: {len(dart_excluded)}개")

    # Gemini 리서치
    research_results = []
    if not dry_run and passed:
        from src.step3_research.stock_gemini import research_stocks_batch
        # 국장/미장 분리
        kr_stocks = [s for s in passed if s.get("market") == "kr"]
        us_stocks = [s for s in passed if s.get("market") == "us"]

        if kr_stocks:
            print(f"\n  [KR] {len(kr_stocks)}개 종목 리서치...")
            research_results += research_stocks_batch(kr_stocks, "kr", max_stocks=20)

        if us_stocks:
            print(f"\n  [US] {len(us_stocks)}개 종목 리서치...")
            research_results += research_stocks_batch(us_stocks, "us", max_stocks=20)

    # 재무 데이터 (국장)
    if not dry_run and market in ("kr", "all"):
        kr_passed = [s for s in passed if s.get("market") == "kr"]
        if kr_passed:
            print(f"\n  [KR] 재무 데이터 수집...")
            from src.step3_research.financial import enrich_kr_stocks
            enriched_kr = enrich_kr_stocks(kr_passed, rights_list, lockup_list)
            # passed 업데이트
            kr_tickers = {s.get("ticker") for s in kr_passed}
            passed = [s for s in passed if s.get("ticker") not in kr_tickers] + enriched_kr

    # 점수 계산
    scored = score_candidates(passed, research_results)

    # 결과 저장
    result = {
        "passed": scored,
        "excluded": dart_excluded,
        "research": research_results,
    }

    save_filter_results(scored, dart_excluded, market, step="step3")
    _save_cache(result, today, market, "step3")
    print(f"\n  → 통과: {len(scored)}개, 제외: {len(dart_excluded)}개")
    return result


def run_step4(step3_data: dict, market: str, today: str, dry_run: bool) -> dict:
    """Step 4: 차트 분석 (Claude CLI)."""
    _print_step(4, "차트 분석 (Claude)")

    cache = _load_cache(today, market, "step4")
    if cache:
        print("  [캐시] step4 데이터 로드")
        return cache

    if dry_run:
        print("  [dry-run] 스킵")
        return {}

    from src.step1_collect.market_data import fetch_ohlcv
    from src.step4_chart.chart_claude import analyze_charts_batch

    passed = step3_data.get("passed", [])
    top_stocks = passed[:30]  # 상위 30개만 차트 분석

    # OHLCV 수집
    print(f"  OHLCV 수집 ({len(top_stocks)}개)...")
    ohlcv_map = {}
    for stock in top_stocks:
        ticker = stock.get("ticker", "")
        m = stock.get("market", "us")
        df = fetch_ohlcv(ticker, days=60, market=m)
        if df is not None:
            ohlcv_map[ticker] = df

    print(f"  차트 분석 시작 ({len(ohlcv_map)}개 수집 완료)...")
    chart_results = analyze_charts_batch(top_stocks, ohlcv_map)

    # 차트 결과를 passed에 병합
    chart_map = {r.get("ticker"): r for r in chart_results}
    enriched = []
    for stock in passed:
        ticker = stock.get("ticker", "")
        stock["chart_result"] = chart_map.get(ticker, {"chart_score": 50, "timing": "관망"})
        enriched.append(stock)

    result = {"stocks_with_chart": enriched, "chart_results": chart_results}
    _save_cache(result, today, market, "step4")
    print(f"\n  → 차트 분석 완료: {len(chart_results)}개")
    return result


def run_step5(
    step4_data: dict,
    step2_data: dict,
    step1_data: dict,
    market: str,
    today: str,
    dry_run: bool,
) -> dict:
    """Step 5: 최종 점수 + 리포트 생성."""
    _print_step(5, "최종 순위 + 리포트 (Claude)")

    if dry_run:
        print("  [dry-run] 스킵")
        return {}

    from src.step5_score.scorer import rank_stocks
    from src.step5_score.report_claude import generate_report, save_report

    stocks = step4_data.get("stocks_with_chart", [])
    macro_data = step1_data.get("macro", {})

    # 최종 순위
    ranked = rank_stocks(stocks)

    # 상위 15개 출력
    print(f"\n  {'순위':>4} {'종목':12} {'티커':8} {'점수':>6} {'타이밍':8} {'테마'}")
    print(f"  {'-'*60}")
    for s in ranked[:15]:
        timing = s.get("chart_result", {}).get("timing", "-")
        print(
            f"  {s['rank']:>4}위 {s.get('name','?')[:10]:12} "
            f"{s.get('ticker','?'):8} {s.get('final_score',0):>6.1f} "
            f"{timing:8} {s.get('theme','')[:15]}"
        )

    # Claude 리포트
    print("\n  최종 리포트 생성 중...")
    report = generate_report(step2_data, ranked[:15], macro_data, market)

    # 저장
    md_path = save_report(report, ranked[:15], step2_data, macro_data, market)
    print(f"\n  리포트 저장 → {md_path}")

    return {"ranked": ranked, "report": report}


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="v05 종목 추천 파이프라인")
    parser.add_argument("--market", choices=["kr", "us", "all"], default="all")
    parser.add_argument("--from", dest="from_step", default="step1",
                        choices=["step1", "step2", "step3", "step4", "step5"])
    parser.add_argument("--dry-run", action="store_true",
                        help="데이터 수집만, AI 호출 없음")
    args = parser.parse_args()

    market = args.market
    dry_run = args.dry_run
    today = datetime.now().strftime("%Y%m%d")

    STEPS = ["step1", "step2", "step3", "step4", "step5"]
    start_idx = STEPS.index(args.from_step)

    print(f"\n{'='*60}")
    print(f"  v05 종목 추천 파이프라인")
    print(f"  날짜: {today} | 시장: {market.upper()} | 시작: {args.from_step}")
    print(f"{'='*60}")

    # 데이터 저장소
    data = {}

    # from step2+ 이면 step1 캐시 강제 로드
    if start_idx > 0:
        data["step1"] = _load_cache(today, market, "step1") or {}
    if start_idx > 1:
        data["step2"] = _load_cache(today, market, "step2") or {}
    if start_idx > 2:
        data["step3"] = _load_cache(today, market, "step3") or {}
    if start_idx > 3:
        data["step4"] = _load_cache(today, market, "step4") or {}

    try:
        if start_idx <= 0:
            data["step1"] = run_step1(market, today, dry_run)
        if start_idx <= 1:
            data["step2"] = run_step2(data["step1"], market, today, dry_run)
        if start_idx <= 2:
            data["step3"] = run_step3(data["step1"], data["step2"], market, today, dry_run)
        if start_idx <= 3:
            data["step4"] = run_step4(data["step3"], market, today, dry_run)
        if start_idx <= 4:
            data["step5"] = run_step5(
                data["step4"], data["step2"], data["step1"], market, today, dry_run
            )

    except KeyboardInterrupt:
        print("\n\n  [중단] 사용자 인터럽트")
        sys.exit(0)
    except Exception as e:
        logger.error(f"파이프라인 오류: {e}", exc_info=True)
        sys.exit(1)

    # 사용량 요약
    print(f"\n{'─'*60}")
    search = get_search_usage()
    claude = get_claude_usage()
    print(f"  Gemini 검색: {search.get('this_month_queries', 0)}회 (이번 달)")
    print(f"  Claude 호출: {claude.get('total_calls', 0)}회 | ${claude.get('this_month_cost_usd', 0):.4f}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
