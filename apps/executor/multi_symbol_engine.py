"""
Multi-Symbol Trading Engine
Main orchestrator for portfolio-based automated trading

Manages trading across multiple assets simultaneously with:
- Symbol-specific strategies (factory pattern)
- Portfolio-level risk management
- Event-driven architecture (on_tick per symbol)
- State recovery from database

This is the CORE of the multi-asset trading system.
"""
import asyncio
import zmq
import zmq.asyncio
import msgpack
import pandas as pd
import logging
from datetime import datetime
from typing import Optional, Dict, List
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
from apps.executor.profiles import get_profile
from config.safe_list import get_active_symbols, get_symbol_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console
        logging.FileHandler('logs/trading_engine.log')  # File
    ]
)
logger = logging.getLogger(__name__)


class MultiSymbolEngine:
    """
    Multi-Symbol Trading Engine
    
    Manages multiple trading pairs simultaneously:
    - Each symbol has independent state (candles, strategy)
    - Portfolio-level risk management (global exposure control)
    - Event-driven: processes ticks as they arrive
    """
    
    def __init__(
        self,
        symbols: List[str] = None,
        use_testnet: bool = True,
        dry_run: bool = False
    ):
        """
        Initialize multi-symbol trading engine.
        
        Args:
            symbols: List of symbols to trade (defaults to safe_list active)
            use_testnet: Use testnet or production
            dry_run: If True, don't execute real orders
        """
        self.symbols = symbols or get_active_symbols()
        self.use_testnet = use_testnet
        self.dry_run = dry_run
        
        logger.info("=" * 60)
        logger.info("MULTI-SYMBOL TRADING ENGINE")
        logger.info("=" * 60)
        logger.info(f"Symbols: {self.symbols}")
        logger.info(f"Dry Run: {dry_run}")
        logger.info("=" * 60)

        print("Dry Run: ", dry_run)
        
        # Load trading profile
        self.profile = get_profile(settings.TRADING_PROFILE)
        logger.info(f"Trading Profile: {self.profile.name}")
        logger.info(f"Combination Method: {self.profile.combination_method}")
        logger.info(f"Min Confidence: {self.profile.min_confidence:.0%}")
        logger.info(f"Max Risk per Trade: {self.profile.max_risk_per_trade:.1%}")
        
        # Global components
        self.connector = TestnetConnector(use_testnet=use_testnet)
        self.account_manager = AccountManager()
        
        # Portfolio-level risk manager
        risk_config = RiskConfig(
            max_account_risk_per_trade=self.profile.max_risk_per_trade,
            max_daily_drawdown=settings.MAX_DAILY_DRAWDOWN,
            kelly_fraction=settings.KELLY_FRACTION
        )
        self.risk_manager = ProfessionalRiskManager(risk_config)
        
        # State per symbol (dictionary-based)
        self.strategies: Dict[str, StrategyManager] = {}
        self.candles: Dict[str, pd.DataFrame] = {}
        self.latest_candles: Dict[str, pd.DataFrame] = {}
        self.last_candle_time: Dict[str, datetime] = {}
        
        # Initialize strategies for each symbol (Factory Pattern)
        self._initialize_strategies()
        
        # ZeroMQ Subscriber
        self.zmq_context = zmq.asyncio.Context()
        self.zmq_socket = self.zmq_context.socket(zmq.SUB)
        
        # Control
        self.running = False
        self.tick_count = 0  # Contador para debugging
        
    def _initialize_strategies(self):
        """
        Factory Pattern: Create strategies based on safe_list configuration.
        
        Each symbol gets strategy instances according to its tier and configuration.
        """
        logger.info("\n" + "=" * 60)
        logger.info("INITIALIZING STRATEGIES")
        logger.info("=" * 60)
        
        for symbol in self.symbols:
            config = get_symbol_config(symbol)
            
            if not config:
                logger.warning(f"⚠️ No config found for {symbol}, skipping")
                continue
            
            # Create strategy manager for this symbol
            strategy_manager = StrategyManager(
                combination_method=self.profile.combination_method
            )
            
            # Determine which strategies to add based on symbol's config
            strategy_type = config.get('strategy', 'mean_reversion')
            params = config.get('params', {})
            
            if strategy_type == 'momentum':
                # Create Momentum strategy with symbol-specific params
                momentum = MomentumStrategy(
                    name=f"Momentum-{symbol}",
                    rsi_period=params.get('rsi_period', 9),
                    fast_ma_period=params.get('ma_fast', 8),
                    slow_ma_period=params.get('ma_slow', 21)
                )
                strategy_manager.register_strategy(momentum)
                logger.info(f"✓ {symbol}: Momentum (RSI={params.get('rsi_period', 9)})")
                
            elif strategy_type == 'mean_reversion':
                # Create Mean Reversion strategy with symbol-specific params
                mean_rev = MeanReversionStrategy(
                    name=f"MeanRev-{symbol}",
                    rsi_period=params.get('rsi_period', 14),
                    bb_period=params.get('bb_period', 20),
                    bb_std=params.get('bb_std', 2.0)
                )
                strategy_manager.register_strategy(mean_rev)
                logger.info(f"✓ {symbol}: MeanReversion (BB_std={params.get('bb_std', 2.0)})")
            
            # Store strategy manager for this symbol
            self.strategies[symbol] = strategy_manager
            
            # Initialize state
            self.candles[symbol] = pd.DataFrame()
            self.latest_candles[symbol] = None
            self.last_candle_time[symbol] = None
        
        logger.info("=" * 60 + "\n")
    
    async def start(self):
        """Start the multi-symbol trading engine."""
        logger.info("Starting Multi-Symbol Trading Engine...")
        
        # Connect to ZeroMQ feed
        zmq_url = settings.ZMQ_FEED_HANDLER_URL
        self.zmq_socket.connect(zmq_url)
        
        # Subscribe to ALL symbols (empty filter = receive all topics)
        self.zmq_socket.setsockopt(zmq.SUBSCRIBE, b'')
        logger.info(f"Subscribed to ZMQ feed: {zmq_url}")
        
        # Initialize connector
        await self.connector.initialize()
        logger.info("Testnet connector initialized")
        
        # Start main loop
        self.running = True
        await self._main_loop()
    
    async def _main_loop(self):
        """
        Main event loop: receive ticks and process per symbol.
        
        Event-driven architecture:
        - ZMQ publishes: [topic: 'BTC/USDT', data: {...}]
        - Engine receives and routes to on_tick(symbol, data)
        """
        logger.info("\n🚀 Trading Engine Running - Event-driven mode\n")
        
        try:
            while self.running:
                # Receive message with topic
                topic, msg = await self.zmq_socket.recv_multipart()
                symbol = topic.decode('utf-8')
                data = msgpack.unpackb(msg, raw=False)
                
                # Route to symbol-specific handler
                if symbol in self.symbols:
                    await self.on_tick(symbol, data)
                else:
                    logger.debug(f"Received tick for non-tracked symbol: {symbol}")
                    
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            await self.stop()
    
    async def on_tick(self, symbol: str, tick_data: Dict):
        """
        Handle incoming tick for specific symbol.
        
        Workflow per symbol:
        1. Update candles (OHLCV data)
        2. Run strategy
        3. Check for signal
        4. Portfolio risk check
        5. Execute trade
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            tick_data: Normalized ticker data from feed handler
        """
        try:
            # Incrementar contador
            self.tick_count += 1
            
            # Log cada 100 ticks para confirmar actividad
            if self.tick_count % 100 == 0:
                logger.info(f"📊 Processed {self.tick_count} ticks total")
            
            # Update candles for this symbol
            await self._update_candles(symbol)
            
            # Check for signals
            if self.latest_candles[symbol] is not None:
                await self._check_signal(symbol)
                
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}", exc_info=True)
    
    async def _update_candles(self, symbol: str):
        """
        Fetch and update OHLCV candles for specific symbol.
        
        Args:
            symbol: Trading pair
        """
        try:
            # Determine required candles based on strategy
            required_candles = 100  # Buffer for indicators
            
            # Fetch OHLCV
            ohlcv = await self.connector.fetch_ohlcv(
                symbol=symbol,
                timeframe=settings.DEFAULT_TIMEFRAME,
                limit=required_candles + 10
            )
            
            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            self.latest_candles[symbol] = df
            self.last_candle_time[symbol] = df['timestamp'].iloc[-1]
            
            # Cambiar a INFO para ver actividad
            logger.info(f"{symbol}: Updated {len(df)} candles, last at {self.last_candle_time[symbol]}")
            
        except Exception as e:
            logger.error(f"Error updating candles for {symbol}: {e}", exc_info=True)
    
    async def _check_signal(self, symbol: str):
        """
        Check for trading signal on specific symbol.
        
        Args:
            symbol: Trading pair
        """
        try:
            candles = self.latest_candles[symbol]
            strategy_manager = self.strategies[symbol]
            
            # Get combined signal
            signal = await strategy_manager.get_combined_signal(
                candles,
                min_confidence=self.profile.min_confidence
            )
            
            if signal and signal.is_actionable():
                logger.info(
                    f"🔔 {symbol} - Signal: {signal.signal_type.value.upper()} "
                    f"(confidence: {signal.confidence:.2%})"
                )
                
                # Execute trade (with portfolio risk check inside)
                await self._execute_trade(symbol, signal)
            else:
                # Log when NO signal (para debugging)
                if signal:
                    logger.debug(
                        f"{symbol}: Signal below threshold "
                        f"({signal.confidence:.2%} < {self.profile.min_confidence:.2%})"
                    )
                else:
                    logger.debug(f"{symbol}: No signal generated")
                
        except Exception as e:
            logger.error(f"Error checking signal for {symbol}: {e}", exc_info=True)
    
    async def _execute_trade(self, symbol: str, signal):
        """
        Execute trade for specific symbol.
        
        Includes portfolio-level risk checks.
        
        Args:
            symbol: Trading pair
            signal: Trading signal
        """
        try:
            # Get current price
            ticker = await self.connector.get_ticker(symbol)
            if not ticker or 'last' not in ticker:
                logger.error(f"{symbol}: Unable to get current price")
                return
            
            current_price = ticker['last']
            
            # Get account balance
            balance_dict = await self.connector.get_balance()
            
            # Extract USDT balance (get_balance returns dict)
            if isinstance(balance_dict, dict):
                balance = balance_dict.get('USDT', {}).get('free', 0)
            else:
                balance = balance_dict  # Fallback if it's already a number
                
            if not balance or balance <= 0:
                logger.error(f"{symbol}: Invalid balance: {balance}")
                return
            
            # Calculate stop loss usando ATR
            stop_loss = self.risk_manager.calculate_dynamic_stop_loss(
                df=self.latest_candles[symbol],
                current_price=current_price,
                side='long' if signal.signal_type.value == 'buy' else 'short'
            )
            
            # Calculate safe position size
            win_rate = 0.55  # Conservative estimate
            reward_ratio = 2.0  # 1:2 risk/reward
            
            quantity = self.risk_manager.calculate_safe_size(
                balance=balance,
                entry_price=current_price,
                stop_loss_price=stop_loss,
                win_rate=win_rate,
                reward_ratio=reward_ratio
            )
            
            if quantity <= 0:
                logger.warning(f"❌ {symbol} - Position size too small: {quantity}")
                return
            
            # Get safe_list config for position limits
            config = get_symbol_config(symbol)
            max_position_usd = config.get('max_position_size_usd', 1000)
            
            # Respect max position size
            position_value_usd = quantity * current_price
            if position_value_usd > max_position_usd:
                quantity = max_position_usd / current_price
                position_value_usd = max_position_usd
            
            # Log trade details
            logger.info(f"\n{'='*60}")
            logger.info(f"TRADE EXECUTION: {symbol}")
            logger.info(f"{'='*60}")
            logger.info(f"Signal: {signal.signal_type.value.upper()}")
            logger.info(f"Confidence: {signal.confidence:.2%}")
            logger.info(f"Current Price: ${current_price:,.2f}")
            logger.info(f"Position Size: ${position_size_usd:,.2f} ({quantity:.6f} units)")
            logger.info(f"Stop Loss: ${validation['stop_loss']:,.2f}")
            logger.info(f"Risk/Reward: 1:{validation['risk_reward_ratio']:.2f}")
            logger.info(f"Account Balance: ${balance:,.2f}")
            
            if self.dry_run:
                logger.info(f"🔵 DRY RUN MODE - Trade NOT executed")
                logger.info(f"{'='*60}\n")
                return
            
            # Execute order
            order_result = await self.connector.place_order(
                symbol=symbol,
                side=signal.signal_type.value,
                quantity=quantity,
                price=current_price,
                order_type='market'
            )
            
            if order_result:
                logger.info(f"✅ {symbol} - Order placed successfully")
                logger.info(f"Order ID: {order_result.get('id', 'N/A')}")
                
                # Track position
                self.account_manager.add_position({
                    'symbol': symbol,
                    'side': signal.signal_type.value,
                    'entry_price': current_price,
                    'quantity': quantity,
                    'stop_loss': validation['stop_loss'],
                    'timestamp': datetime.now()
                })
            else:
                logger.error(f"❌ {symbol} - Order failed")
            
            logger.info(f"{'='*60}\n")
                
        except Exception as e:
            logger.error(f"Error executing trade for {symbol}: {e}", exc_info=True)
    
    async def stop(self):
        """Stop the engine and cleanup resources."""
        logger.info("Stopping Multi-Symbol Trading Engine...")
        self.running = False
        
        await self.connector.close()
        self.zmq_socket.close()
        self.zmq_context.term()
        
        logger.info("Engine stopped")


async def main():
    """Main entry point."""
    # Get symbols from safe_list
    engine = MultiSymbolEngine(
        use_testnet=settings.USE_TESTNET,
        dry_run=settings.DRY_RUN
    )
    
    await engine.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Multi-Symbol Engine stopped by user")
