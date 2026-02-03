"""
Trading Engine - Main orchestrator for automated trading

Integrates:
- Market data from ZeroMQ
- Multiple trading strategies
- Professional risk management
- Position tracking
- Order execution via testnet

This is the CORE of the trading system.
"""
import asyncio
import zmq
import zmq.asyncio
import msgpack
import pandas as pd
import logging
from datetime import datetime
from typing import Optional
import os

from core.config import settings
from apps.executor.testnet_connector import TestnetConnector
from apps.executor.account_manager import AccountManager
from apps.executor.risk_manager import ProfessionalRiskManager, RiskConfig
from apps.executor.strategies import (
    StrategyManager,
    MomentumStrategy,
    MeanReversionStrategy
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TradingEngine:
    """
    Main trading engine that orchestrates the entire trading system.
    
    Workflow:
    1. Subscribe to market data (ZeroMQ)
    2. Fetch OHLCV candles
    3. Run strategies on candles
    4. If signal generated -> validate with risk manager
    5. Check account manager (daily limits, positions)
    6. Execute trade via testnet connector
    7. Monitor positions and update P&L
    """
    
    def __init__(
        self,
        symbol: str = None,
        timeframe: str = None,
        use_testnet: bool = True,
        dry_run: bool = False
    ):
        """
        Initialize trading engine.
        
        Args:
            symbol: Trading symbol (defaults to config)
            timeframe: Candle timeframe (defaults to config)
            use_testnet: Use testnet or production
            dry_run: If True, don't execute real orders
        """
        self.symbol = symbol or settings.DEFAULT_SYMBOL
        self.timeframe = timeframe or settings.DEFAULT_TIMEFRAME
        self.use_testnet = use_testnet
        self.dry_run = dry_run
        
        # Initialize components
        self.connector = TestnetConnector(use_testnet=use_testnet)
        self.account_manager = AccountManager()
        
        # Risk manager
        risk_config = RiskConfig(
            max_account_risk_per_trade=settings.MAX_RISK_PER_TRADE,
            max_daily_drawdown=settings.MAX_DAILY_DRAWDOWN,
            kelly_fraction=settings.KELLY_FRACTION
        )
        self.risk_manager = ProfessionalRiskManager(risk_config)
        
        # Strategy manager
        self.strategy_manager = StrategyManager(combination_method='consensus')
        self._setup_strategies()
        
        # Market data
        self.latest_candles: Optional[pd.DataFrame] = None
        self.last_candle_time = None
        
        # Control
        self.running = False
        
        logger.info(f"Trading Engine initialized for {self.symbol} ({self.timeframe})")
        logger.info(f"Testnet: {use_testnet} | Dry Run: {dry_run}")
    
    def _setup_strategies(self):
        """Register trading strategies."""
        # Momentum strategy
        momentum = MomentumStrategy(
            rsi_period=14,
            fast_ma_period=10,
            slow_ma_period=30
        )
        self.strategy_manager.register_strategy(momentum)
        
        # Mean reversion strategy
        mean_reversion = MeanReversionStrategy(
            bb_period=20,
            bb_std=2.0,
            rsi_period=14
        )
        self.strategy_manager.register_strategy(mean_reversion)
        
        logger.info(f"Registered {len(self.strategy_manager.strategies)} strategies")
    
    async def start(self):
        """Start the trading engine."""
        logger.info("="*60)
        logger.info("TRADING ENGINE STARTING")
        logger.info("="*60)
        
        # Initialize connector
        await self.connector.initialize()
        
        # Get initial balance
        balance = await self.connector.get_usdt_balance()
        self.account_manager.current_balance = balance
        logger.info(f"Initial balance: ${balance:.2f}")
        
        # Get initial candles
        await self._update_candles()
        
        self.running = True
        
        logger.info("="*60)
        logger.info("TRADING ENGINE RUNNING")
        logger.info("Press Ctrl+C to stop")
        logger.info("="*60)
        
        try:
            # Main loop
            await self._trading_loop()
        except KeyboardInterrupt:
            logger.info("\nShutdown requested...")
        finally:
            await self.stop()
    
    async def _trading_loop(self):
        """Main trading loop."""
        while self.running:
            try:
                # Update candles
                await self._update_candles()
                
                # Update daily P&L for risk manager
                daily_pnl = self.account_manager.get_daily_pnl()
                self.risk_manager.update_daily_pnl(daily_pnl)
                
                # Check for existing position
                existing_position = self.account_manager.get_position(self.symbol)
                
                if existing_position:
                    # Monitor existing position
                    await self._monitor_position(existing_position)
                else:
                    # Look for new trading opportunities
                    await self._check_for_signals()
                
                # Wait before next iteration
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    async def _update_candles(self):
        """Fetch latest OHLCV candles."""
        try:
            required_candles = self.strategy_manager.get_required_candles()
            
            ohlcv = await self.connector.fetch_ohlcv(
                self.symbol,
                timeframe=self.timeframe,
                limit=required_candles + 10  # Extra buffer
            )
            
            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            self.latest_candles = df
            self.last_candle_time = df['timestamp'].iloc[-1]
            
            logger.debug(f"Updated candles: {len(df)} candles, last at {self.last_candle_time}")
            
        except Exception as e:
            logger.error(f"Error updating candles: {e}", exc_info=True)
    
    async def _check_for_signals(self):
        """Check all strategies for trading signals."""
        if self.latest_candles is None or len(self.latest_candles) == 0:
            return
        
        # Get combined signal from all strategies
        signal = await self.strategy_manager.get_combined_signal(
            self.latest_candles,
            min_confidence=0.6
        )
        
        if signal and signal.is_actionable():
            logger.info(
                f"🔔 Signal received: {signal.signal_type.value.upper()} "
                f"(confidence: {signal.confidence:.2%})"
            )
            
            # Execute trade
            await self._execute_trade(signal)
    
    async def _execute_trade(self, signal):
        """
        Execute a trade based on signal.
        
        Workflow:
        1. Validate with risk manager (position sizing, stop loss)
        2. Check volatility
        3. Place order (if not dry run)
        4. Track position
        """
        try:
            # Get current price
            ticker = await self.connector.get_ticker(self.symbol)
            current_price = ticker['last']
            
            # Validate volatility
            is_safe = self.risk_manager.validate_volatility(self.latest_candles)
            if not is_safe:
                logger.warning("Trade blocked: Market too volatile")
                return
            
            # Calculate stop loss if not provided
            if not signal.stop_loss:
                side = 'long' if signal.signal_type.value == 'buy' else 'short'
                signal.stop_loss = self.risk_manager.calculate_dynamic_stop_loss(
                    self.latest_candles,
                    current_price,
                    side=side
                )
            
            # Calculate position size
            balance = await self.connector.get_usdt_balance()
            
            # Estimate win rate and reward ratio from strategy metadata
            # (In real system, these would come from backtesting)
            win_rate = 0.55  # 55% default
            reward_ratio = 2.0  # 2:1 default
            
            position_size = self.risk_manager.calculate_safe_size(
                balance=balance,
                entry_price=current_price,
                stop_loss_price=signal.stop_loss,
                win_rate=win_rate,
                reward_ratio=reward_ratio
            )
            
            if position_size == 0:
                logger.warning("Trade blocked by risk manager (position size = 0)")
                return
            
            logger.info(
                f"✓ Trade approved: {position_size:.6f} {self.symbol} @ ${current_price:.2f}"
            )
            
            # Execute order (if not dry run)
            if self.dry_run:
                logger.info(
                    f"[DRY RUN] Would place {signal.signal_type.value.upper()} order: "
                    f"{position_size:.6f} {self.symbol} @ ${current_price:.2f}"
                )
            else:
                # Place market order
                side = 'buy' if signal.signal_type.value == 'buy' else 'sell'
                order = await self.connector.create_market_order(
                    symbol=self.symbol,
                    side=side,
                    amount=position_size
                )
                
                logger.info(f"✓ Order executed: {order.get('id')}")
                
                # Place stop loss order
                sl_side = 'sell' if side == 'buy' else 'buy'
                sl_order = await self.connector.create_stop_loss(
                    symbol=self.symbol,
                    side=sl_side,
                    amount=position_size,
                    stop_price=signal.stop_loss
                )
                
                logger.info(f"✓ Stop loss placed: ${signal.stop_loss:.2f}")
            
            # Track position in account manager
            position_side = 'long' if signal.signal_type.value == 'buy' else 'short'
            self.account_manager.open_position(
                symbol=self.symbol,
                side=position_side,
                entry_price=current_price,
                size=position_size,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit
            )
            
            logger.info(f"✓ Position tracked in account manager")
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}", exc_info=True)
    
    async def _monitor_position(self, position):
        """Monitor an open position."""
        try:
            # Get current price
            ticker = await self.connector.get_ticker(self.symbol)
            current_price = ticker['last']
            
            # Update unrealized P&L
            self.account_manager.update_position_pnl(self.symbol, current_price)
            
            logger.debug(
                f"Position: {position.side.value.upper()} {position.size:.6f} @ ${position.entry_price:.2f} | "
                f"Current: ${current_price:.2f} | P&L: ${position.unrealized_pnl:+.2f}"
            )
            
            # Check if take profit hit
            if position.take_profit:
                if position.side.value == 'long' and current_price >= position.take_profit:
                    logger.info(f"🎯 Take profit hit at ${current_price:.2f}")
                    await self._close_position("Take profit reached")
                elif position.side.value == 'short' and current_price <= position.take_profit:
                    logger.info(f"🎯 Take profit hit at ${current_price:.2f}")
                    await self._close_position("Take profit reached")
            
        except Exception as e:
            logger.error(f"Error monitoring position: {e}", exc_info=True)
    
    async def _close_position(self, reason: str):
        """Close the current position."""
        try:
            logger.info(f"Closing position: {reason}")
            
            # Get current price
            ticker = await self.connector.get_ticker(self.symbol)
            exit_price = ticker['last']
            
            # Close on exchange (if not dry run)
            if not self.dry_run:
                order = await self.connector.close_position(self.symbol)
                logger.info(f"✓ Position closed on exchange: {order.get('id') if order else 'N/A'}")
            else:
                logger.info(f"[DRY RUN] Would close position at ${exit_price:.2f}")
            
            # Update account manager
            closed_trade = self.account_manager.close_position(self.symbol, exit_price)
            
            if closed_trade:
                logger.info(
                    f"✓ Trade closed: P&L ${closed_trade.realized_pnl:+.2f} "
                    f"({closed_trade.realized_pnl/closed_trade.entry_price/closed_trade.size*100:+.2f}%)"
                )
                
                # Print stats
                self.account_manager.print_stats()
            
        except Exception as e:
            logger.error(f"Error closing position: {e}", exc_info=True)
    
    async def stop(self):
        """Stop the trading engine."""
        logger.info("Stopping trading engine...")
        self.running = False
        
        # Close any open positions
        if self.symbol in self.account_manager.open_positions:
            await self._close_position("Shutdown")
        
        # Close connector
        await self.connector.close()
        
        # Print final statistics
        logger.info("\n" + "="*60)
        logger.info("FINAL STATISTICS")
        logger.info("="*60)
        self.account_manager.print_stats()
        self.strategy_manager.print_stats()
        logger.info("="*60)
        logger.info("Trading Engine stopped")


async def main():
    """Main entry point."""
    # Get configuration from environment
    dry_run = os.getenv('DRY_RUN', 'true').lower() == 'true'
    use_testnet = os.getenv('USE_TESTNET', 'true').lower() == 'true'
    
    # Create and start trading engine
    engine = TradingEngine(
        symbol=settings.DEFAULT_SYMBOL,
        timeframe=settings.DEFAULT_TIMEFRAME,
        use_testnet=use_testnet,
        dry_run=dry_run
    )
    
    await engine.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown complete")
