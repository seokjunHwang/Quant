from __future__ import annotations
"""
Step 1-3: DART 전자공시 수집.
- 오늘 공시 목록
- 보호예수 해제 예정 (30일 이내)
- 유상증자 결정 공시
- 재무데이터 (현금, 부채비율)
"""

import logging
from datetime import datetime, timedelta

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
    today = datetime.now().strftime("%Y%m%d")
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


def get_rights_offerings(days_back: int = 30) -> list[dict]:
    """
    최근 유상증자 결정 공시 목록.
    → 이 종목들은 주가 희석 리스크 → 제외 대상
    """
    end = datetime.now()
    start = end - timedelta(days=days_back)

    results = []
    for market in ["Y", "K"]:
        try:
            data = _get("list.json", {
                "bgn_de": start.strftime("%Y%m%d"),
                "end_de": end.strftime("%Y%m%d"),
                "corp_cls": market,
                "pblntf_detail_ty": "I001",  # 유상증자결정
                "page_count": 100,
            })
            if data.get("status") == "000":
                for i in data.get("list", []):
                    results.append({
                        "corp_name": i.get("corp_name"),
                        "corp_code": i.get("corp_code"),
                        "report_nm": i.get("report_nm"),
                        "rcept_dt": i.get("rcept_dt"),
                        "risk": "유상증자",
                    })
        except Exception as e:
            logger.warning(f"Rights offerings [{market}] failed: {e}")

    logger.info(f"Rights offerings found: {len(results)}")
    return results


def get_lockup_releases(days_ahead: int = 30) -> list[dict]:
    """
    보호예수 해제 예정 종목 (의무보유확약 해제).
    → 매도 압력 리스크 → 감점 대상
    """
    end = datetime.now() + timedelta(days=days_ahead)
    start = datetime.now()

    results = []
    for market in ["Y", "K"]:
        try:
            data = _get("list.json", {
                "bgn_de": start.strftime("%Y%m%d"),
                "end_de": end.strftime("%Y%m%d"),
                "corp_cls": market,
                "pblntf_detail_ty": "B001",  # 의무보유확약 해제
                "page_count": 100,
            })
            if data.get("status") == "000":
                for i in data.get("list", []):
                    results.append({
                        "corp_name": i.get("corp_name"),
                        "corp_code": i.get("corp_code"),
                        "report_nm": i.get("report_nm"),
                        "release_date": i.get("rcept_dt"),
                        "risk": "보호예수해제",
                    })
        except Exception as e:
            logger.warning(f"Lockup releases [{market}] failed: {e}")

    logger.info(f"Lockup releases found: {len(results)}")
    return results


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


def check_risk(corp_name: str, rights_list: list[dict], lockup_list: list[dict]) -> dict:
    """
    종목의 DART 리스크 체크.
    Returns: {"has_rights_offering": bool, "has_lockup": bool, "risk_score": int}
    """
    rights_names = {r["corp_name"] for r in rights_list}
    lockup_names = {l["corp_name"] for l in lockup_list}

    has_rights = corp_name in rights_names
    has_lockup = corp_name in lockup_names

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
