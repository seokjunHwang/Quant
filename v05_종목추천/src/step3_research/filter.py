from __future__ import annotations
"""
Step 3-3: 후보 종목 1차 필터링.
- DART 리스크 제외 (유상증자, 보호예수)
- 시총/거래량 기본 필터
- 테마 관련성 점수 계산
- 제외 이유 기록
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from src.utils.config import DATA_DIR, FILTERING, LARGE_CAP_COUNT, SMALL_MID_CAP_COUNT

logger = logging.getLogger(__name__)


def build_candidate_pool(
    themes_data: dict,
    universe_kr: list[dict] | None = None,
    universe_us: list[dict] | None = None,
    market: str = "all",
) -> list[dict]:
    """
    테마 분석 결과에서 후보 종목 풀 생성.

    themes_data의 tickers_hint_kr/us → 후보 종목 리스트 생성.
    universe에서 섹터별 추가 후보 병합.

    Returns:
        [{"ticker": ..., "name": ..., "theme": ..., "market": ..., "source": "hint/universe"}, ...]
    """
    candidates = []
    seen = set()

    for theme in themes_data.get("themes", []):
        theme_name = theme.get("theme_name", "")
        strength = theme.get("strength", "중")

        if market in ("kr", "all"):
            for ticker_hint in theme.get("tickers_hint_kr", []):
                # "삼성전자(005930)" 또는 "삼성전자" 형태 파싱
                name, ticker = _parse_ticker_hint(ticker_hint, "kr")
                key = f"kr_{ticker or name}"
                if key not in seen:
                    seen.add(key)
                    candidates.append({
                        "ticker": ticker or "",
                        "name": name,
                        "theme": theme_name,
                        "theme_strength": strength,
                        "market": "kr",
                        "source": "theme_hint",
                    })

        if market in ("us", "all"):
            for ticker_hint in theme.get("tickers_hint_us", []):
                name, ticker = _parse_ticker_hint(ticker_hint, "us")
                key = f"us_{ticker or name}"
                if key not in seen:
                    seen.add(key)
                    candidates.append({
                        "ticker": ticker or name,
                        "name": name,
                        "theme": theme_name,
                        "theme_strength": strength,
                        "market": "us",
                        "source": "theme_hint",
                    })

    logger.info(f"Candidate pool: {len(candidates)} stocks from themes")
    return candidates


def _parse_ticker_hint(hint: str, market: str) -> tuple[str, str]:
    """
    "삼성전자(005930)" → ("삼성전자", "005930")
    "NVDA" → ("NVDA", "NVDA")
    "엔비디아(NVDA)" → ("엔비디아", "NVDA")
    """
    hint = hint.strip()
    if "(" in hint and ")" in hint:
        name = hint[:hint.index("(")].strip()
        ticker = hint[hint.index("(")+1:hint.index(")")].strip()
    else:
        name = hint
        ticker = hint if market == "us" else ""
    return name, ticker


def apply_dart_filter(
    candidates: list[dict],
    rights_list: list[dict],
    lockup_list: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    DART 리스크 기반 필터.

    Returns:
        (passed, excluded)
        excluded items have "exclude_reason" field
    """
    from src.step1_collect.dart import check_risk

    passed = []
    excluded = []

    rights_names = {r["corp_name"] for r in rights_list}
    lockup_names = {l["corp_name"] for l in lockup_list}

    for stock in candidates:
        if stock.get("market") != "kr":
            passed.append(stock)
            continue

        name = stock.get("name", "")
        corp_name = name.split("(")[0].strip()

        reasons = []
        if corp_name in rights_names:
            reasons.append("유상증자 결정 (30일 이내)")
        if corp_name in lockup_names:
            reasons.append("보호예수 해제 예정 (30일 이내)")

        if reasons:
            excluded.append({**stock, "exclude_reason": ", ".join(reasons)})
        else:
            passed.append(stock)

    logger.info(f"DART filter: {len(passed)} passed, {len(excluded)} excluded")
    return passed, excluded


