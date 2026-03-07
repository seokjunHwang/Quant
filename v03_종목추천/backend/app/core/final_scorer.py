"""
Step 5: Final Scorer — 종목 발굴 점수 + RSI 시그널 + 경고 감점을 합산하여 최종 랭킹 산출.

최종 점수 = 종목 발굴 점수 (Step 2)
           + RSI 시그널 보너스 (Step 4)
           - 경고 감점 (Step 3)

RSI 시그널 보너스:
  Regular Bullish  +15점
  Hidden Bullish   +10점
  Regular Bearish  -10점
  Hidden Bearish   -5점

경고 감점:
  경고 1개당 -5점
"""

import logging

from app.models.schemas import (
    DivergenceSignal,
    FinalRanking,
    ValidatedStock,
)

logger = logging.getLogger(__name__)

RSI_BONUS = {
    "regular_bullish": 15,
    "hidden_bullish": 10,
    "regular_bearish": -10,
    "hidden_bearish": -5,
}

WARNING_PENALTY_PER = -5


def calculate_final_scores(
    validated_stocks: list[ValidatedStock],
    rsi_signals: list[DivergenceSignal],
) -> list[FinalRanking]:
    """
    검증된 종목 + RSI 시그널을 합산하여 최종 랭킹 산출.

    Args:
        validated_stocks: Step 3에서 통과한 종목 리스트
        rsi_signals: Step 4에서 감지된 RSI 다이버전스 시그널

    Returns:
        최종 랭킹 리스트 (final_score 내림차순)
    """
    if not validated_stocks:
        return []

    # RSI 시그널을 티커별로 인덱싱 (가장 최근 시그널 사용)
    ticker_signals: dict[str, DivergenceSignal] = {}
    for signal in rsi_signals:
        if signal.ticker not in ticker_signals:
            ticker_signals[signal.ticker] = signal

    rankings: list[FinalRanking] = []

    for stock in validated_stocks:
        base_score = stock.discovery_score

        # RSI 보너스
        rsi_bonus = 0.0
        rsi_signal_label = None
        signal = ticker_signals.get(stock.ticker)
        if signal:
            rsi_bonus = RSI_BONUS.get(signal.signal_type, 0)
            rsi_signal_label = signal.signal_label

        # 경고 감점
        warning_penalty = stock.warning_count * WARNING_PENALTY_PER

        final_score = base_score + rsi_bonus + warning_penalty

        ranking = FinalRanking(
            rank=0,
            ticker=stock.ticker,
            name=stock.name,
            theme=stock.theme,
            theme_rank=stock.theme_rank,
            discovery_score=base_score,
            rsi_bonus=rsi_bonus,
            warning_penalty=warning_penalty,
            final_score=round(final_score, 2),
            market_cap=stock.market_cap,
            warnings=stock.warnings,
            rsi_signal=rsi_signal_label,
        )
        rankings.append(ranking)

    rankings.sort(key=lambda r: r.final_score, reverse=True)
    for i, r in enumerate(rankings):
        r.rank = i + 1

    logger.info(f"Final scoring complete: {len(rankings)} stocks ranked")
    if rankings:
        top = rankings[0]
        logger.info(
            f"  Top pick: {top.ticker} ({top.theme}) — "
            f"score {top.final_score} (base={top.discovery_score}, "
            f"rsi={top.rsi_bonus}, warn={top.warning_penalty})"
        )

    return rankings
