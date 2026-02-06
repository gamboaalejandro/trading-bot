"""
Strategy Manager - Manages multiple trading strategies
"""
from typing import List, Optional, Dict
import pandas as pd
import logging

from .base_strategy import BaseStrategy, Signal, SignalType

logger = logging.getLogger(__name__)


class StrategyManager:
    """
    Manages multiple trading strategies and combines their signals.
    
    Features:
    - Register multiple strategies
    - Get signals from all strategies
    - Combine signals (consensus, weighted voting, etc.)
    - Track strategy performance
    """
    
    def __init__(self, combination_method: str = 'consensus'):
        """
        Initialize strategy manager.
        
        Args:
            combination_method: How to combine signals ('consensus', 'first_match', 'highest_confidence')
        """
        self.strategies: List[BaseStrategy] = []
        self.combination_method = combination_method
        self.strategy_stats: Dict[str, Dict] = {}
    
    def register_strategy(self, strategy: BaseStrategy):
        """
        Register a trading strategy.
        
        Args:
            strategy: Strategy instance to register
        """
        self.strategies.append(strategy)
        self.strategy_stats[strategy.name] = {
            'signals_generated': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'hold_signals': 0
        }
        logger.info(f"Registered strategy: {strategy.name}")
    
    def get_required_candles(self) -> int:
        """Get maximum required candles across all strategies."""
        if not self.strategies:
            return 0
        return max(s.get_required_candles() for s in self.strategies)
    
    async def get_all_signals(self, df: pd.DataFrame) -> Dict[str, Optional[Signal]]:
        """
        Get signals from all registered strategies.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Dictionary mapping strategy name to signal
        """
        signals = {}
        
        for strategy in self.strategies:
            try:
                signal = await strategy.analyze(df)
                signals[strategy.name] = signal
                
                # Update stats
                if signal:
                    self.strategy_stats[strategy.name]['signals_generated'] += 1
                    
                    if signal.signal_type == SignalType.BUY:
                        self.strategy_stats[strategy.name]['buy_signals'] += 1
                    elif signal.signal_type == SignalType.SELL:
                        self.strategy_stats[strategy.name]['sell_signals'] += 1
                    else:
                        self.strategy_stats[strategy.name]['hold_signals'] += 1
                        
            except Exception as e:
                logger.error(f"Error getting signal from {strategy.name}: {e}", exc_info=True)
                signals[strategy.name] = None
        
        return signals
    
    async def get_combined_signal(
        self,
        df: pd.DataFrame,
        min_confidence: float = 0.6
    ) -> Optional[Signal]:
        """
        Get combined signal from all strategies.
        
        Args:
            df: DataFrame with OHLCV data
            min_confidence: Minimum confidence threshold
            
        Returns:
            Combined signal or None
        """
        all_signals = await self.get_all_signals(df)
        
        # Filter out None and HOLD signals
        actionable_signals = {
            name: sig for name, sig in all_signals.items()
            if sig and sig.signal_type != SignalType.HOLD
        }
        
        if not actionable_signals:
            logger.debug("No actionable signals from any strategy")
            return None
        
        # Apply combination method
        if self.combination_method == 'consensus':
            return self._consensus_signal(actionable_signals, min_confidence)
        elif self.combination_method == 'majority':
            return self._majority_signal(actionable_signals, min_confidence)
        elif self.combination_method == 'weighted':
            return self._weighted_signal(actionable_signals, min_confidence)
        elif self.combination_method == 'any':
            return self._any_signal(actionable_signals, min_confidence)
        elif self.combination_method == 'first_match':
            return self._first_match_signal(actionable_signals, min_confidence)
        elif self.combination_method == 'highest_confidence':
            return self._highest_confidence_signal(actionable_signals, min_confidence)
        else:
            logger.warning(f"Unknown combination method: {self.combination_method}")
            return None
    
    def _consensus_signal(
        self,
        signals: Dict[str, Signal],
        min_confidence: float
    ) -> Optional[Signal]:
        """
        Require consensus (majority) among strategies.
        
        All strategies must agree on direction (BUY or SELL).
        Returns averaged signal if consensus exists.
        """
        if not signals:
            return None
        
        # Count signal types
        buy_count = sum(
            1 for sig in signals.values()
            if sig.signal_type == SignalType.BUY and sig.confidence >= min_confidence
        )
        sell_count = sum(
            1 for sig in signals.values()
            if sig.signal_type == SignalType.SELL and sig.confidence >= min_confidence
        )
        
        total_signals = len(signals)
        
        # Require majority (> 50%)
        if buy_count > total_signals / 2:
            # Average BUY signals
            buy_signals = [
                sig for sig in signals.values()
                if sig.signal_type == SignalType.BUY and sig.confidence >= min_confidence
            ]
            return self._average_signals(buy_signals, 'buy')
            
        elif sell_count > total_signals / 2:
            # Average SELL signals
            sell_signals = [
                sig for sig in signals.values()
                if sig.signal_type == SignalType.SELL and sig.confidence >= min_confidence
            ]
            return self._average_signals(sell_signals, 'sell')
        
        logger.debug(
            f"No consensus: {buy_count} BUY, {sell_count} SELL "
            f"(need > {total_signals/2:.1f})"
        )
        return None
    
    def _first_match_signal(
        self,
        signals: Dict[str, Signal],
        min_confidence: float
    ) -> Optional[Signal]:
        """Return first signal that meets confidence threshold."""
        for sig in signals.values():
            if sig.confidence >= min_confidence:
                logger.debug(f"First match: {sig.signal_type.value} (confidence: {sig.confidence:.2%})")
                return sig
        
        return None
    
    def _highest_confidence_signal(
        self,
        signals: Dict[str, Signal],
        min_confidence: float
    ) -> Optional[Signal]:
        """Return signal with highest confidence."""
        valid_signals = [
            sig for sig in signals.values()
            if sig.confidence >= min_confidence
        ]
        
        if not valid_signals:
            return None
        
        best_signal = max(valid_signals, key=lambda s: s.confidence)
        logger.debug(
            f"Highest confidence: {best_signal.signal_type.value} "
            f"(confidence: {best_signal.confidence:.2%})"
        )
        
        return best_signal
    
    def _majority_signal(
        self,
        signals: Dict[str, Signal],
        min_confidence: float
    ) -> Optional[Signal]:
        """
        Require majority (>50%) of strategies to agree.
        Similar to consensus but more lenient.
        """
        if not signals:
            return None
        
        # Count valid signals
        buy_signals = [
            sig for sig in signals.values()
            if sig.signal_type == SignalType.BUY and sig.confidence >= min_confidence
        ]
        sell_signals = [
            sig for sig in signals.values()
            if sig.signal_type == SignalType.SELL and sig.confidence >= min_confidence
        ]
        
        total_strategies = len(signals)
        threshold = total_strategies / 2  # >50%
        
        if len(buy_signals) > threshold:
            logger.debug(f"Majority BUY: {len(buy_signals)}/{total_strategies} strategies")
            return self._average_signals(buy_signals, 'buy')
        elif len(sell_signals) > threshold:
            logger.debug(f"Majority SELL: {len(sell_signals)}/{total_strategies} strategies")
            return self._average_signals(sell_signals, 'sell')
        
        logger.debug(
            f"No majority: {len(buy_signals)} BUY, {len(sell_signals)} SELL "
            f"(need > {threshold:.1f})"
        )
        return None
    
    def _weighted_signal(
        self,
        signals: Dict[str, Signal],
        min_confidence: float
    ) -> Optional[Signal]:
        """
        Weight signals by their confidence scores.
        Returns strongest overall direction.
        """
        if not signals:
            return None
        
        # Calculate weighted scores
        buy_weight = sum(
            sig.confidence
            for sig in signals.values()
            if sig.signal_type == SignalType.BUY and sig.confidence >= min_confidence
        )
        sell_weight = sum(
            sig.confidence
            for sig in signals.values()
            if sig.signal_type == SignalType.SELL and sig.confidence >= min_confidence
        )
        
        # Require significant difference (>0.3)
        weight_diff = abs(buy_weight - sell_weight)
        if weight_diff < 0.3:
            logger.debug(f"Weights too close: BUY={buy_weight:.2f}, SELL={sell_weight:.2f}")
            return None
        
        if buy_weight > sell_weight:
            buy_signals = [
                sig for sig in signals.values()
                if sig.signal_type == SignalType.BUY and sig.confidence >= min_confidence
            ]
            logger.debug(f"Weighted BUY wins: {buy_weight:.2f} vs {sell_weight:.2f}")
            return self._average_signals(buy_signals, 'buy')
        else:
            sell_signals = [
                sig for sig in signals.values()
                if sig.signal_type == SignalType.SELL and sig.confidence >= min_confidence
            ]
            logger.debug(f"Weighted SELL wins: {sell_weight:.2f} vs {buy_weight:.2f}")
            return self._average_signals(sell_signals, 'sell')
    
    def _any_signal(
        self,
        signals: Dict[str, Signal],
        min_confidence: float
    ) -> Optional[Signal]:
        """
        Accept any signal above confidence threshold.
        Returns highest confidence signal.
        """
        valid_signals = [
            sig for sig in signals.values()
            if sig.confidence >= min_confidence
        ]
        
        if not valid_signals:
            return None
        
        # Return highest confidence
        best_signal = max(valid_signals, key=lambda s: s.confidence)
        logger.debug(
            f"ANY method: {best_signal.signal_type.value} "
            f"(confidence: {best_signal.confidence:.2%})"
        )
        return best_signal
    
    def _average_signals(self, signals: List[Signal], signal_type: str) -> Signal:
        """Average multiple signals of the same type."""
        if not signals:
            raise ValueError("Cannot average empty signal list")
        
        # Average confidence
        avg_confidence = sum(s.confidence for s in signals) / len(signals)
        
        # Average prices
        avg_entry = sum(s.entry_price for s in signals) / len(signals)
        
        # Average stop loss (if all have it)
        stop_losses = [s.stop_loss for s in signals if s.stop_loss is not None]
        avg_stop_loss = sum(stop_losses) / len(stop_losses) if stop_losses else None
        
        # Average take profit (if all have it)
        take_profits = [s.take_profit for s in signals if s.take_profit is not None]
        avg_take_profit = sum(take_profits) / len(take_profits) if take_profits else None
        
        # Combine metadata
        combined_metadata = {
            'combined_from': [s.metadata.get('strategy', 'unknown') for s in signals],
            'individual_confidences': [s.confidence for s in signals]
        }
        
        return Signal(
            signal_type=SignalType.BUY if signal_type == 'buy' else SignalType.SELL,
            confidence=avg_confidence,
            entry_price=avg_entry,
            stop_loss=avg_stop_loss,
            take_profit=avg_take_profit,
            metadata=combined_metadata
        )
    
    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        return {
            'total_strategies': len(self.strategies),
            'combination_method': self.combination_method,
            'strategy_stats': self.strategy_stats
        }
    
    def print_stats(self):
        """Print formatted strategy statistics."""
        print("\n" + "="*60)
        print("STRATEGY MANAGER STATISTICS")
        print("="*60)
        print(f"Total Strategies: {len(self.strategies)}")
        print(f"Combination Method: {self.combination_method}")
        print("-"*60)
        
        for strategy_name, stats in self.strategy_stats.items():
            print(f"\n{strategy_name}:")
            print(f"  Total Signals: {stats['signals_generated']}")
            print(f"  BUY Signals:   {stats['buy_signals']}")
            print(f"  SELL Signals:  {stats['sell_signals']}")
            print(f"  HOLD Signals:  {stats['hold_signals']}")
        
        print("="*60)
