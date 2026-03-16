"""
Step 6: 포지션 관리 & 주문 실행.

Alpaca Paper Trading (무료) 기반.
"""

import logging
from datetime import datetime

from src.utils.config import (
    ALPACA_API_KEY,
    ALPACA_BASE_URL,
    ALPACA_SECRET_KEY,
    MAX_POSITIONS,
    MIN_SCORE,
    RISK,
    SYSTEM_MODE,
)

logger = logging.getLogger(__name__)

# Lazy-loaded Alpaca client
_trading_client = None
_data_client = None


def _get_trading_client():
    """Alpaca Trading Client (lazy init)."""
    global _trading_client
    if _trading_client is None:
        if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
            logger.error("Alpaca API keys not configured")
            return None

        from alpaca.trading.client import TradingClient
        _trading_client = TradingClient(
            ALPACA_API_KEY,
            ALPACA_SECRET_KEY,
            paper=SYSTEM_MODE == "paper",
        )
    return _trading_client


def get_account_info() -> dict | None:
    """계좌 정보 조회."""
    client = _get_trading_client()
    if not client:
        return None

    try:
        account = client.get_account()
        return {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "portfolio_value": float(account.portfolio_value),
            "status": account.status,
        }
    except Exception as e:
        logger.error(f"Account info failed: {e}")
        return None


def get_positions() -> list[dict]:
    """현재 보유 포지션 조회."""
    client = _get_trading_client()
    if not client:
        return []

    try:
        positions = client.get_all_positions()
        return [
            {
                "ticker": p.symbol,
                "qty": float(p.qty),
                "avg_entry": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "unrealized_pnl": float(p.unrealized_pl),
                "unrealized_pnl_pct": float(p.unrealized_plpc) * 100,
                "market_value": float(p.market_value),
            }
            for p in positions
        ]
    except Exception as e:
        logger.error(f"Get positions failed: {e}")
        return []


def calc_position_size(
    equity: float,
    current_price: float,
    stop_loss: float,
) -> int:
    """
    켈리 공식 기반 포지션 사이즈 계산.

    Kelly fraction = 0.5 (보수적)
    Max loss per trade = 7%
    """
    if current_price <= 0 or stop_loss <= 0:
        return 0

    kelly_fraction = RISK.get("kelly_fraction", 0.5)
    max_loss_pct = RISK.get("max_loss_per_trade", 0.07)

    # Risk per share
    risk_per_share = abs(current_price - stop_loss)
    if risk_per_share == 0:
        return 0

    # Max capital at risk
    max_capital_risk = equity * max_loss_pct * kelly_fraction

    # Position size
    shares = int(max_capital_risk / risk_per_share)

    # Cap at 20% of equity per position
    max_shares_by_equity = int(equity * 0.20 / current_price)
    shares = min(shares, max_shares_by_equity)

    return max(shares, 0)


def submit_buy_order(
    ticker: str,
    qty: int,
    order_type: str = "market",
    limit_price: float | None = None,
) -> dict | None:
    """
    매수 주문 실행.

    Args:
        ticker: 종목 티커
        qty: 주문 수량
        order_type: "market" or "limit"
        limit_price: 지정가 (limit order일 때)
    """
    client = _get_trading_client()
    if not client:
        return None

    try:
        from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        if order_type == "limit" and limit_price:
            request = LimitOrderRequest(
                symbol=ticker,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                limit_price=limit_price,
            )
        else:
            request = MarketOrderRequest(
                symbol=ticker,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )

        order = client.submit_order(request)

        result = {
            "order_id": str(order.id),
            "ticker": ticker,
            "side": "buy",
            "qty": qty,
            "type": order_type,
            "status": order.status,
            "submitted_at": datetime.now().isoformat(),
        }

        logger.info(f"BUY order submitted: {ticker} x{qty} ({order_type})")
        return result

    except Exception as e:
        logger.error(f"Buy order failed [{ticker}]: {e}")
        return None


def submit_sell_order(
    ticker: str,
    qty: int,
    order_type: str = "market",
    limit_price: float | None = None,
) -> dict | None:
    """매도 주문 실행."""
    client = _get_trading_client()
    if not client:
        return None

    try:
        from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        if order_type == "limit" and limit_price:
            request = LimitOrderRequest(
                symbol=ticker,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                limit_price=limit_price,
            )
        else:
            request = MarketOrderRequest(
                symbol=ticker,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )

        order = client.submit_order(request)
        logger.info(f"SELL order submitted: {ticker} x{qty} ({order_type})")

        return {
            "order_id": str(order.id),
            "ticker": ticker,
            "side": "sell",
            "qty": qty,
            "type": order_type,
            "status": order.status,
            "submitted_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Sell order failed [{ticker}]: {e}")
        return None


def check_exit_conditions(position: dict, vix_data: dict) -> dict | None:
    """
    청산 조건 체크.

    Returns:
        None = hold, dict = exit signal
    """
    trailing_stop = RISK.get("trailing_stop_pct", 0.05)
    max_loss = RISK.get("max_loss_per_trade", 0.07)

    pnl_pct = position.get("unrealized_pnl_pct", 0) / 100

    # Stop loss hit
    if pnl_pct <= -max_loss:
        return {
            "ticker": position["ticker"],
            "reason": "stop_loss",
            "pnl_pct": round(pnl_pct * 100, 2),
        }

    # Trailing stop (simplified — full impl needs high watermark tracking)
    if pnl_pct > 0.05 and pnl_pct < trailing_stop:
        return {
            "ticker": position["ticker"],
            "reason": "trailing_stop",
            "pnl_pct": round(pnl_pct * 100, 2),
        }

    return None


def can_open_new_position() -> bool:
    """새 포지션 진입 가능한지 확인."""
    current = get_positions()
    return len(current) < MAX_POSITIONS
