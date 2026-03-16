"""
Step 5-4: Gemini 최종 판단.

점수화된 종목에 대해 Gemini가 최종 매수 추천, 목표가, 손절가를 생성.
"""

import logging
from datetime import datetime

from src.utils.gemini_client import generate_json

logger = logging.getLogger(__name__)

JUDGE_SYSTEM = """당신은 미국 주식 단타 매매 전문가입니다.
주어진 종목 분석 데이터를 기반으로 매수 추천 여부, 목표가, 손절가를 판단합니다.
보수적으로 판단하세요. 확실하지 않으면 skip을 추천하세요."""

JUDGE_PROMPT = """다음 종목의 매수 여부를 판단하세요:

종목: {ticker} ({name})
섹터: {sector}
현재가: ${current_price:.2f}
시가총액: ${market_cap_m:.0f}M

점수 분석:
- 총점: {total_score}/110
- 로직체인 매칭: {logic}/30
- 스마트머니: {smart}/20
- 거래량/수급: {volume}/20
- 차트 기술적: {chart}/20
- VIX 가산점: {vix_bonus}/10
- 리스크 패널티: {risk}

추론된 시나리오: {scenario}
매칭된 로직체인: {chain_event}

아래 JSON으로 응답하세요:
{{
  "action": "buy | skip",
  "reasoning": "추천/비추천 이유 3줄 이내",
  "target_price": 0.00,
  "stop_loss": 0.00,
  "confidence": "high | medium | low",
  "hold_days": 3
}}"""


def judge_stock(
    scored: dict,
    scenarios: list[dict],
    matched_chains: list[dict],
) -> dict:
    """
    Gemini로 최종 매수 판단.

    Returns:
        {"action": "buy/skip", "reasoning": ..., "target_price": ..., "stop_loss": ...}
    """
    bd = scored["breakdown"]

    scenario_text = "없음"
    if scenarios:
        s = scenarios[0]
        scenario_text = f"{s.get('scenario', '')} (확률 {s.get('probability', 0):.0%})"

    chain_text = "없음"
    if matched_chains:
        c = matched_chains[0]
        chain_text = f"{c.get('event', '')} (유사도 {c.get('similarity', 0):.2f})"

    prompt = JUDGE_PROMPT.format(
        ticker=scored["ticker"],
        name=scored.get("name", scored["ticker"]),
        sector=scored.get("sector", "Unknown"),
        current_price=scored.get("current_price", 0),
        market_cap_m=scored.get("market_cap", 0) / 1e6,
        total_score=scored["total_score"],
        logic=bd["logic_chain_score"],
        smart=bd["smart_money_score"],
        volume=bd["volume_score"],
        chart=bd["chart_score"],
        vix_bonus=bd["vix_bonus"],
        risk=bd["risk_penalty"],
        scenario=scenario_text,
        chain_event=chain_text,
    )

    try:
        result = generate_json(prompt, system_instruction=JUDGE_SYSTEM, temperature=0.2)
        if isinstance(result, list):
            result = result[0]

        return {
            "ticker": scored["ticker"],
            "action": result.get("action", "skip"),
            "reasoning": result.get("reasoning", ""),
            "target_price": result.get("target_price", 0),
            "stop_loss": result.get("stop_loss", 0),
            "confidence": result.get("confidence", "low"),
            "hold_days": result.get("hold_days", 3),
            "ai_score": scored["total_score"],
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Final judge failed for {scored['ticker']}: {e}")
        return {
            "ticker": scored["ticker"],
            "action": "skip",
            "reasoning": f"AI 판단 실패: {e}",
            "target_price": 0,
            "stop_loss": 0,
            "confidence": "low",
        }
