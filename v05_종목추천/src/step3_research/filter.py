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
from src.utils.config import now_kst
from pathlib import Path

from src.utils.config import (
    DATA_DIR, DAILY_DIR, FILTERING,
    LARGE_CAP_KR, SMALL_MID_KR, LARGE_CAP_US, SMALL_MID_US,
)

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


def _is_ticker(s: str) -> bool:
    """영문 대문자+숫자+점으로만 구성된 문자열이면 티커로 판단."""
    import re
    return bool(re.match(r'^[A-Z0-9.]{1,10}$', s))


def _parse_ticker_hint(hint: str, market: str) -> tuple[str, str]:
    """
    "삼성전자(005930)" → ("삼성전자", "005930")
    "NVDA" → ("NVDA", "NVDA")
    "엔비디아(NVDA)" → ("엔비디아", "NVDA")
    "XOM(엑슨모빌)" → ("엑슨모빌", "XOM")  ← 티커/이름 뒤집힌 경우 자동 보정
    """
    hint = hint.strip()
    if "(" in hint and ")" in hint:
        left = hint[:hint.index("(")].strip()
        right = hint[hint.index("(")+1:hint.index(")")].strip()

        # 미장: 어느 쪽이 티커인지 자동 판별
        if market == "us":
            if _is_ticker(left) and not _is_ticker(right):
                return right, left  # "XOM(엑슨모빌)" → name=엑슨모빌, ticker=XOM
            elif _is_ticker(right) and not _is_ticker(left):
                return left, right  # "엔비디아(NVDA)" → name=엔비디아, ticker=NVDA
        # 국장 or 둘 다 동일 패턴: 기존 로직 (왼쪽=이름, 오른쪽=코드)
        return left, right
    else:
        name = hint
        ticker = hint if market == "us" else ""
    return name, ticker


def apply_dart_filter(
    candidates: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    DART 리스크 기반 필터 (후보 종목만 개별 API 조회).

    Returns:
        (passed, excluded)
        excluded items have "exclude_reason" field
    """
    from src.step1_collect.dart import check_rights_offering, check_lockup_release

    passed = []
    excluded = []

    kr_candidates = [s for s in candidates if s.get("market") == "kr"]
    us_candidates = [s for s in candidates if s.get("market") != "kr"]

    # 미장은 DART 체크 불필요
    passed.extend(us_candidates)

    for stock in kr_candidates:
        name = stock.get("name", "")
        corp_name = name.split("(")[0].strip()

        reasons = []
        if check_rights_offering(corp_name):
            reasons.append("유상증자 결정 (30일 이내)")
        if check_lockup_release(corp_name):
            reasons.append("보호예수 해제 예정 (30일 이내)")

        if reasons:
            logger.info(f"  DART 제외: {corp_name} — {', '.join(reasons)}")
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
    최종 종목 선정 (국장/미장 분리).
    - 국장: 대형 3 + 중소형 7 = 10
    - 미장: 대형 8 + 중소형 12 = 20

    Returns:
        (selected, excluded)
    """
    large_cap_threshold = FILTERING.get("large_cap_threshold_kr", 5_000_000_000_000)

    # 시가총액 정보 병합
    for stock in scored:
        ticker = stock.get("ticker", "")
        info = stock_info_map.get(ticker, {})
        stock["market_cap"] = info.get("market_cap", 0)
        stock["current_price"] = info.get("current_price", 0)

    # 시장별 분리 → 대형/중소형 선정
    selected = []
    for mkt, lg_count, sm_count in [("kr", LARGE_CAP_KR, SMALL_MID_KR),
                                     ("us", LARGE_CAP_US, SMALL_MID_US)]:
        mkt_stocks = [s for s in scored if s.get("market") == mkt]
        if mkt == "us":
            mkt_stocks += [s for s in scored if s.get("market") not in ("kr",)]
            mkt_stocks = list({s.get("ticker"): s for s in mkt_stocks}.values())

        large = [s for s in mkt_stocks if s.get("market_cap", 0) >= large_cap_threshold]
        small = [s for s in mkt_stocks if s.get("market_cap", 0) < large_cap_threshold]
        selected += large[:lg_count] + small[:sm_count]

    # 제외된 것들
    selected_tickers = {s.get("ticker") for s in selected}
    excluded = [
        {**s, "exclude_reason": f"점수 컷오프 (score={s.get('score', 0)})"}
        for s in scored if s.get("ticker") not in selected_tickers
    ]

    kr_sel = sum(1 for s in selected if s.get("market") == "kr")
    us_sel = len(selected) - kr_sel
    logger.info(f"Final selection: KR {kr_sel} + US {us_sel} = {len(selected)} total")
    return selected, excluded


STEP_DIRS = {
    "step3": "step3_종목필터링",
}


def save_filter_results(
    passed: list[dict],
    excluded: list[dict],
    market: str,
    step: str = "step3",
    today: str = "",
) -> Path:
    """
    필터링 결과 JSON + MD 저장.
    """
    if not today:
        today = now_kst().strftime("%Y%m%d")
    out_dir = DAILY_DIR / today / market / STEP_DIRS.get(step, step)
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
