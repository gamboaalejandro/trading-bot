"""
Statistical Backtester - Core Engine (DEPRECATED)

DEPRECATED: this legacy backtester ignores trading costs, uses the
in-progress candle and must not be used to make decisions. Use
``apps.research`` (see docs/research/PLAN.md) instead.

It never generates synthetic data: any download problem raises
BacktestDataError.
"""
import warnings

import pandas as pd
import numpy as np
import requests
import logging
from typing import Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Backtester")

DEPRECATION_MESSAGE = (
    "apps.analytics.backtester is DEPRECATED (no costs, no data validation); "
    "use apps.research instead"
)


class BacktestDataError(RuntimeError):
    """Historical data could not be obtained. There is no mock fallback."""


class Backtester:
    """
    DEPRECATED rapid backtesting engine for technical indicators.
    Connects to Binance Public API (no keys needed for history).
    """

    BASE_URL = "https://api.binance.us/api/v3/klines"

    def __init__(self, symbol: str, timeframe: str = '1h', limit: int = 1000):
        warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=2)
        self.symbol = symbol.replace('/', '').upper()
        self.timeframe = timeframe
        self.limit = limit
        self.df = pd.DataFrame()

    def fetch_data(self) -> pd.DataFrame:
        """
        Fetch historical OHLCV data from Binance.

        Raises:
            BacktestDataError: on any network/HTTP error (including 451
                geo-blocking), an empty answer or a malformed payload.
        """
        params = {
            'symbol': self.symbol,
            'interval': self.timeframe,
            'limit': self.limit
        }

        logger.info(f"Fetching data from {self.BASE_URL} for {self.symbol}...")
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            raise BacktestDataError(f"Could not download klines for {self.symbol}: {e}") from e

        if not data:
            raise BacktestDataError(f"No klines received for {self.symbol} {self.timeframe}")

        try:
            # [open_time, open, high, low, close, volume, ...]
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'trades',
                'taker_buy_base', 'taker_buy_quote', 'ignore'
            ])
            cols = ['open', 'high', 'low', 'close', 'volume']
            df[cols] = df[cols].astype(float)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        except (ValueError, TypeError) as e:
            raise BacktestDataError(f"Malformed klines payload for {self.symbol}: {e}") from e

        self.df = df
        logger.info(f"Loaded {len(self.df)} candles for {self.symbol}")
        return self.df

    def run_momentum(self, rsi_period: int = 14, ma_fast: int = 10, ma_slow: int = 30) -> Dict:
        """
        Backtest Momentum Strategy (RSI + MA Crossover).
        Vectorized implementation for speed.
        """
        if self.df.empty:
            self.fetch_data()

        df = self.df.copy()

        # Calculate Indicators
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # MAs
        df['ma_fast'] = df['close'].rolling(window=ma_fast).mean()
        df['ma_slow'] = df['close'].rolling(window=ma_slow).mean()

        # Signals
        # Buy: Fast > Slow AND RSI > 50 (Momentum)
        df['signal'] = 0
        df.loc[(df['ma_fast'] > df['ma_slow']) & (df['rsi'] > 50), 'signal'] = 1

        # Sell: Fast < Slow OR RSI < 50
        df.loc[(df['ma_fast'] < df['ma_slow']) | (df['rsi'] < 50), 'signal'] = -1

        # Calculate Returns
        # Strategy takes position at close of signal candle, realizes return on next candle
        df['pct_change'] = df['close'].pct_change().shift(-1)

        # Strategy Return: Long only (Spot)
        # If signal is 1, we hold. If -1 or 0, we are cash (return 0).
        df['strategy_return'] = df['pct_change'] * (df['signal'] > 0).astype(int)

        return self._calculate_metrics(df)

    def run_mean_reversion(self, rsi_period: int = 14, bb_period: int = 20, bb_std: float = 2.0) -> Dict:
        """
        Backtest Mean Reversion Strategy (Bollinger Bands + RSI).
        """
        if self.df.empty:
            self.fetch_data()

        df = self.df.copy()

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # Bollinger Bands
        df['bb_mid'] = df['close'].rolling(window=bb_period).mean()
        df['bb_std'] = df['close'].rolling(window=bb_period).std()
        df['bb_upper'] = df['bb_mid'] + (df['bb_std'] * bb_std)
        df['bb_lower'] = df['bb_mid'] - (df['bb_std'] * bb_std)

        # Signals
        # Buy: Price < Lower Band AND RSI < 30
        df['signal'] = 0
        df.loc[(df['close'] < df['bb_lower']) & (df['rsi'] < 30), 'signal'] = 1

        # Sell: Price > Upper Band OR RSI > 70
        df.loc[(df['close'] > df['bb_upper']) | (df['rsi'] > 70), 'signal'] = -1

        # Position Management (Stateful logic needed for mean reversion holding)
        # Vectorized approximation:
        # If we bought, hold until sell signal.
        # Use ffill to propagate '1' (holding) forward until '-1' (sell).
        df['position'] = df['signal'].replace(0, np.nan)
        df['position'] = df['position'].ffill().fillna(0)

        # Strategy Return
        df['pct_change'] = df['close'].pct_change().shift(-1)
        df['strategy_return'] = df['pct_change'] * (df['position'] == 1).astype(int)

        return self._calculate_metrics(df)

    def _calculate_metrics(self, df: pd.DataFrame) -> Dict:
        """Calculate performance metrics."""
        # Fill NaN returns with 0
        df['strategy_return'] = df['strategy_return'].fillna(0)

        df['cum_return'] = (1 + df['strategy_return']).cumprod()

        total_return = df['cum_return'].iloc[-1] - 1 if not df.empty else 0
        annualized_return = total_return * (365 * 24 / self.limit) # Approx

        # Sharpe Ratio (assuming risk-free rate 0)
        if df['strategy_return'].std() == 0:
            sharpe = 0
        else:
            sharpe = (df['strategy_return'].mean() / df['strategy_return'].std()) * np.sqrt(365 * 24)

        # Max Drawdown
        cum_max = df['cum_return'].cummax()
        drawdown = (df['cum_return'] - cum_max) / cum_max
        max_drawdown = drawdown.min()

        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'trades': df['signal'].abs().sum()
        }

if __name__ == "__main__":
    # Test Run
    bt = Backtester("SOL/USDT", timeframe="1h", limit=1000)
    bt.fetch_data()

    print("=== MOMENTUM (Default) ===")
    metrics = bt.run_momentum(rsi_period=14, ma_fast=10, ma_slow=30)
    print(metrics)

    print("\n=== MEAN REVERSION (Default) ===")
    metrics_mr = bt.run_mean_reversion(rsi_period=14, bb_period=20, bb_std=2.0)
    print(metrics_mr)
