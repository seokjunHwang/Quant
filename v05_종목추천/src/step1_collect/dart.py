from __future__ import annotations
"""
Step 1-3: DART 전자공시 수집.
- 오늘 공시 목록
- 보호예수 해제 예정 (30일 이내)
- 유상증자 결정 공시
- 재무데이터 (현금, 부채비율)
"""

import logging
from datetime import timedelta

from src.utils.config import now_kst

import requests

from src.utils.config import DART_API_KEY

logger = logging.getLogger(__name__)
BASE_URL = "https://opendart.fss.or.kr/api"


def _get(endpoint: str, params: dict) -> dict:
    params["crtfc_key"] = DART_API_KEY
    resp = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_today_disclosures(market: str = "Y") -> list[dict]:
    """
    오늘 공시 목록.
    market: Y=유가(KOSPI), K=코스닥, N=코넥스
    """
    today = now_kst().strftime("%Y%m%d")
    try:
        data = _get("list.json", {
            "bgn_de": today, "end_de": today,
            "corp_cls": market, "page_count": 100,
        })
        if data.get("status") != "000":
            logger.warning(f"DART list error: {data.get('message')}")
            return []

        items = data.get("list", [])
        return [{
            "corp_name": i.get("corp_name"),
            "report_nm": i.get("report_nm"),
            "rcept_dt": i.get("rcept_dt"),
            "corp_code": i.get("corp_code"),
            "rcept_no": i.get("rcept_no"),
        } for i in items]
    except Exception as e:
        logger.error(f"Today disclosures failed: {e}")
        return []


# ── DART 리스크 캐시 (1회 실행 중 재사용) ─────────────────────

_rights_cache: set | None = None
_lockup_cache: set | None = None


def _load_rights_names(days_back: int = 30) -> set:
    """유상증자 결정 종목명 세트 (KOSPI+KOSDAQ, 캐싱)."""
    global _rights_cache
    if _rights_cache is not None:
        return _rights_cache

    end = now_kst()
    start = end - timedelta(days=days_back)
    names = set()

    for market in ["Y", "K"]:
        try:
            data = _get("list.json", {
                "bgn_de": start.strftime("%Y%m%d"),
                "end_de": end.strftime("%Y%m%d"),
                "corp_cls": market,
                "pblntf_detail_ty": "I001",
                "page_count": 100,
            })
            if data.get("status") == "000":
                for i in data.get("list", []):
                    names.add(i.get("corp_name", "").strip())
        except Exception as e:
            logger.debug(f"Rights cache load [{market}]: {e}")

    _rights_cache = names
    logger.info(f"DART 유상증자 캐시: {len(names)}건")
    return names


def _load_lockup_names(days_ahead: int = 30) -> set:
    """보호예수 해제 종목명 세트 (KOSPI+KOSDAQ, 캐싱)."""
    global _lockup_cache
    if _lockup_cache is not None:
        return _lockup_cache

    end = now_kst() + timedelta(days=days_ahead)
    start = now_kst()
    names = set()

    for market in ["Y", "K"]:
        try:
            data = _get("list.json", {
                "bgn_de": start.strftime("%Y%m%d"),
                "end_de": end.strftime("%Y%m%d"),
                "corp_cls": market,
                "pblntf_detail_ty": "B001",
                "page_count": 100,
            })
            if data.get("status") == "000":
                for i in data.get("list", []):
                    names.add(i.get("corp_name", "").strip())
        except Exception as e:
            logger.debug(f"Lockup cache load [{market}]: {e}")

    _lockup_cache = names
    logger.info(f"DART 보호예수 캐시: {len(names)}건")
    return names


def check_rights_offering(corp_name: str) -> bool:
    """종목이 최근 30일 유상증자 결정 공시에 있는지 확인."""
    return corp_name.strip() in _load_rights_names()


def check_lockup_release(corp_name: str) -> bool:
    """종목이 향후 30일 보호예수 해제 공시에 있는지 확인."""
    return corp_name.strip() in _load_lockup_names()


def get_corp_code(corp_name: str) -> str | None:
    """회사명 → DART corp_code 조회."""
    try:
        # 전체 기업 코드 목록 (zip 파일) - 캐싱 권장
        data = _get("company.json", {"corp_name": corp_name})
        if data.get("status") == "000":
            return data.get("corp_code")
    except Exception:
        pass
    return None


def check_risk(corp_name: str) -> dict:
    """
    종목의 DART 리스크 체크 (API 직접 조회).
    Returns: {"has_rights_offering": bool, "has_lockup": bool, "risk_score": int}
    """
    has_rights = check_rights_offering(corp_name)
    has_lockup = check_lockup_release(corp_name)

    risk_score = 0
    if has_rights:
        risk_score -= 30
    if has_lockup:
        risk_score -= 20

    return {
        "has_rights_offering": has_rights,
        "has_lockup_release": has_lockup,
        "risk_score": risk_score,
    }
