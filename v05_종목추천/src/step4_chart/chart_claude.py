from __future__ import annotations
"""
Step 4-2: Claude CLI로 차트 해석.
기술적 지표 → Claude → 매매 타이밍 판단.
"""

import logging

from src.utils.claude_cli import ask_claude

logger = logging.getLogger(__name__)

CHART_PROMPT = """당신은 주식 차트 분석 전문가입니다.
아래 기술적 지표 데이터를 분석하여 단타/스윙 관점의 매매 타이밍을 판단해주세요.

=== 종목 정보 ===
종목명: {name} ({ticker})
시장: {market}
테마: {theme}

=== 기술적 지표 ===
현재가: {current_price}
RSI(14): {rsi} → {rsi_signal}
볼린저밴드 위치: {bb_pct:.1%} (0=하단, 1=상단)
MACD 크로스: {macd_cross}
거래량 비율(20일 대비): {volume_ratio:.1f}x
추세: {trend}
5일 등락률: {price_change_5d:+.1f}%
20일 등락률: {price_change_20d:+.1f}%
20일 지지: {support}
20일 저항: {resistance}

아래 JSON 형식으로 반환하세요:
{{
  "ticker": "{ticker}",
  "chart_score": 0~100,
  "timing": "매수적기/관망/매도적기",
  "entry_condition": "매수 진입 조건 (구체적으로)",
  "stop_loss": "손절 기준",
  "target_price": "목표가 또는 목표 등락률",
  "chart_summary": "차트 상황 2줄 요약",
  "signals": ["포지티브 신호들"],
  "warnings": ["주의할 점들"]
}}

규칙:
- chart_score: 단타/스윙 매매 적합도 (100이 최고)
- RSI 30 이하 + 볼린저 하단 = 과매도 반등 기대
- MACD 골든크로스 + 거래량 급증 = 강한 매수 신호
- RSI 70 이상 = 과매수 주의"""


def analyze_chart_claude(
    ticker: str,
    name: str,
    theme: str,
    market: str,
    chart_indicators: dict,
) -> dict:
    """
    기술적 지표 → Claude CLI → 차트 점수 + 매매 타이밍.

    Args:
        chart_indicators: indicators.analyze_chart() 결과

    Returns:
        {
            "ticker": ...,
            "chart_score": 0~100,
            "timing": "매수적기/관망/매도적기",
            "entry_condition": ...,
            "stop_loss": ...,
            "target_price": ...,
            "chart_summary": ...,
            "signals": [...],
            "warnings": [...],
        }
    """
    if not chart_indicators:
        return {
            "ticker": ticker,
            "chart_score": 50,
            "timing": "관망",
            "entry_condition": "데이터 부족",
            "stop_loss": "-",
            "target_price": "-",
            "chart_summary": "차트 데이터 없음",
            "signals": [],
            "warnings": ["OHLCV 데이터 수집 실패"],
        }

    prompt = CHART_PROMPT.format(
        ticker=ticker,
        name=name,
        theme=theme,
        market="한국" if market == "kr" else "미국",
        **chart_indicators,
    )

    logger.debug(f"  Chart analysis [{ticker}] via Claude...")
    result = ask_claude(prompt, expect_json=True, context=f"step4_chart_{ticker}")

    if isinstance(result, dict):
        result.setdefault("ticker", ticker)
        result.setdefault("chart_score", 50)
        result.setdefault("timing", "관망")
    else:
        result = {
            "ticker": ticker,
            "chart_score": 50,
            "timing": "관망",
            "entry_condition": "분석 실패",
            "stop_loss": "-",
            "target_price": "-",
            "chart_summary": "Claude 분석 실패",
            "signals": [],
            "warnings": [],
        }

    return result


def analyze_charts_batch(
    candidates: list[dict],
    ohlcv_map: dict,
    max_stocks: int = 40,
) -> list[dict]:
    """
    후보 종목 차트 일괄 분석.

    Args:
        candidates: [{"ticker": ..., "name": ..., "theme": ..., "market": ...}, ...]
        ohlcv_map: {ticker: pd.DataFrame}

    Returns:
        chart_results: [analyze_chart_claude() 결과, ...]
    """
    from src.step4_chart.indicators import analyze_chart

    targets = candidates[:max_stocks]
    results = []

    for i, stock in enumerate(targets):
        ticker = stock.get("ticker", "")
        name = stock.get("name", ticker)
        theme = stock.get("theme", "")
        market = stock.get("market", "us")

        df = ohlcv_map.get(ticker)
        indicators = analyze_chart(df) if df is not None else {}

        logger.info(f"  [{i+1}/{len(targets)}] {name}({ticker}) 차트 분석...")
        try:
            result = analyze_chart_claude(ticker, name, theme, market, indicators)
            result["raw_indicators"] = indicators
            results.append(result)
        except Exception as e:
            logger.warning(f"  [{ticker}] 차트 분석 실패: {e}")
            results.append({
                "ticker": ticker,
                "chart_score": 50,
                "timing": "관망",
                "chart_summary": f"분석 오류: {e}",
                "signals": [],
                "warnings": [],
                "raw_indicators": indicators,
            })

    return results
