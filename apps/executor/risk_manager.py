import pandas as pd
import numpy as np
from typing import Optional

class RiskManager:
    """
    Manages trading risk using Kelly Criterion and ATR-based Stop Loss.
    """

    def __init__(self, leverage: int = 1, strategy_win_rate: float = 0.55, profit_loss_ratio: float = 1.5):
        self.leverage = leverage
        self.win_rate = strategy_win_rate  # Expected Win Rate
        self.ratio = profit_loss_ratio     # Reward/Risk Ratio

    def calculate_kelly_size(self, balance: float) -> float:
        """
        Calculates position size as a percentage of capital using Kelly Criterion.
        Formula: K% = W - (1 - W) / R
        """
        kelly_fraction = self.win_rate - ((1 - self.win_rate) / self.ratio)
        kelly_fraction = max(0, kelly_fraction)  # No negative allocation
        
        # Safe Kelly: typically use Half-Kelly to avoid ruin
        safe_allocation = (kelly_fraction * 0.5) * balance * self.leverage
        return safe_allocation

    def calculate_dynamic_stop_loss(self, df: pd.DataFrame, current_price: float, atr_period: int = 14, multiplier: float = 1.5, side: str = 'long') -> float:
        """
        Calculates dynamic Stop Loss using ATR.
        """
        if len(df) < atr_period:
            return current_price * 0.99 if side == 'long' else current_price * 1.01 # Fallback 1%

        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        atr = df['tr'].rolling(window=atr_period).mean().iloc[-1]
        
        if side == 'long':
            stop_loss = current_price - (atr * multiplier)
        else:
            stop_loss = current_price + (atr * multiplier)
            
        return stop_loss
