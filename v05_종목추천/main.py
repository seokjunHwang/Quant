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
from pathlib import Path

# ── 로깅 설정 ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
# 노이즈 억제
for noisy in ["httpx", "httpcore", "yfinance", "urllib3", "requests", "pykrx"]:
    logging.getLogger(noisy).setLevel(logging.WARNING)

# pykrx의 버그: util.py에서 logging.info(args, kwargs)를 호출해 root 로거에
# 잘못된 포맷으로 기록 → logging 내부에서 TypeError 발생 → stderr에 긴
# "--- Logging error ---" 트레이스백. 기능상 무해하므로 완전히 차단.
logging.raiseExceptions = False


class _DropRootNoise(logging.Filter):
    """pykrx가 root 로거로 직접 찍는 INFO 노이즈를 드롭."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not (record.name == "root" and record.levelno <= logging.INFO)


for _h in logging.getLogger().handlers:
    _h.addFilter(_DropRootNoise())

logger = logging.getLogger(__name__)

from src.utils.config import (
    DATA_DIR, DAILY_DIR, now_kst,
    MAX_REPORT_KR, MAX_REPORT_US, MAX_CHART,
    MAX_RESEARCH_KR, MAX_RESEARCH_US,
)
from src.utils.gemini_client import get_search_usage
from src.utils.claude_cli import get_claude_usage


# ── 스텝 디렉토리 매핑 ────────────────────────────────────────────────────────

STEP_DIRS = {
    "step0": "step0_글로벌이벤트",
    "step1": "step1_데이터수집",
    "step2": "step2_테마분석",
    "step3": "step3_종목필터링",
    "step4": "step4_차트분석",
    "step5": "step5_리포트",
}


def _step_dir(today: str, market: str, step: str) -> Path:
    """step별 저장 디렉토리 반환 + 생성."""
    d = DAILY_DIR / today / market / STEP_DIRS.get(step, step)
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _load_cache(today: str, market: str, step: str) -> dict | None:
    path = _step_dir(today, market, step) / f"{step}.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_cache(data: dict | list, today: str, market: str, step: str) -> None:
    out_dir = _step_dir(today, market, step)
    path = out_dir / f"{step}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"  캐시 저장 → {path}")


def _save_step1_md(data: dict, today: str, market: str) -> None:
    """Step 1 수집 결과를 사람이 읽기 좋은 MD로 저장."""
    out_dir = _step_dir(today, market, "step1")
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
        # Gemini가 [{...}] 리스트로 반환하는 경우 방어
        if isinstance(ndata, list):
            ndata = ndata[0] if ndata else {}
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
    if isinstance(premarket, list):
        premarket = premarket[0] if premarket else {}
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

    # DART (오늘 공시만 — 리스크 체크는 Step 3에서 후보 종목별 수행)
    dart = data.get("dart", {})
    today_disc = dart.get("today_disclosures", [])
    if today_disc:
        lines += ["", f"## DART 오늘 공시 ({len(today_disc)}건)", ""]
        for d in today_disc[:15]:
            lines.append(f"- {d.get('corp_name','')} — {d.get('report_nm','')}")
        if len(today_disc) > 15:
            lines.append(f"- ... 외 {len(today_disc)-15}건")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    logger.info(f"  MD 저장 → {path}")


def _save_step2_md(data: dict, today: str, market: str) -> None:
    """Step 2 테마 분석 결과 MD 저장."""
    out_dir = _step_dir(today, market, "step2")
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

def run_step0(market: str, today: str, dry_run: bool) -> dict:
    """Step 0: 글로벌 이벤트 수집 + 경제 캘린더."""
    _print_step(0, "글로벌 이벤트 수집")

    cache = _load_cache(today, market, "step0")
    if cache:
        print("  [캐시] step0 데이터 로드")
        return cache

    if dry_run:
        print("  [dry-run] 스킵")
        return {}

    from src.step0_globe.events_gemini import fetch_global_events, fetch_economic_calendar

    print("  글로벌 이벤트 검색...")
    events = fetch_global_events()
    print(f"  → 이벤트 {len(events.get('events', []))}건")

    print("  경제 캘린더 검색...")
    calendar = fetch_economic_calendar()
    print(f"  → 캘린더 {len(calendar.get('calendar', []))}건")

    result = {
        "events_raw": events,
        "calendar_raw": calendar,
    }

    _save_cache(result, today, market, "step0")
    return result


def run_step1(market: str, today: str, dry_run: bool) -> dict:
    """Step 1: 데이터 수집 (뉴스 + 매크로 + DART)."""
    _print_step(1, "데이터 수집")

    cache = _load_cache(today, market, "step1")
    if cache:
        print("  [캐시] step1 데이터 로드")
        return cache

    from src.step1_collect.news_gemini import fetch_market_news, fetch_us_premarket
    from src.step1_collect.market_data import fetch_macro
    from src.step1_collect.dart import get_today_disclosures

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

    # DART 오늘 공시 (참고용)
    if market in ("kr", "all"):
        print("  DART 오늘 공시 수집...")
        result["dart"] = {
            "today_disclosures": get_today_disclosures(),
        }

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

    # DART 필터 (국장 후보 종목만 개별 체크)
    passed, dart_excluded = apply_dart_filter(candidates)
    if dart_excluded:
        print(f"  DART 제외: {len(dart_excluded)}개")

    # Gemini 리서치
    research_results = []
    if not dry_run and passed:
        from src.step3_research.stock_gemini_cli import research_stocks_batch
        # 국장/미장 분리
        kr_stocks = [s for s in passed if s.get("market") == "kr"]
        us_stocks = [s for s in passed if s.get("market") == "us"]

        if kr_stocks:
            print(f"\n  [KR] {len(kr_stocks)}개 종목 리서치 (최대 {MAX_RESEARCH_KR}개)...")
            research_results += research_stocks_batch(kr_stocks, "kr", max_stocks=MAX_RESEARCH_KR)

        if us_stocks:
            print(f"\n  [US] {len(us_stocks)}개 종목 리서치 (최대 {MAX_RESEARCH_US}개)...")
            research_results += research_stocks_batch(us_stocks, "us", max_stocks=MAX_RESEARCH_US)

    # 재무 데이터 (국장)
    if not dry_run and market in ("kr", "all"):
        kr_passed = [s for s in passed if s.get("market") == "kr"]
        if kr_passed:
            print(f"\n  [KR] 재무 데이터 수집...")
            from src.step3_research.financial import enrich_kr_stocks
            enriched_kr = enrich_kr_stocks(kr_passed)
            # passed 업데이트
            kr_tickers = {s.get("ticker") for s in kr_passed}
            passed = [s for s in passed if s.get("ticker") not in kr_tickers] + enriched_kr

    # 시총 수집 + 상폐/유효하지 않은 종목 제거
    if not dry_run:
        from src.step1_collect.market_data import fetch_stock_info
        print(f"\n  시총 데이터 수집...")
        delisted = []
        for stock in passed:
            ticker = stock.get("ticker", "")
            mkt = stock.get("market", "us")
            if not stock.get("market_cap"):
                info = fetch_stock_info(ticker, market=mkt)
                stock["market_cap"] = info.get("market_cap", 0)
                # US 종목 시총 0 = 상폐/유효하지 않은 티커
                if mkt == "us" and not stock["market_cap"]:
                    delisted.append(ticker)

        if delisted:
            print(f"  상폐/무효 종목 제외: {', '.join(delisted)}")
            passed = [s for s in passed if s.get("ticker") not in delisted]

    # 점수 계산
    scored = score_candidates(passed, research_results)

    # 결과 저장
    result = {
        "passed": scored,
        "excluded": dart_excluded,
        "research": research_results,
    }

    save_filter_results(scored, dart_excluded, market, step="step3", today=today)
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
    top_stocks = passed[:MAX_CHART]  # 상위 N개만 차트 분석

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

    # 국장/미장 분리 후 시장별 상위 N개 선정
    ranked_kr = [s for s in ranked if s.get("market") == "kr"][:MAX_REPORT_KR]
    ranked_us = [s for s in ranked if s.get("market") != "kr"][:MAX_REPORT_US]
    top_ranked = sorted(ranked_kr + ranked_us, key=lambda x: x.get("final_score", 0), reverse=True)

    # 순위 재부여
    for i, s in enumerate(top_ranked):
        s["rank"] = i + 1

    # 출력
    print(f"\n  {'순위':>4} {'종목':12} {'티커':8} {'점수':>6} {'타이밍':8} {'테마'}")
    print(f"  {'-'*70}")
    for s in top_ranked:
        timing = s.get("chart_result", {}).get("timing", "-")
        mkt = "KR" if s.get("market") == "kr" else "US"
        print(
            f"  {s['rank']:>4}위 [{mkt}] {s.get('name','?')[:10]:12} "
            f"{s.get('ticker','?'):8} {s.get('final_score',0):>6.1f} "
            f"{timing:8} {s.get('theme','')[:15]}"
        )

    print(f"\n  → 국장 {len(ranked_kr)}개 + 미장 {len(ranked_us)}개 = {len(top_ranked)}개")

    # Claude 리포트
    print("\n  최종 리포트 생성 중...")
    report = generate_report(step2_data, top_ranked, macro_data, market)

    # 저장
    md_path = save_report(report, top_ranked, step2_data, macro_data, market)
    print(f"\n  리포트 저장 → {md_path}")

    return {"ranked": ranked, "report": report}


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="v05 종목 추천 파이프라인")
    parser.add_argument("--market", choices=["kr", "us", "all"], default="all")
    parser.add_argument("--from", dest="from_step", default="step0",
                        choices=["step0", "step1", "step2", "step3", "step4", "step5"])
    parser.add_argument("--dry-run", action="store_true",
                        help="데이터 수집만, AI 호출 없음")
    args = parser.parse_args()

    market = args.market
    dry_run = args.dry_run
    today = now_kst().strftime("%Y%m%d")

    STEPS = ["step0", "step1", "step2", "step3", "step4", "step5"]
    start_idx = STEPS.index(args.from_step)

    print(f"\n{'='*60}")
    print(f"  v05 종목 추천 파이프라인")
    print(f"  날짜: {today} | 시장: {market.upper()} | 시작: {args.from_step}")
    print(f"{'='*60}")

    # 데이터 저장소
    data = {}

    # 캐시 강제 로드
    if start_idx > 0:
        data["step0"] = _load_cache(today, market, "step0") or {}
    if start_idx > 1:
        data["step1"] = _load_cache(today, market, "step1") or {}
    if start_idx > 2:
        data["step2"] = _load_cache(today, market, "step2") or {}
    if start_idx > 3:
        data["step3"] = _load_cache(today, market, "step3") or {}
    if start_idx > 4:
        data["step4"] = _load_cache(today, market, "step4") or {}

    try:
        if start_idx <= 0:
            data["step0"] = run_step0(market, today, dry_run)
        if start_idx <= 1:
            data["step1"] = run_step1(market, today, dry_run)
        if start_idx <= 2:
            data["step2"] = run_step2(data["step1"], market, today, dry_run)

        # Step 0 impact analysis (Step 0 + Step 2 완료 후)
        if not dry_run and data.get("step0") and data.get("step2"):
            try:
                _print_step(0, "이벤트 영향 분석 (Claude)")
                from src.step0_globe.impact_claude import analyze_events_impact
                step0 = data["step0"]
                impact = analyze_events_impact(
                    step0.get("events_raw", {}),
                    step0.get("calendar_raw", {}),
                    data.get("step2"),
                )
                data["step0"]["impact"] = impact
                _save_cache(data["step0"], today, market, "step0")
                ev_count = len(impact.get("events", []))
                up_count = len(impact.get("upcoming", []))
                print(f"  → 이벤트 {ev_count}건, 예정 {up_count}건 분석 완료")
            except Exception as e:
                logger.warning(f"이벤트 영향 분석 스킵: {e}")

        if start_idx <= 3:
            data["step3"] = run_step3(data["step1"], data["step2"], market, today, dry_run)
        if start_idx <= 4:
            data["step4"] = run_step4(data["step3"], market, today, dry_run)
        if start_idx <= 5:
            data["step5"] = run_step5(
                data["step4"], data["step2"], data["step1"], market, today, dry_run
            )

    except KeyboardInterrupt:
        print("\n\n  [중단] 사용자 인터럽트")
        sys.exit(0)
    except Exception as e:
        logger.error(f"파이프라인 오류: {e}", exc_info=True)
        sys.exit(1)

    # 웹 대시보드 데이터 빌드
    try:
        from build_web import build_web_data, save_web_json, build_dates_index, WEB_DATA_DIR
        print(f"\n{'─'*60}")
        print("  웹 대시보드 데이터 빌드...")
        web_data = build_web_data(today)
        if web_data:
            save_web_json(web_data, f"{today}.json")
            idx = build_dates_index()
            web_dates = [d for d in idx["dates"] if (WEB_DATA_DIR / f"{d}.json").exists()]
            idx["dates"] = web_dates
            idx["latest"] = web_dates[0] if web_dates else ""
            save_web_json(idx, "dates.json")
            print("  웹 데이터 빌드 완료")
            # 글로벌 이벤트 데이터 빌드
            step0 = data.get("step0", {})
            impact = step0.get("impact", {})
            if impact:
                save_web_json(impact, f"events_{today}.json")
                print("  이벤트 데이터 빌드 완료")
    except Exception as e:
        logger.warning(f"웹 빌드 스킵: {e}")

    # 사용량 요약
    print(f"\n{'─'*60}")
    search = get_search_usage()
    claude = get_claude_usage()
    print(f"  Gemini 검색: {search.get('this_month', 0)}회 (이번 달)")
    print(f"  Claude 호출: {claude.get('total_calls', 0)}회 (Max 구독 — 추가 과금 없음)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
