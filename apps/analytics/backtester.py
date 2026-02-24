"""
Statistical Backtester - Core Engine
Fetches historical data and runs vectorized strategy logic for rapid optimization.
"""
import pandas as pd
import numpy as np
import requests
import logging
from typing import Dict, List, Optional
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Backtester")

class Backtester:
    """
    Rapid backtesting engine for technical indicators.
    Connects to Binance Public API (no keys needed for history).
    """

    # Try Binance US first (often works in US-based sandboxes)
    # If this fails, we can fall back to mocking data for demonstration
    BASE_URL = "https://api.binance.us/api/v3/klines"

    def __init__(self, symbol: str, timeframe: str = '1h', limit: int = 1000):
        self.symbol = symbol.replace('/', '').upper()
        self.timeframe = timeframe
        self.limit = limit
        self.df = pd.DataFrame()

    def fetch_data(self):
        """Fetch historical OHLCV data from Binance."""
        params = {
            'symbol': self.symbol,
            'interval': self.timeframe,
            'limit': self.limit
        }

        try:
            logger.info(f"Fetching data from {self.BASE_URL} for {self.symbol}...")
            response = requests.get(self.BASE_URL, params=params, timeout=10)

            if response.status_code == 451:
                 # If geo-blocked, try mock data for demonstration
                logger.warning("Geo-blocked by Binance US (451). Using MOCK data for demonstration.")
                return self._generate_mock_data()

            response.raise_for_status()
            data = response.json()

            if not data:
                logger.warning("No data received.")
                return pd.DataFrame()

            # [open_time, open, high, low, close, volume, ...]
            self.df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'trades',
                'taker_buy_base', 'taker_buy_quote', 'ignore'
            ])

            # Convert types
            cols = ['open', 'high', 'low', 'close', 'volume']
            self.df[cols] = self.df[cols].astype(float)
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'], unit='ms')

            logger.info(f"Loaded {len(self.df)} candles for {self.symbol}")
            return self.df

        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            logger.info("Falling back to MOCK data for demonstration.")
            return self._generate_mock_data()

    def _generate_mock_data(self):
        """Generate realistic-looking mock data for testing logic."""
        dates = pd.date_range(end=pd.Timestamp.now(), periods=self.limit, freq=self.timeframe)

        # Random Walk
        np.random.seed(42)
        returns = np.random.normal(0.0005, 0.02, self.limit) # Mean 0.05%, Std 2%
        price_path = 100 * np.cumprod(1 + returns)

        self.df = pd.DataFrame({
            'timestamp': dates,
            'open': price_path,
            'high': price_path * 1.01,
            'low': price_path * 0.99,
            'close': price_path * (1 + np.random.normal(0, 0.005, self.limit)),
            'volume': np.random.randint(100, 10000, self.limit)
        })
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
