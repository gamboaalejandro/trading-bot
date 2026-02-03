"""
Momentum Strategy - RSI + Moving Average Crossover
Generates buy signals when momentum is positive, sell when negative.
"""
from typing import Optional
import pandas as pd
import numpy as np

from .base_strategy import BaseStrategy, Signal, SignalType


class MomentumStrategy(BaseStrategy):
    """
    Momentum-based trading strategy using RSI and MA crossover.
    
    Buy Signal:
    - RSI > oversold_threshold (default 30)
    - Fast MA crosses above Slow MA
    - Bullish momentum
    
    Sell Signal:
    - RSI < overbought_threshold (default 70)
    - Fast MA crosses below Slow MA
    - Bearish momentum
    
    Parameters:
    - rsi_period: Period for RSI calculation (default 14)
    - fast_ma_period: Fast moving average period (default 10)
    - slow_ma_period: Slow moving average period (default 30)
    - oversold_threshold: RSI level for oversold (default 30)
    - overbought_threshold: RSI level for overbought (default 70)
    """
    
    def __init__(
        self,
        rsi_period: int = 14,
        fast_ma_period: int = 10,
        slow_ma_period: int = 30,
        oversold_threshold: float = 30.0,
        overbought_threshold: float = 70.0,
        name: str = "Momentum"
    ):
        super().__init__(name)
        
        self.rsi_period = rsi_period
        self.fast_ma_period = fast_ma_period
        self.slow_ma_period = slow_ma_period
        self.oversold_threshold = oversold_threshold
        self.overbought_threshold = overbought_threshold
        
        # Previous MA values for crossover detection
        self.prev_fast_ma = None
        self.prev_slow_ma = None
    
    def get_required_candles(self) -> int:
        """Need enough candles for slow MA + RSI."""
        return max(self.slow_ma_period, self.rsi_period) + 5
    
    def calculate_rsi(self, df: pd.DataFrame) -> pd.Series:
        """Calculate RSI indicator."""
        delta = df['close'].diff()
        
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def detect_crossover(self, fast_ma: float, slow_ma: float) -> Optional[str]:
        """
        Detect MA crossover.
        
        Returns:
            'bullish' if fast crosses above slow
            'bearish' if fast crosses below slow
            None if no crossover
        """
        if self.prev_fast_ma is None or self.prev_slow_ma is None:
            self.prev_fast_ma = fast_ma
            self.prev_slow_ma = slow_ma
            return None
        
        # Bullish crossover: fast was below slow, now above
        if self.prev_fast_ma <= self.prev_slow_ma and fast_ma > slow_ma:
            self.logger.debug(
                f"Bullish crossover detected: Fast MA {fast_ma:.2f} > Slow MA {slow_ma:.2f}"
            )
            crossover = 'bullish'
        # Bearish crossover: fast was above slow, now below
        elif self.prev_fast_ma >= self.prev_slow_ma and fast_ma < slow_ma:
            self.logger.debug(
                f"Bearish crossover detected: Fast MA {fast_ma:.2f} < Slow MA {slow_ma:.2f}"
            )
            crossover = 'bearish'
        else:
            crossover = None
        
        # Update previous values
        self.prev_fast_ma = fast_ma
        self.prev_slow_ma = slow_ma
        
        return crossover
    
    async def generate_signal(self, df: pd.DataFrame) -> Optional[Signal]:
        """Generate momentum-based trading signal."""
        
        # Calculate indicators
        df['rsi'] = self.calculate_rsi(df)
        df['fast_ma'] = df['close'].rolling(window=self.fast_ma_period).mean()
        df['slow_ma'] = df['close'].rolling(window=self.slow_ma_period).mean()
        
        # Get latest values
        current_price = df['close'].iloc[-1]
        current_rsi = df['rsi'].iloc[-1]
        fast_ma = df['fast_ma'].iloc[-1]
        slow_ma = df['slow_ma'].iloc[-1]
        
        # Check for NaN
        if pd.isna(current_rsi) or pd.isna(fast_ma) or pd.isna(slow_ma):
            self.logger.warning("Indicators contain NaN values")
            return None
        
        # Detect crossover
        crossover = self.detect_crossover(fast_ma, slow_ma)
        
        # Calculate confidence based on RSI and MA separation
        ma_separation = abs(fast_ma - slow_ma) / slow_ma  # Percentage separation
        
        # BUY SIGNAL
        if crossover == 'bullish' and current_rsi > self.oversold_threshold:
            # Confidence increases with:
            # - RSI further from oversold
            # - Greater MA separation
            rsi_factor = min((current_rsi - self.oversold_threshold) / 50.0, 1.0)
            ma_factor = min(ma_separation * 100, 0.5)  # Cap at 0.5
            confidence = 0.5 + (rsi_factor * 0.3) + (ma_factor * 0.2)
            confidence = min(confidence, 1.0)
            
            # Simple stop loss: 2% below entry
            stop_loss = current_price * 0.98
            # Take profit: 2x risk (4% above entry)
            take_profit = current_price * 1.04
            
            return Signal(
                signal_type=SignalType.BUY,
                confidence=confidence,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                metadata={
                    'strategy': self.name,
                    'rsi': current_rsi,
                    'fast_ma': fast_ma,
                    'slow_ma': slow_ma,
                    'crossover': crossover
                }
            )
        
        # SELL SIGNAL
        elif crossover == 'bearish' and current_rsi < self.overbought_threshold:
            # Confidence increases with:
            # - RSI further from overbought
            # - Greater MA separation
            rsi_factor = min((self.overbought_threshold - current_rsi) / 50.0, 1.0)
            ma_factor = min(ma_separation * 100, 0.5)
            confidence = 0.5 + (rsi_factor * 0.3) + (ma_factor * 0.2)
            confidence = min(confidence, 1.0)
            
            # Stop loss: 2% above entry
            stop_loss = current_price * 1.02
            # Take profit: 4% below entry
            take_profit = current_price * 0.96
            
            return Signal(
                signal_type=SignalType.SELL,
                confidence=confidence,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                metadata={
                    'strategy': self.name,
                    'rsi': current_rsi,
                    'fast_ma': fast_ma,
                    'slow_ma': slow_ma,
                    'crossover': crossover
                }
            )
        
        # HOLD - No clear signal
        return Signal(
            signal_type=SignalType.HOLD,
            confidence=0.0,
            entry_price=current_price,
            metadata={
                'strategy': self.name,
                'rsi': current_rsi,
                'fast_ma': fast_ma,
                'slow_ma': slow_ma,
                'reason': 'No crossover or RSI out of range'
            }
        )
