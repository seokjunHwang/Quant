"""
v05 파이프라인이 생성한 일자별 JSON을 읽어 v07 페이지에 필요한 형태로 정규화.

v05 디렉토리 구조:
  data/{YYYYMMDD}/all/
    step0_글로벌이벤트/step0.json
    step1_데이터수집/step1.json
    step2_테마분석/step2.json

v07은 데이터 생성을 하지 않음 (읽기 전용).
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

V05_DATA_DIR = Path("/workspace/Quant/v05_종목추천/data/daily")

# ── 날짜 디렉토리 헬퍼 ────────────────────────────────────────


_DATE_RE = re.compile(r"^\d{8}$")


def list_available_dates() -> list[str]:
    """v05 데이터가 있는 날짜 리스트 (최신순). step1.json이 있는 날짜만."""
    if not V05_DATA_DIR.exists():
        return []
    out = []
    for p in V05_DATA_DIR.iterdir():
        if not p.is_dir() or not _DATE_RE.match(p.name):
            continue
        if (p / "all" / "step1_데이터수집" / "step1.json").exists():
            out.append(p.name)
    return sorted(out, reverse=True)


def latest_date() -> str | None:
    dates = list_available_dates()
    return dates[0] if dates else None


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ── step0 / step1 / step2 raw 로드 ───────────────────────────


def load_raw(date: str) -> dict[str, Any]:
    base = V05_DATA_DIR / date / "all"
    return {
        "date": date,
        "step0": _read_json(base / "step0_글로벌이벤트" / "step0.json") or {},
        "step1": _read_json(base / "step1_데이터수집" / "step1.json") or {},
        "step2": _read_json(base / "step2_테마분석" / "step2.json") or {},
    }


# ── 날짜 포맷 ────────────────────────────────────────────────


def format_date_kr(date: str) -> str:
    """20260408 → 2026년 4월 8일 (수)"""
    try:
        dt = datetime.strptime(date, "%Y%m%d")
        weekday = "월화수목금토일"[dt.weekday()]
        return f"{dt.year}년 {dt.month}월 {dt.day}일 ({weekday})"
    except Exception:
        return date


# ── 매크로 정규화 ────────────────────────────────────────────

MACRO_LABELS = {
    "vix":          ("VIX 변동성지수", ""),
    "sp500":        ("S&P 500", ""),
    "nasdaq":       ("나스닥", ""),
    "us10y_yield":  ("미국 10년물 국채금리", "%"),
    "us2y_yield":   ("미국 2년물 국채금리", "%"),
    "dollar_index": ("달러인덱스 (DXY)", ""),
    "gold":         ("금 (Gold)", "$"),
    "oil_wti":      ("WTI 원유", "$"),
    "bitcoin":      ("비트코인", "$"),
    "kospi":        ("코스피", ""),
    "kosdaq":       ("코스닥", ""),
    "usdkrw":       ("원/달러 환율", "원"),
}


def normalize_macro(step1: dict) -> dict:
    macro = step1.get("macro") or {}
    items = []
    for key, (label, unit) in MACRO_LABELS.items():
        v = macro.get(key)
        if not isinstance(v, dict):
            continue
        price = v.get("price")
        chg = v.get("change_pct")
        if price is None:
            continue
        items.append({
            "key": key,
            "label": label,
            "unit": unit,
            "price": price,
            "change_pct": chg,
            "direction": "up" if (chg or 0) > 0 else ("down" if (chg or 0) < 0 else "flat"),
        })
    return {
        "items": items,
        "vix_zone": macro.get("vix_zone", ""),
    }


# ── 뉴스(시황 요약) 정규화 ───────────────────────────────────


def _safe_get(d: Any, *keys, default=None):
    cur = d
    for k in keys:
        if isinstance(cur, dict):
            cur = cur.get(k)
        else:
            return default
    return cur if cur is not None else default


def normalize_news(step1: dict) -> dict:
    """v05 step1.news는 {kr:..., us:...} 형태. Gemini가 dict 또는 list로 반환."""
    news = step1.get("news") or {}
    out: dict[str, dict] = {}
    for mkt in ("us", "kr"):
        nd = news.get(mkt)
        if isinstance(nd, list):
            nd = nd[0] if nd else {}
        if not isinstance(nd, dict):
            nd = {}
        out[mkt] = {
            "summary": _safe_get(nd, "macro_environment", "summary", default="") or "",
            "key_indicators": _safe_get(nd, "macro_environment", "key_indicators", default=[]) or [],
            "hot_themes": nd.get("hot_themes") or [],
        }
    return out


# ── 글로벌 이벤트 정규화 ─────────────────────────────────────


def normalize_events(step0: dict) -> dict:
    events = _safe_get(step0, "events_raw", "events", default=[]) or []
    cal = _safe_get(step0, "calendar_raw", "calendar", default=[]) or []
    sector_summary = _safe_get(step0, "impact", "sector_summary", default=[]) or []

    SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    events_sorted = sorted(
        events,
        key=lambda e: SEVERITY_ORDER.get(e.get("severity", "low"), 9),
    )

    return {
        "events": events_sorted,
        "calendar": cal,
        "sector_summary": sector_summary,
    }


# ── 테마 정규화 + slug ───────────────────────────────────────


def slugify(name: str) -> str:
    """한글 테마명을 URL slug으로. 한글은 그대로 두되 공백/특수문자만 정리."""
    s = re.sub(r"\s+", "-", name.strip())
    s = re.sub(r"[/\\?#&%]+", "-", s)
    return s.strip("-") or "theme"


_TICKER_RE = re.compile(r"^(.+?)\s*\(([^)]+)\)\s*$")


def _parse_ticker_hint(hint: str) -> dict:
    """'현대건설(000720)' → {name, ticker}"""
    m = _TICKER_RE.match(hint or "")
    if m:
        return {"name": m.group(1).strip(), "ticker": m.group(2).strip()}
    return {"name": hint, "ticker": ""}


def normalize_themes(step2: dict) -> dict:
    themes_raw = step2.get("themes") or []
    themes = []
    for t in themes_raw:
        name = t.get("theme_name") or t.get("name") or ""
        if not name:
            continue
        kr_stocks = [_parse_ticker_hint(h) for h in (t.get("tickers_hint_kr") or [])]
        us_stocks = [_parse_ticker_hint(h) for h in (t.get("tickers_hint_us") or [])]
        # 종목명 가나다순 (객관적 정렬)
        kr_stocks.sort(key=lambda x: x["name"])
        us_stocks.sort(key=lambda x: x["name"])
        themes.append({
            "name": name,
            "slug": slugify(name),
            "trading_type": t.get("trading_type", ""),
            "strength": t.get("strength", ""),
            "duration": t.get("duration", ""),
            "reason": t.get("reason", ""),
            "risk": t.get("risk", ""),
            "sectors_kr": t.get("sectors_kr") or [],
            "sectors_us": t.get("sectors_us") or [],
            "stocks_kr": kr_stocks,
            "stocks_us": us_stocks,
            "stock_count": len(kr_stocks) + len(us_stocks),
        })

    return {
        "market_summary": step2.get("market_summary", ""),
        "overall_strategy": step2.get("overall_strategy", ""),
        "themes": themes,
        "avoid_sectors": step2.get("avoid_sectors") or [],
    }


# ── 한 날짜에 대한 통합 뷰 ────────────────────────────────────


def load_day(date: str) -> dict:
    raw = load_raw(date)
    return {
        "date": date,
        "date_label": format_date_kr(date),
        "macro": normalize_macro(raw["step1"]),
        "news": normalize_news(raw["step1"]),
        "events": normalize_events(raw["step0"]),
        "themes": normalize_themes(raw["step2"]),
    }


# ── 테마 slug → 테마 객체 lookup ──────────────────────────────


def find_theme(date: str, slug: str) -> dict | None:
    day = load_day(date)
    for t in day["themes"]["themes"]:
        if t["slug"] == slug:
            return t
    return None
