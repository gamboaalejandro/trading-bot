"""
Professional Risk Management Module
Implements Kelly Criterion with circuit breakers and safety limits.
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class RiskConfig:
    """Risk management configuration parameters."""
    max_account_risk_per_trade: float = 0.02  # Never risk more than 2% per trade (Layer over Kelly)
    max_daily_drawdown: float = 0.05          # If you lose 5% in a day, STOP completely
    max_leverage: int = 5                     # Hard leverage limit
    min_notional_usdt: float = 6.0            # Binance minimum (~5.1 USDT)
    kelly_fraction: float = 0.25              # Full Kelly is too volatile, use 1/4 or 1/2
    
    # Stop loss configuration
    default_atr_period: int = 14
    default_atr_multiplier: float = 2.0       # Increased from 1.5 for crypto volatility
    
    # Volatility filter
    max_volatility_threshold: float = 0.05    # 5% ATR threshold


class ProfessionalRiskManager:
    """
    Professional-grade risk manager with circuit breakers and Kelly Criterion.
    
    Features:
    - Daily drawdown circuit breaker
    - Fractional Kelly position sizing
    - Hard risk caps per trade
    - Volatility-based filters
    - Notional value validation
    - ATR-based dynamic stop losses
    """
    
    def __init__(self, config: RiskConfig, current_daily_pnl: float = 0.0):
        """
        Initialize risk manager.
        
        Args:
            config: Risk configuration parameters
            current_daily_pnl: Current day's P&L (negative for losses)
        """
        self.cfg = config
        self.current_daily_loss = current_daily_pnl  # Must be updated from accounting system
        
    def update_daily_pnl(self, pnl: float):
        """Update current daily P&L."""
        self.current_daily_loss = pnl
        
    def calculate_safe_size(
        self,
        balance: float,
        entry_price: float,
        stop_loss_price: float,
        win_rate: float,
        reward_ratio: float
    ) -> float:
        """
        Calculate position size combining Kelly with hard risk limits.
        Returns quantity in BASE CURRENCY (e.g., amount of BTC).
        
        Args:
            balance: Account balance in USDT
            entry_price: Planned entry price
            stop_loss_price: Stop loss price
            win_rate: Expected win rate (0.0 to 1.0)
            reward_ratio: Reward/Risk ratio (e.g., 2.0 = 2:1)
            
        Returns:
            Position size in base currency, or 0.0 if trade is blocked
        """
        
        # 1. Circuit Breaker: Daily Drawdown
        max_daily_loss = balance * self.cfg.max_daily_drawdown
        if self.current_daily_loss <= -max_daily_loss:
            logger.warning(
                f"⚠️ KILL SWITCH ACTIVATED: Daily loss limit reached "
                f"({self.current_daily_loss:.2f} / -{max_daily_loss:.2f})"
            )
            return 0.0

        # 2. Kelly Calculation (Fractional)
        if reward_ratio == 0:
            logger.warning("Reward ratio is 0, cannot calculate Kelly")
            return 0.0
            
        kelly_pct = win_rate - ((1 - win_rate) / reward_ratio)
        kelly_pct = max(0, kelly_pct) * self.cfg.kelly_fraction
        
        logger.debug(f"Kelly %: {kelly_pct:.4f} (fractional: {self.cfg.kelly_fraction})")
        
        # 3. Hard Risk Cap (The safety net)
        # Even if Kelly says 20%, if our hard cap is 2%, we use 2%.
        position_size_equity_pct = min(kelly_pct, self.cfg.max_account_risk_per_trade)
        
        logger.debug(
            f"Position size %: {position_size_equity_pct:.4f} "
            f"(capped at {self.cfg.max_account_risk_per_trade})"
        )
        
        # 4. Size Calculation Based on Risk Amount (Distance to Stop Loss)
        # How much money do I lose if SL is hit?
        risk_per_share = abs(entry_price - stop_loss_price)
        if risk_per_share == 0:
            logger.warning("Risk per share is 0 (entry == stop loss)")
            return 0.0
        
        risk_amount_usdt = balance * position_size_equity_pct
        quantity_asset = risk_amount_usdt / risk_per_share
        
        logger.debug(
            f"Risk amount: ${risk_amount_usdt:.2f} | "
            f"Risk per unit: ${risk_per_share:.2f} | "
            f"Quantity: {quantity_asset:.6f}"
        )
        
        # 5. Notional Value Validation (Binance requirement)
        notional_value = quantity_asset * entry_price
        if notional_value < self.cfg.min_notional_usdt:
            logger.warning(
                f"⚠️ Order rejected: Notional value {notional_value:.2f} < "
                f"{self.cfg.min_notional_usdt} USDT minimum"
            )
            return 0.0
        
        logger.info(
            f"✓ Position approved: {quantity_asset:.6f} units @ ${entry_price:.2f} "
            f"(notional: ${notional_value:.2f}, SL: ${stop_loss_price:.2f})"
        )
        
        return quantity_asset

    def validate_volatility(
        self,
        df: pd.DataFrame,
        threshold_atr_pct: Optional[float] = None
    ) -> bool:
        """
        Prevent trading if market is TOO crazy (e.g., flash crash).
        
        Args:
            df: DataFrame with OHLC data
            threshold_atr_pct: Maximum acceptable volatility (defaults to config value)
            
        Returns:
            True if volatility is acceptable, False otherwise
        """
        if df.empty or len(df) < 1:
            logger.warning("Cannot validate volatility: insufficient data")
            return False
        
        threshold = threshold_atr_pct or self.cfg.max_volatility_threshold
        
        # Calculate simple ATR percentage of last candle
        last_close = df['close'].iloc[-1]
        last_high = df['high'].iloc[-1]
        last_low = df['low'].iloc[-1]
        
        tr_pct = (last_high - last_low) / last_close
        
        if tr_pct > threshold:
            logger.warning(
                f"⚠️ Market too volatile ({tr_pct:.2%} > {threshold:.2%}). "
                f"Operation cancelled for safety."
            )
            return False
        
        logger.debug(f"Volatility check passed: {tr_pct:.2%}")
        return True

    def calculate_dynamic_stop_loss(
        self,
        df: pd.DataFrame,
        current_price: float,
        atr_period: Optional[int] = None,
        multiplier: Optional[float] = None,
        side: str = 'long'
    ) -> float:
        """
        Calculate dynamic stop loss using ATR.
        
        In crypto, 1.5 ATR is sometimes just noise. 2.0 or 2.5 is safer
        to avoid 'stop hunts'.
        
        Args:
            df: DataFrame with OHLC data (must have 'high', 'low', 'close')
            current_price: Current market price
            atr_period: ATR period (defaults to config)
            multiplier: ATR multiplier (defaults to config)
            side: 'long' or 'short'
            
        Returns:
            Stop loss price
        """
        atr_period = atr_period or self.cfg.default_atr_period
        multiplier = multiplier or self.cfg.default_atr_multiplier
        
        # Fallback if insufficient data
        if len(df) < atr_period:
            fallback_pct = 0.95 if side == 'long' else 1.05
            stop_loss = current_price * fallback_pct
            logger.warning(
                f"Insufficient data for ATR ({len(df)} < {atr_period}). "
                f"Using {abs(1-fallback_pct):.1%} fallback SL: ${stop_loss:.2f}"
            )
            return stop_loss

        # Calculate True Range
        df = df.copy()  # Avoid SettingWithCopyWarning
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        
        # Calculate ATR
        atr = df['tr'].rolling(window=atr_period).mean().iloc[-1]
        
        if pd.isna(atr) or atr <= 0:
            fallback_pct = 0.95 if side == 'long' else 1.05
            stop_loss = current_price * fallback_pct
            logger.warning(
                f"Invalid ATR value ({atr}). Using fallback SL: ${stop_loss:.2f}"
            )
            return stop_loss
        
        # Calculate stop loss
        if side == 'long':
            stop_loss = current_price - (atr * multiplier)
        else:
            stop_loss = current_price + (atr * multiplier)
        
        logger.info(
            f"ATR-based SL calculated: ${stop_loss:.2f} "
            f"(ATR: ${atr:.2f}, multiplier: {multiplier}x, side: {side})"
        )
        
        return stop_loss


# Backward compatibility: Keep old RiskManager as alias
class RiskManager(ProfessionalRiskManager):
    """Deprecated: Use ProfessionalRiskManager instead."""
    
    def __init__(self, leverage: int = 1, strategy_win_rate: float = 0.55, profit_loss_ratio: float = 1.5):
        """
        Old interface for backward compatibility.
        
        DEPRECATED: This interface is maintained for backward compatibility only.
        Use ProfessionalRiskManager with RiskConfig instead.
        """
        logger.warning(
            "RiskManager with old interface is deprecated. "
            "Use ProfessionalRiskManager with RiskConfig instead."
        )
        
        config = RiskConfig()
        super().__init__(config)
        
        self.leverage = leverage
        self.win_rate = strategy_win_rate
        self.ratio = profit_loss_ratio
    
    def calculate_kelly_size(self, balance: float) -> float:
        """
        Old Kelly calculation (returns USDT amount, not position size).
        
        DEPRECATED: Use calculate_safe_size() instead.
        """
        logger.warning("calculate_kelly_size() is deprecated. Use calculate_safe_size() instead.")
        
        kelly_fraction = self.win_rate - ((1 - self.win_rate) / self.ratio)
        kelly_fraction = max(0, kelly_fraction)
        
        # Safe Kelly: typically use Half-Kelly to avoid ruin
        safe_allocation = (kelly_fraction * 0.5) * balance * self.leverage
        return safe_allocation