def score_candidates(
    candidates: list[dict],
    research_results: list[dict],
) -> list[dict]:
    """
    후보 종목 점수 계산.
    research_results의 score_hint + 테마 강도 → 종합 점수.
    """
    research_map = {r.get("ticker", ""): r for r in research_results}

    strength_bonus = {"강": 20, "중": 10, "약": 0}

    scored = []
    for stock in candidates:
        ticker = stock.get("ticker", "")
        research = research_map.get(ticker, {})

        score_hint = research.get("score_hint", 50)
        theme_strength = stock.get("theme_strength", "중")
        bonus = strength_bonus.get(theme_strength, 10)

        momentum = research.get("momentum", "neutral")
        momentum_bonus = 10 if momentum == "bullish" else (-10 if momentum == "bearish" else 0)

        # DART 리스크 패널티
        dart_risk = stock.get("dart_risk", {})
        dart_penalty = dart_risk.get("risk_score", 0)

        # 재무 점수 (국장만)
        financial_score = stock.get("financial_score", 50)
        financial_bonus = (financial_score - 50) * 0.2  # 재무 영향 20%

        total_score = score_hint + bonus + momentum_bonus + dart_penalty + financial_bonus

        scored.append({
            **stock,
            "research": research,
            "score": round(total_score, 1),
            "score_breakdown": {
                "base": score_hint,
                "theme_strength": bonus,
                "momentum": momentum_bonus,
                "dart_penalty": dart_penalty,
                "financial": round(financial_bonus, 1),
            },
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def select_final_candidates(
    scored: list[dict],
    stock_info_map: dict,
) -> tuple[list[dict], list[dict]]:
    """
    최종 15종목 선정.
    - 대형주 5개 (시총 상위)
    - 중소형주 10개 (점수 순)

    Returns:
        (selected, excluded)
    """
    large_cap_threshold = FILTERING.get("large_cap_threshold_kr", 5_000_000_000_000)
    large_cap_count = LARGE_CAP_COUNT
    small_mid_count = SMALL_MID_CAP_COUNT

    large_cap = []
    small_mid = []

    for stock in scored:
        ticker = stock.get("ticker", "")
        info = stock_info_map.get(ticker, {})
        market_cap = info.get("market_cap", 0)
        stock["market_cap"] = market_cap
        stock["current_price"] = info.get("current_price", 0)

        if market_cap >= large_cap_threshold:
            large_cap.append(stock)
        else:
            small_mid.append(stock)

    selected_large = large_cap[:large_cap_count]
    selected_small = small_mid[:small_mid_count]
    selected = selected_large + selected_small

    # 제외된 것들
    selected_tickers = {s.get("ticker") for s in selected}
    excluded = [
        {**s, "exclude_reason": f"점수 컷오프 (score={s.get('score', 0)})"}
        for s in scored if s.get("ticker") not in selected_tickers
    ]

    logger.info(
        f"Final selection: {len(selected_large)} large-cap + {len(selected_small)} mid/small "
        f"= {len(selected)} total"
    )
    return selected, excluded


def save_filter_results(
    passed: list[dict],
    excluded: list[dict],
    market: str,
    step: str = "step3",
) -> Path:
    """
    필터링 결과 JSON + MD 저장.
    """
    today = datetime.now().strftime("%Y%m%d")
    out_dir = DATA_DIR / today / market
    out_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "date": today,
        "market": market,
        "passed_count": len(passed),
        "excluded_count": len(excluded),
        "passed": passed,
        "excluded": excluded,
    }

    json_path = out_dir / f"{step}_filter.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # MD 리포트
    md_path = out_dir / f"{step}_filter.md"
    lines = [
        f"# {step.upper()} 필터링 결과 ({today} / {market.upper()})",
        "",
        f"## 통과 종목 ({len(passed)}개)",
        "",
    ]
    for s in passed:
        score = s.get("score", "?")
        theme = s.get("theme", "")
        lines.append(f"- **{s.get('name', s.get('ticker'))}** ({s.get('ticker', '')}) | 점수: {score} | 테마: {theme}")

    lines += ["", f"## 제외 종목 ({len(excluded)}개)", ""]
    for s in excluded:
        reason = s.get("exclude_reason", "?")
        lines.append(f"- {s.get('name', s.get('ticker'))} ({s.get('ticker', '')}) — {reason}")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    logger.info(f"Filter results saved → {json_path}")
    return json_path
