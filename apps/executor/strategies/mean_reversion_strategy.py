"""
Mean Reversion Strategy - Bollinger Bands + RSI
Trades on the assumption that price will return to the mean.
"""
from typing import Optional
import pandas as pd
import numpy as np

from .base_strategy import BaseStrategy, Signal, SignalType


class MeanReversionStrategy(BaseStrategy):
    """
    Mean reversion strategy using Bollinger Bands and RSI.
    
    Buy Signal:
    - Price touches or goes below lower Bollinger Band
    - RSI < oversold_threshold (default 30)
    - Expecting bounce back to mean
    
    Sell Signal:
    - Price touches or goes above upper Bollinger Band
    - RSI > overbought_threshold (default 70)
    - Expecting pullback to mean
    
    Parameters:
    - bb_period: Period for Bollinger Bands (default 20)
    - bb_std: Standard deviation multiplier (default 2.0)
    - rsi_period: Period for RSI (default 14)
    - oversold_threshold: RSI oversold level (default 30)
    - overbought_threshold: RSI overbought level (default 70)
    """
    
    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        oversold_threshold: float = 30.0,
        overbought_threshold: float = 70.0,
        name: str = "MeanReversion"
    ):
        super().__init__(name)
        
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.oversold_threshold = oversold_threshold
        self.overbought_threshold = overbought_threshold
    
    def get_required_candles(self) -> int:
        """Need enough candles for BB + RSI."""
        return max(self.bb_period, self.rsi_period) + 5
    
    def calculate_rsi(self, df: pd.DataFrame) -> pd.Series:
        """Calculate RSI indicator."""
        delta = df['close'].diff()
        
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calculate_bollinger_bands(self, df: pd.DataFrame) -> tuple:
        """
        Calculate Bollinger Bands.
        
        Returns:
            (middle_band, upper_band, lower_band)
        """
        middle_band = df['close'].rolling(window=self.bb_period).mean()
        std = df['close'].rolling(window=self.bb_period).std()
        
        upper_band = middle_band + (std * self.bb_std)
        lower_band = middle_band - (std * self.bb_std)
        
        return middle_band, upper_band, lower_band
    
    async def generate_signal(self, df: pd.DataFrame) -> Optional[Signal]:
        """Generate mean reversion trading signal."""
        
        # Calculate indicators
        df['rsi'] = self.calculate_rsi(df)
        df['bb_middle'], df['bb_upper'], df['bb_lower'] = self.calculate_bollinger_bands(df)
        
        # Get latest values
        current_price = df['close'].iloc[-1]
        current_rsi = df['rsi'].iloc[-1]
        bb_middle = df['bb_middle'].iloc[-1]
        bb_upper = df['bb_upper'].iloc[-1]
        bb_lower = df['bb_lower'].iloc[-1]
        
        # Check for NaN
        if any(pd.isna(val) for val in [current_rsi, bb_middle, bb_upper, bb_lower]):
            self.logger.warning("Indicators contain NaN values")
            return None
        
        # Calculate price position within bands (0 = lower band, 1 = upper band)
        bb_width = bb_upper - bb_lower
        if bb_width == 0:
            self.logger.warning("Bollinger Bands have zero width")
            return None
        
        price_position = (current_price - bb_lower) / bb_width
        
        # BUY SIGNAL - Price near/below lower band + oversold RSI
        if price_position <= 0.1 and current_rsi < self.oversold_threshold:
            # Confidence increases with:
            # - Price closer to lower band
            # - RSI more oversold
            # - Tighter bands (higher volatility means stronger signal)
            
            band_factor = max(0, 1.0 - (price_position / 0.1))  # 1.0 at lower band, 0.0 at 10%
            rsi_factor = 1.0 - (current_rsi / self.oversold_threshold)
            
            confidence = 0.5 + (band_factor * 0.3) + (rsi_factor * 0.2)
            confidence = min(confidence, 1.0)
            
            # Stop loss: below lower band
            stop_loss = bb_lower * 0.99
            # Take profit: middle band (mean reversion target)
            take_profit = bb_middle
            
            return Signal(
                signal_type=SignalType.BUY,
                confidence=confidence,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                metadata={
                    'strategy': self.name,
                    'rsi': current_rsi,
                    'price_position': price_position,
                    'bb_lower': bb_lower,
                    'bb_middle': bb_middle,
                    'bb_upper': bb_upper,
                    'reason': 'Price near lower band + oversold'
                }
            )
        
        # SELL SIGNAL - Price near/above upper band + overbought RSI
        elif price_position >= 0.9 and current_rsi > self.overbought_threshold:
            # Confidence increases with:
            # - Price closer to upper band
            # - RSI more overbought
            
            band_factor = (price_position - 0.9) / 0.1  # 0.0 at 90%, 1.0 at upper band
            rsi_factor = (current_rsi - self.overbought_threshold) / (100 - self.overbought_threshold)
            
            confidence = 0.5 + (band_factor * 0.3) + (rsi_factor * 0.2)
            confidence = min(confidence, 1.0)
            
            # Stop loss: above upper band
            stop_loss = bb_upper * 1.01
            # Take profit: middle band
            take_profit = bb_middle
            
            return Signal(
                signal_type=SignalType.SELL,
                confidence=confidence,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                metadata={
                    'strategy': self.name,
                    'rsi': current_rsi,
                    'price_position': price_position,
                    'bb_lower': bb_lower,
                    'bb_middle': bb_middle,
                    'bb_upper': bb_upper,
                    'reason': 'Price near upper band + overbought'
                }
            )
        
        # HOLD - Price within normal range
        return Signal(
            signal_type=SignalType.HOLD,
            confidence=0.0,
            entry_price=current_price,
            metadata={
                'strategy': self.name,
                'rsi': current_rsi,
                'price_position': price_position,
                'bb_lower': bb_lower,
                'bb_middle': bb_middle,
                'bb_upper': bb_upper,
                'reason': f'Price in middle range ({price_position:.1%})'
            }
        )
