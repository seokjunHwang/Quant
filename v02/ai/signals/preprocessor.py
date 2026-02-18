"""Feature preprocessing for XGBoost signal generation.

Adapted from /app/signals/crypto_preprocessor.py for v02 architecture.
"""

import pandas as pd
import pandas_ta as ta
import yfinance as yf


class CryptoPreprocessor:
    """Fetches market data and computes features for ML prediction."""

    def __init__(self, lookback_days: int = 120):
        self.lookback_days = lookback_days

    def fetch_data(self, symbol: str) -> pd.DataFrame:
        """Fetch OHLCV data from yfinance."""
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=f"{self.lookback_days}d")
        df.columns = [c.lower() for c in df.columns]
        return df[["open", "high", "low", "close", "volume"]]

    def compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute all technical features."""
        df = df.copy()

        # Returns
        df["return_1d"] = df["close"].pct_change()
        df["log_return"] = pd.Series(
            data=pd.array(df["close"] / df["close"].shift(1)).map(
                lambda x: float(pd.Series([x]).apply("log").iloc[0]) if x > 0 else 0
            ),
            index=df.index,
        )

        # Moving averages
        for period in [7, 14, 30]:
            df[f"sma_{period}"] = ta.sma(df["close"], length=period)
            df[f"ema_{period}"] = ta.ema(df["close"], length=period)

        # Momentum
        df["rsi_14"] = ta.rsi(df["close"], length=14)

        stoch = ta.stoch(df["high"], df["low"], df["close"], k=14, d=3)
        if stoch is not None:
            df["stoch_k"] = stoch.iloc[:, 0]
            df["stoch_d"] = stoch.iloc[:, 1]

        macd = ta.macd(df["close"])
        if macd is not None:
            df["macd"] = macd.iloc[:, 0]
            df["macd_signal"] = macd.iloc[:, 1]
            df["macd_hist"] = macd.iloc[:, 2]

        # Volatility
        df["atr_14"] = ta.atr(df["high"], df["low"], df["close"], length=14)
        bb = ta.bbands(df["close"], length=20)
        if bb is not None:
            df["bb_upper"] = bb.iloc[:, 2]
            df["bb_lower"] = bb.iloc[:, 0]
            df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / bb.iloc[:, 1]

        # Volume
        df["obv"] = ta.obv(df["close"], df["volume"])
        df["vol_ma_20"] = ta.sma(df["volume"], length=20)

        # CCI
        df["cci_14"] = ta.cci(df["high"], df["low"], df["close"], length=14)

        # ADX
        adx = ta.adx(df["high"], df["low"], df["close"], length=14)
        if adx is not None:
            df["adx"] = adx.iloc[:, 0]

        return df.dropna()

    def preprocess(self, symbol: str) -> pd.DataFrame:
        """Full pipeline: fetch → compute features → return latest row."""
        df = self.fetch_data(symbol)
        df = self.compute_features(df)
        return df
