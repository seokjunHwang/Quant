from __future__ import annotations
"""
Step 3-2: DART 재무데이터 수집.
현금, 부채비율, 영업이익 등 기본 재무 지표.
"""

import logging

import requests

from src.utils.config import DART_API_KEY

logger = logging.getLogger(__name__)
BASE_URL = "https://opendart.fss.or.kr/api"


def _get(endpoint: str, params: dict) -> dict:
    params["crtfc_key"] = DART_API_KEY
    resp = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_corp_code_by_name(corp_name: str) -> str | None:
    """회사명 → DART corp_code 조회."""
    try:
        data = _get("company.json", {"corp_name": corp_name})
        if data.get("status") == "000":
            return data.get("corp_code")
    except Exception as e:
        logger.debug(f"corp_code lookup failed [{corp_name}]: {e}")
    return None


def get_financial_summary(corp_code: str, year: int | None = None) -> dict:
    """
    DART 단일회사 주요재무지표 조회.
    Returns: {"revenue": ..., "op_income": ..., "net_income": ..., "debt_ratio": ..., "cash": ...}
    """
    from src.utils.config import now_kst
    if year is None:
        year = now_kst().year - 1  # 전년도 사업보고서

    try:
        data = _get("fnlttSinglAcntAll.json", {
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": "11011",  # 사업보고서
            "fs_div": "CFS",        # 연결재무제표 우선
        })

        if data.get("status") != "000":
            # 연결 없으면 별도 시도
            data = _get("fnlttSinglAcntAll.json", {
                "corp_code": corp_code,
                "bsns_year": str(year),
                "reprt_code": "11011",
                "fs_div": "OFS",
            })

        if data.get("status") != "000":
            return {}

        items = {i.get("account_nm"): i.get("thstrm_amount", "0")
                 for i in data.get("list", [])}

        def parse_amount(key: str) -> float:
            val = items.get(key, "0") or "0"
            try:
                return float(val.replace(",", ""))
            except ValueError:
                return 0.0

        revenue = parse_amount("매출액")
        op_income = parse_amount("영업이익")
        net_income = parse_amount("당기순이익")
        total_assets = parse_amount("자산총계")
        total_liabilities = parse_amount("부채총계")
        cash = parse_amount("현금및현금성자산")

        debt_ratio = round(total_liabilities / total_assets * 100, 1) if total_assets else 0

        return {
            "year": year,
            "revenue": revenue,
            "op_income": op_income,
            "net_income": net_income,
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "debt_ratio": debt_ratio,
            "cash": cash,
            "op_margin": round(op_income / revenue * 100, 1) if revenue else 0,
        }

    except Exception as e:
        logger.warning(f"Financial data failed [{corp_code}]: {e}")
        return {}


def get_financial_score(financials: dict) -> int:
    """
    재무 점수 계산 (0~100).
    - 부채비율 낮을수록 +
    - 영업이익률 높을수록 +
    - 현금 보유 +
    """
    if not financials:
        return 50  # 데이터 없으면 중간값

    score = 50

    # 부채비율 (낮을수록 좋음)
    debt_ratio = financials.get("debt_ratio", 100)
    if debt_ratio < 50:
        score += 20
    elif debt_ratio < 100:
        score += 10
    elif debt_ratio > 200:
        score -= 15
    elif debt_ratio > 150:
        score -= 10

    # 영업이익률
    op_margin = financials.get("op_margin", 0)
    if op_margin > 15:
        score += 20
    elif op_margin > 8:
        score += 10
    elif op_margin < 0:
        score -= 20
    elif op_margin < 3:
        score -= 5

    # 당기순이익 흑자/적자
    net_income = financials.get("net_income", 0)
    if net_income > 0:
        score += 10
    elif net_income < 0:
        score -= 10

    return max(0, min(100, score))


def enrich_kr_stocks(
    stocks: list[dict],
) -> list[dict]:
    """
    국장 종목 리스트에 DART 재무/리스크 데이터 추가.

    Args:
        stocks: [{"ticker": ..., "name": ..., ...}, ...]

    Returns:
        enriched stocks with financial_score, dart_risk added
    """
    from src.step1_collect.dart import check_risk

    enriched = []
    for stock in stocks:
        name = stock.get("name", "")
        corp_name = name.split("(")[0].strip()  # 괄호 있으면 제거

        # DART 리스크 (개별 종목 API 조회)
        dart_risk = check_risk(corp_name)

        # 재무 (corp_code 필요)
        financials = {}
        financial_score = 50
        corp_code = stock.get("corp_code")
        if not corp_code:
            corp_code = get_corp_code_by_name(corp_name)

        if corp_code:
            financials = get_financial_summary(corp_code)
            financial_score = get_financial_score(financials)

        enriched.append({
            **stock,
            "corp_code": corp_code,
            "financials": financials,
            "financial_score": financial_score,
            "dart_risk": dart_risk,
        })

    return enriched
