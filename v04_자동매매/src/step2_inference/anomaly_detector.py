"""
Step 2-1: 이상 신호 집계 및 패턴 감지.

Step 1에서 수집된 개별 신호들을 종합하여 "동시 발생 패턴"을 감지.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def aggregate_anomalies(
    macro_result: dict,
    smart_money_result: dict,
) -> list[dict]:
    """
    매크로 + 스마트머니 이상 신호를 합치고 severity 기준으로 정렬.

    Returns:
        정렬된 이상 신호 리스트
    """
    all_anomalies = []

    # Macro anomalies
    all_anomalies.extend(macro_result.get("anomalies", []))

    # Smart money anomalies
    all_anomalies.extend(smart_money_result.get("anomalies", []))

    # Sort by severity (high > medium > low)
    severity_order = {"high": 0, "medium": 1, "low": 2}
    all_anomalies.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 3))

    return all_anomalies


def build_anomaly_summary(anomalies: list[dict]) -> str:
    """
    이상 신호들을 AI에게 보낼 텍스트 요약으로 변환.
    이 텍스트가 Step 2-2(역추론)와 Phase 0(벡터 검색)에 사용됨.
    """
    if not anomalies:
        return "현재 감지된 이상 신호 없음"

    lines = []
    for i, a in enumerate(anomalies, 1):
        severity = a.get("severity", "?")
        desc = a.get("description", "")
        ticker = a.get("ticker", "")
        prefix = f"[{severity.upper()}]"
        ticker_str = f" ({ticker})" if ticker else ""
        lines.append(f"{i}. {prefix} {desc}{ticker_str}")

    return "\n".join(lines)


def build_search_query(anomalies: list[dict]) -> str:
    """
    이상 신호를 ChromaDB 검색 쿼리용 텍스트로 변환.
    pre_signals 필드와 매칭하기 위한 용도.
    """
    # Extract key terms for vector search
    terms = []

    for a in anomalies:
        signal_type = a.get("signal_type", "")
        desc = a.get("description", "")

        if signal_type == "macro_anomaly":
            terms.append(desc)
        elif signal_type in ("volume_surge", "insider_buy"):
            # Generic: 특정 종목명 제외하고 패턴만
            if "거래량" in desc:
                terms.append("거래량 급증")
            if "내부자" in desc:
                terms.append("내부자 매수")
        elif signal_type == "yield_curve":
            terms.append("수익률 역전 yield curve inversion")

    return ", ".join(terms) if terms else "no anomalies detected"
