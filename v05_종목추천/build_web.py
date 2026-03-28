#!/usr/bin/env python3
"""
v05 종목추천 → 웹 대시보드 데이터 빌드.

사용법:
  python build_web.py                    # 오늘 날짜
  python build_web.py --date 20260328    # 특정 날짜
  python build_web.py --all              # 전체 날짜

파이프라인 실행 후 이 스크립트를 돌리면 web/data/ 에 JSON 생성.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from src.utils.config import DATA_DIR, now_kst

WEB_DATA_DIR = Path(__file__).parent / "web" / "data"


def load_step_json(date_dir: Path, market: str, step_dir: str, filename: str) -> dict | list | None:
    path = date_dir / market / step_dir / filename
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    # 하위 호환: step 디렉토리 없이 바로 있는 경우
    path_flat = date_dir / market / filename
    if path_flat.exists():
        with open(path_flat, encoding="utf-8") as f:
            return json.load(f)
    return None


def find_latest_report(date_dir: Path, market: str) -> dict | None:
    """step5_리포트 디렉토리에서 최신 final_report JSON 찾기."""
    report_dir = date_dir / market / "step5_리포트"
    if not report_dir.exists():
        report_dir = date_dir / market  # 하위 호환

    reports = sorted(report_dir.glob("final_report_*.json"), reverse=True)
    if reports:
        with open(reports[0], encoding="utf-8") as f:
            return json.load(f)
    return None


def build_web_data(date_str: str, market: str = "all") -> dict | None:
    """특정 날짜의 리포트 데이터를 웹 JSON 형식으로 변환."""
    date_dir = DATA_DIR / date_str
    if not date_dir.exists():
        return None

    # 각 step 데이터 로드 (자정 넘김 대응: 인접 날짜에서도 탐색)
    def load_with_fallback(step_dir, filename):
        # 현재 날짜 먼저
        result = load_step_json(date_dir, market, step_dir, filename)
        if result:
            return result
        # 인접 날짜 탐색 (전날/다음날)
        for offset in [-1, 1]:
            from datetime import datetime, timedelta
            try:
                dt = datetime.strptime(date_str, "%Y%m%d") + timedelta(days=offset)
                adj_dir = DATA_DIR / dt.strftime("%Y%m%d")
                result = load_step_json(adj_dir, market, step_dir, filename)
                if result:
                    return result
            except Exception:
                pass
        return None

    step1 = load_with_fallback("step1_데이터수집", "step1.json") or {}
    step2 = load_with_fallback("step2_테마분석", "step2.json") or {}
    step3 = load_with_fallback("step3_종목필터링", "step3.json") or {}

    # 리포트도 인접 날짜 탐색
    report_full = find_latest_report(date_dir, market)
    if not report_full:
        for offset in [-1, 1]:
            from datetime import datetime, timedelta
            try:
                dt = datetime.strptime(date_str, "%Y%m%d") + timedelta(days=offset)
                adj_dir = DATA_DIR / dt.strftime("%Y%m%d")
                report_full = find_latest_report(adj_dir, market)
                if report_full:
                    break
            except Exception:
                pass

    if not report_full:
        return None

    report = report_full.get("report", {})
    ranked = report_full.get("ranked_stocks", [])
    macro_snapshot = report_full.get("macro_snapshot", {})

    # 매크로 데이터 정리
    macro = {}
    raw_macro = step1.get("macro", macro_snapshot)
    for key, val in raw_macro.items():
        if isinstance(val, dict) and "price" in val:
            macro[key] = {
                "price": val.get("price"),
                "change_pct": val.get("change_pct", 0),
                "prev_close": val.get("prev_close"),
            }
    macro["vix_zone"] = raw_macro.get("vix_zone", "")

    # 테마 정리
    themes = []
    for t in step2.get("themes", []):
        themes.append({
            "name": t.get("theme_name", ""),
            "strength": t.get("strength", "중"),
            "trading_type": t.get("trading_type", ""),
            "duration": t.get("duration", ""),
            "reason": t.get("reason", ""),
            "risk": t.get("risk", ""),
            "sectors_kr": t.get("sectors_kr", []),
            "sectors_us": t.get("sectors_us", []),
        })

    # 추천 종목 정리 — ranked_stocks 전체를 기반으로, Claude 리포트 상세는 병합
    report_recs = {r.get("ticker", ""): r for r in report.get("recommendations", [])}

    recommendations = []
    for stock in ranked:
        ticker = stock.get("ticker", "")
        score_detail = stock.get("score_detail", {})
        # Claude 리포트에 상세 설명이 있으면 병합
        rec_detail = report_recs.get(ticker, {})

        # 차트 지표 (과열 표시용)
        chart_result = stock.get("chart_result", {})
        raw_ind = chart_result.get("raw_indicators", {})
        research = stock.get("research", {})

        recommendations.append({
            "rank": stock.get("rank", 0),
            "ticker": ticker,
            "name": stock.get("name", rec_detail.get("name", "")),
            "market": stock.get("market", "us"),
            "theme": stock.get("theme", rec_detail.get("theme", "")),
            "final_score": stock.get("final_score", 0),
            "trading_type": rec_detail.get("trading_type", stock.get("theme_strength", "")),
            "timing": chart_result.get("timing", "-"),
            "why": rec_detail.get("why", research.get("news_summary", "")),
            "entry": rec_detail.get("entry", chart_result.get("entry_condition", "")),
            "stop_loss": rec_detail.get("stop_loss", chart_result.get("stop_loss", "")),
            "target": rec_detail.get("target", chart_result.get("target_price", "")),
            "risk": rec_detail.get("risk", ""),
            "upcoming_events": rec_detail.get("upcoming_events", ""),
            "analyst_view": research.get("analyst_view", ""),
            "heat": {
                "rsi": raw_ind.get("rsi", 50),
                "rsi_signal": raw_ind.get("rsi_signal", "중립"),
                "bb_pct": raw_ind.get("bb_pct", 0.5),
                "trend": raw_ind.get("trend", "sideways"),
                "volume_ratio": raw_ind.get("volume_ratio", 1.0),
                "price_change_5d": raw_ind.get("price_change_5d", 0),
                "price_change_20d": raw_ind.get("price_change_20d", 0),
            },
            "score_detail": {
                "theme": score_detail.get("theme", 0),
                "chart": score_detail.get("chart", 0),
                "supply_demand": score_detail.get("supply_demand", 0),
                "financial": score_detail.get("financial", 0),
                "dart_penalty": score_detail.get("dart_penalty", 0),
            },
        })

    # DART 제외 종목
    excluded = step3.get("excluded", [])
    excluded_summary = [
        {"name": s.get("name", ""), "ticker": s.get("ticker", ""), "reason": s.get("exclude_reason", "")}
        for s in excluded[:10]
    ]

    # 시장별 뉴스 상세
    news = step1.get("news", {})
    market_news = {}
    for mkt_key in ["kr", "us"]:
        n = news.get(mkt_key, {})
        if n:
            market_news[mkt_key] = {
                "summary": n.get("macro_environment", {}).get("summary", ""),
                "hot_themes": n.get("hot_themes", []),
                "sector_news": n.get("sector_news", []),
                "risk_factors": n.get("risk_factors", []),
            }
    premarket = step1.get("premarket", {})

    return {
        "date": date_str,
        "generated_at": report_full.get("generated_at", ""),
        "market_summary": step2.get("market_summary", report.get("executive_summary", "")),
        "strategy": step2.get("overall_strategy", report.get("one_line_strategy", "")),
        "market_view": report.get("market_view", ""),
        "top_theme": report.get("top_theme", ""),
        "macro": macro,
        "themes": themes,
        "news": market_news,
        "premarket": {
            "movers": premarket.get("premarket_movers", [])[:10],
            "events": premarket.get("economic_events", []),
            "fed_watch": premarket.get("fed_watch", {}),
        },
        "recommendations": recommendations,
        "avoid": report.get("avoid_stocks", []),
        "excluded": excluded_summary,
        "counts": {
            "kr": sum(1 for r in recommendations if r.get("market") == "kr"),
            "us": sum(1 for r in recommendations if r.get("market") != "kr"),
            "total": len(recommendations),
        },
    }


def build_dates_index() -> dict:
    """사용 가능한 날짜 목록 생성."""
    dates = []
    if DATA_DIR.exists():
        for d in sorted(DATA_DIR.iterdir(), reverse=True):
            if d.is_dir() and d.name.isdigit() and len(d.name) == 8:
                dates.append(d.name)
    return {
        "dates": dates,
        "latest": dates[0] if dates else "",
    }


def save_web_json(data: dict, filename: str) -> None:
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = WEB_DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  저장 → {path}")


def main():
    parser = argparse.ArgumentParser(description="웹 대시보드 데이터 빌드")
    parser.add_argument("--date", help="특정 날짜 (YYYYMMDD)")
    parser.add_argument("--all", action="store_true", help="전체 날짜")
    args = parser.parse_args()

    print("=" * 50)
    print("  v05 웹 대시보드 빌드")
    print("=" * 50)

    if args.all:
        # 전체 날짜
        idx = build_dates_index()
        dates = idx["dates"]
    elif args.date:
        dates = [args.date]
    else:
        dates = [now_kst().strftime("%Y%m%d")]

    for date_str in dates:
        print(f"\n  [{date_str}] 빌드 중...")
        data = build_web_data(date_str)
        if data:
            save_web_json(data, f"{date_str}.json")
        else:
            print(f"  [{date_str}] 데이터 없음 — 스킵")

    # dates index 업데이트
    idx = build_dates_index()
    # 웹 데이터가 있는 날짜만 필터
    web_dates = [d for d in idx["dates"] if (WEB_DATA_DIR / f"{d}.json").exists()]
    idx["dates"] = web_dates
    idx["latest"] = web_dates[0] if web_dates else ""
    save_web_json(idx, "dates.json")

    print(f"\n  완료: {len(web_dates)}개 날짜")
    print("=" * 50)


if __name__ == "__main__":
    main()
