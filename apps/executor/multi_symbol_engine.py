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
import sys

# FIX for Windows: ZMQ requires SelectorEventLoop on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import zmq
import zmq.asyncio
import msgpack
import pandas as pd
import logging
from datetime import datetime
from typing import Optional, Dict, List
import os
import json
import time

from core.config import settings, resolve_settings_mode, ExecutionMode, TradingModeError
from core.binance_client import CancelReplaceError
from apps.executor.testnet_connector import TestnetConnector
from apps.executor.account_manager import AccountManager
from apps.executor.risk_manager import ProfessionalRiskManager, RiskConfig
from apps.executor.strategies import (
    StrategyManager,
    MomentumStrategy,
    MeanReversionStrategy
)
from apps.executor.profiles import get_profile
from apps.executor.pnl_logger import PnLLogger
from config.safe_list import get_active_symbols, get_symbol_config

os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console
        logging.FileHandler('logs/trading_engine.log')  # File
    ]
)
logger = logging.getLogger(__name__)

STATE_FILE = os.getenv('ENGINE_STATE_FILE', 'state/open_positions.json')
EMA_TREND_PERIOD = 200  # Trend filter in StrategyManager
CANDLE_BUFFER = 50      # Extra candles so rolling indicators are warmed up

# Exchange stop management: a failed stop placement/move is retried after
# each delay (seconds). The longest a position can stay without an exchange
# stop in the cancel-replace path is bounded by sum(delays) + request time,
# which must stay under MAX_UNPROTECTED_SECONDS.
STOP_RETRY_DELAYS = (0.5, 1.0, 2.0)
MAX_UNPROTECTED_SECONDS = 10.0
STOP_REARM_INTERVAL_SECONDS = 30.0  # monitor loop re-arms unprotected positions
BINANCE_UNKNOWN_ORDER = -2011


def timeframe_to_seconds(timeframe: str) -> int:
    """Convert a Binance interval ('1m', '4h', '1d', '1w') to seconds."""
    units = {'m': 60, 'h': 3600, 'd': 86400, 'w': 604800}
    return int(timeframe[:-1]) * units[timeframe[-1]]


def base_asset(symbol: str) -> str:
    """'BTC/USDT' -> 'BTC'."""
    return symbol.split('/')[0]


def _same_price(exchange_price, target: float, rel_tol: float = 1e-4) -> bool:
    """True if an exchange price (tick-rounded string) matches target."""
    try:
        return abs(float(exchange_price) - target) <= rel_tol * max(abs(target), 1e-12)
    except (TypeError, ValueError):
        return False


def fill_summary(order: Dict, base: str) -> tuple:
    """
    Summarize a Binance spot order response.

    Returns (net_base_quantity, average_price, fee_in_quote): quantity is
    executedQty minus commissions charged in the base asset, which are not
    in the wallet and cannot be sold back.
    """
    executed = float(order.get('executedQty', 0) or 0)
    quote = float(order.get('cummulativeQuoteQty', 0) or 0)
    avg_price = quote / executed if executed > 0 else 0.0
    base_fee = 0.0
    quote_fee = 0.0
    for fill in order.get('fills', []):
        commission = float(fill.get('commission', 0) or 0)
        if fill.get('commissionAsset') == base:
            base_fee += commission
        elif fill.get('commissionAsset') == 'USDT':
            quote_fee += commission
    return executed - base_fee, avg_price, quote_fee


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
        dry_run: bool = True
    ):
        """
        Initialize multi-symbol trading engine.
        
        Args:
            symbols: List of symbols to trade (defaults to safe_list active)
            use_testnet: Use testnet or production
            dry_run: If True (default), don't execute real orders
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
        
        # P&L tracking
        self.pnl_logger = PnLLogger()
        logger.info("[OK] P&L Logger initialized")
        
        # State per symbol (dictionary-based)
        self.strategies: Dict[str, StrategyManager] = {}
        self.candles: Dict[str, pd.DataFrame] = {}
        self.latest_candles: Dict[str, pd.DataFrame] = {}
        self.last_candle_time: Dict[str, datetime] = {}
        
        # Daily risk accounting (feeds the risk manager kill switch)
        self.trading_day = datetime.now().date()
        self.daily_realized_pnl = 0.0
        self.daily_trades: Dict[str, int] = {}

        # Position tracking (prevent duplicate trades)
        self.open_positions: Dict[str, Dict] = {}  # {symbol: {'side': 'buy', 'entry_price': 71000, 'timestamp': ...}}
        
        # Restore positions from a previous run (stops live on the exchange)
        self._load_state()

        # Initialize strategies for each symbol (Factory Pattern)
        self._initialize_strategies()
        
        # ZeroMQ Subscriber
        self.zmq_context = zmq.asyncio.Context()
        self.zmq_socket = self.zmq_context.socket(zmq.SUB)
        
        # Exchange stop bookkeeping and operator alerts
        self.stop_retry_delays = STOP_RETRY_DELAYS
        self.alerts: List[Dict[str, str]] = []
        self._last_stop_rearm: Dict[str, float] = {}

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
                logger.warning(f"️ No config found for {symbol}, skipping")
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
                logger.info(f"[OK] {symbol}: Momentum (RSI={params.get('rsi_period', 9)})")
                
            elif strategy_type == 'mean_reversion':
                # Create Mean Reversion strategy with symbol-specific params
                mean_rev = MeanReversionStrategy(
                    name=f"MeanRev-{symbol}",
                    rsi_period=params.get('rsi_period', 14),
                    bb_period=params.get('bb_period', 20),
                    bb_std=params.get('bb_std', 2.0)
                )
                strategy_manager.register_strategy(mean_rev)
                logger.info(f"[OK] {symbol}: MeanReversion (BB_std={params.get('bb_std', 2.0)})")
            
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
        
        # Start main loop and position monitoring in parallel
        self.running = True
        
        # Create monitoring task
        monitor_task = asyncio.create_task(self.monitor_open_positions())
        
        try:
            await self._main_loop()
        finally:
            # Cancel monitoring when main loop stops
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
    
    async def _main_loop(self):
        """
        Main event loop: receive ticks and process per symbol.
        
        Event-driven architecture:
        - ZMQ publishes: [topic: 'BTC/USDT', data: {...}]
        - Engine receives and routes to on_tick(symbol, data)
        """
        logger.info("\n[RUNNING] Trading Engine - Event-driven mode\n")
        
        last_message_time = asyncio.get_event_loop().time()
        heartbeat_timeout = 60  # seconds without data = warning
        
        try:
            while self.running:
                try:
                    # Receive message with timeout
                    topic, msg = await asyncio.wait_for(
                        self.zmq_socket.recv_multipart(),
                        timeout=heartbeat_timeout
                    )
                    
                    last_message_time = asyncio.get_event_loop().time()
                    
                    symbol = topic.decode('utf-8')
                    data = msgpack.unpackb(msg, raw=False)
                    
                    # Route to symbol-specific handler
                    if symbol in self.symbols:
                        await self.on_tick(symbol, data)
                    else:
                        logger.debug(f"Received tick for non-tracked symbol: {symbol}")
                
                except asyncio.TimeoutError:
                    # No data received for 60 seconds
                    logger.warning(f"️ No data received for {heartbeat_timeout}s - feed handler may be stuck")
                    logger.warning("Checking if feed handler is still alive...")
                    # Continue waiting (don't crash)
                    continue
                    
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
                logger.info(f"[STATS] Processed {self.tick_count} ticks total")
            
            # Update candles only when a new candle may have closed, and
            # evaluate strategies once per CLOSED candle (no repainting,
            # no REST call per tick)
            if not self._new_candle_due(symbol):
                return

            previous_candle = self.last_candle_time[symbol]
            await self._update_candles(symbol)

            if (
                self.latest_candles[symbol] is not None
                and self.last_candle_time[symbol] != previous_candle
            ):
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
            # Enough history for the slowest indicator AND the EMA 200 trend
            # filter (previously 110 candles: EMA200 and SOL's MA200 never ran)
            required_candles = max(
                self.strategies[symbol].get_required_candles(),
                EMA_TREND_PERIOD
            ) + CANDLE_BUFFER

            # Fetch OHLCV (+1 because the in-progress candle is dropped below)
            ohlcv = await self.connector.fetch_ohlcv(
                symbol=symbol,
                timeframe=settings.DEFAULT_TIMEFRAME,
                limit=min(required_candles + 1, 1000)
            )
            
            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            # Drop the candle that is still forming: signals on it repaint
            candle_seconds = timeframe_to_seconds(settings.DEFAULT_TIMEFRAME)
            now = pd.Timestamp.utcnow().tz_localize(None)
            if not df.empty and df['timestamp'].iloc[-1] + pd.Timedelta(seconds=candle_seconds) > now:
                df = df.iloc[:-1].reset_index(drop=True)
            
            self.latest_candles[symbol] = df
            self.last_candle_time[symbol] = df['timestamp'].iloc[-1]
            
            logger.debug(f"{symbol}: Updated {len(df)} candles, last at {self.last_candle_time[symbol]}")
            
        except Exception as e:
            logger.error(f"Error updating candles for {symbol}: {e}", exc_info=True)
    
    def _new_candle_due(self, symbol: str) -> bool:
        """True if no candles yet or the next candle should have closed."""
        last = self.last_candle_time[symbol]
        if last is None:
            return True
        candle_seconds = timeframe_to_seconds(settings.DEFAULT_TIMEFRAME)
        next_close = last + pd.Timedelta(seconds=2 * candle_seconds)
        return pd.Timestamp.utcnow().tz_localize(None) >= next_close

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
            
            # ENHANCED DEBUG LOGGING
            if signal:
                # Get latest candle data for debug info
                latest_close = candles['close'].iloc[-1]
                
                logger.debug(f"{symbol} - Signal Generated:")
                logger.debug(f"  Type: {signal.signal_type.value.upper()}")
                logger.debug(f"  Confidence: {signal.confidence:.2%}")
                logger.debug(f"  Price: ${latest_close:,.2f}")
                logger.debug(f"  Min Required: {self.profile.min_confidence:.2%}")
                
                # ========================================
                # SELL SIGNAL → CLOSE LONG POSITION
                # ========================================
                # In Spot mode, SELL signals should close LONG positions
                # NOT open SHORT positions (which are impossible in Spot)
                if signal.signal_type.value == 'sell' and symbol in self.open_positions:
                    existing_position = self.open_positions[symbol]
                    
                    # Only close if it's a LONG position
                    if existing_position['side'] == 'buy':
                        logger.info(
                            f"[EXIT SIGNAL] {symbol} - SELL signal received, closing LONG position "
                            f"(confidence: {signal.confidence:.2%})"
                        )
                        
                        # Get current price for exit
                        ticker = await self.connector.get_ticker(symbol)
                        if ticker and 'last' in ticker:
                            current_price = ticker['last']
                            await self.close_position(symbol, 'exit_signal', current_price)
                        return  # Exit after closing
                    else:
                        logger.debug(f"{symbol}: SELL signal but position is SHORT (already selling)")
                        return

                # Spot cannot open shorts: a SELL without an open LONG would
                # sell coins the bot never bought
                if signal.signal_type.value == 'sell':
                    logger.info(f"[SKIP] {symbol} - SELL signal without open position (spot is long-only)")
                    return
                
                # Check if actionable (for opening new positions)
                if signal.is_actionable():
                    logger.info(
                        f"[SIGNAL] {symbol} - Signal: {signal.signal_type.value.upper()} "
                        f"(confidence: {signal.confidence:.2%})"
                    )
                    
                    # Execute trade (with portfolio risk check inside)
                    await self._execute_trade(symbol, signal)
                else:
                    # Signal exists but below threshold
                    logger.info(
                        f"[SKIP] {symbol} - Signal FILTERED: {signal.signal_type.value.upper()} "
                        f"({signal.confidence:.2%} < {self.profile.min_confidence:.2%})"
                    )
            else:
                # No signal at all - log periodically for awareness
                # Log every 50th check to avoid spam
                if not hasattr(self, '_no_signal_count'):
                    self._no_signal_count = {}
                
                self._no_signal_count[symbol] = self._no_signal_count.get(symbol, 0) + 1
                
                if self._no_signal_count[symbol] % 50 == 0:
                    latest_close = candles['close'].iloc[-1]
                    logger.debug(
                        f"{symbol}: No signal after {self._no_signal_count[symbol]} checks "
                        f"(Price: ${latest_close:,.2f})"
                    )
                
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
            self._roll_trading_day()

            # Portfolio limits from the trading profile and safe_list
            if len(self.open_positions) >= self.profile.max_positions and symbol not in self.open_positions:
                logger.info(f"[SKIP] {symbol} - Max open positions reached ({self.profile.max_positions})")
                return
            max_daily = (get_symbol_config(symbol) or {}).get('max_daily_trades')
            if max_daily is not None and self.daily_trades.get(symbol, 0) >= max_daily:
                logger.info(f"[SKIP] {symbol} - Max daily trades reached ({max_daily})")
                return

            # Check if we already have an open position for this symbol
            if symbol in self.open_positions:
                existing = self.open_positions[symbol]
                logger.info(f"[SKIP] {symbol} - Already have open {existing['side'].upper()} position @ ${existing['entry_price']:,.2f}")
                logger.info(f"   Opened: {existing['timestamp']} | Current signal: {signal.signal_type.value.upper()}")
                return  # Skip this signal
            
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
                logger.warning(f" {symbol} - Position size too small: {quantity}")
                return
            
            # Get safe_list config for position limits
            config = get_symbol_config(symbol)
            max_position_usd = config.get('max_position_size_usd', 1000)
            
            # Respect max position size and the free USDT (keep 2% for fees)
            max_position_usd = min(max_position_usd, balance * 0.98)
            position_value_usd = quantity * current_price
            if position_value_usd > max_position_usd:
                quantity = max_position_usd / current_price
                position_value_usd = max_position_usd

            if position_value_usd < self.risk_manager.cfg.min_notional_usdt:
                logger.warning(f"{symbol} - Notional ${position_value_usd:.2f} below exchange minimum, skipping")
                return
            
            # Log trade details
            logger.info(f"\n{'='*60}")
            logger.info(f"TRADE EXECUTION: {symbol}")
            logger.info(f"{'='*60}")
            logger.info(f"Signal: {signal.signal_type.value.upper()}")
            logger.info(f"Confidence: {signal.confidence:.2%}")
            logger.info(f"Current Price: ${current_price:,.2f}")
            logger.info(f"Position Size: ${position_value_usd:,.2f} ({quantity:.6f} units)")
            logger.info(f"Stop Loss: ${stop_loss:,.2f}")
            risk_amount = abs(current_price - stop_loss) * quantity
            logger.info(f"Risk Amount: ${risk_amount:,.2f}")
            logger.info(f"Account Balance: ${balance:,.2f}")
            
            if self.dry_run:
                logger.info(f" DRY RUN MODE - Trade NOT executed")
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
                # Track what was really filled: net of commission charged in
                # the base asset, at the average fill price
                quantity, current_price, _ = fill_summary(order_result, base_asset(symbol))
                if quantity <= 0:
                    logger.error(f" {symbol} - Order not filled: {order_result.get('status')}")
                    return
                order_id = order_result.get('orderId', 'N/A')
                logger.info(f" {symbol} - Order filled: {quantity:.8f} @ ${current_price:,.4f}")
                logger.info(f"Order ID: {order_id}")
                
                # Get TP/SL configuration from .env (Spot optimized)
                tp_rr_ratio = float(getattr(settings, 'TP_RR_RATIO', 3.0))  # Default 3:1 for Spot
                
                # Calculate Take Profit/Stop Loss for SPOT (Wide TP/SL)
                # SPOT Strategy: Swing trading with wide stops to capture full trends
                distance_to_sl = abs(current_price - stop_loss)
                
                if signal.signal_type.value == 'buy':
                    take_profit = current_price + (distance_to_sl * tp_rr_ratio)
                else:  # sell
                    take_profit = current_price - (distance_to_sl * tp_rr_ratio)
                
                # Calculate projected profit percentage
                profit_pct = (distance_to_sl * tp_rr_ratio) / current_price * 100
                risk_pct = distance_to_sl / current_price * 100
                
                logger.info(f" SPOT Trade Setup (Swing Trading):")
                logger.info(f"   TP Distance: ${distance_to_sl * tp_rr_ratio:.2f} (+{profit_pct:.2f}%)")
                logger.info(f"   SL Distance: ${distance_to_sl:.2f} (-{risk_pct:.2f}%)")
                logger.info(f"   Risk/Reward: 1:{tp_rr_ratio:.1f}")
                
                self.daily_trades[symbol] = self.daily_trades.get(symbol, 0) + 1

                # Track position to prevent duplicate trades
                self.open_positions[symbol] = {
                    'side': signal.signal_type.value,
                    'entry_price': current_price,
                    'quantity': quantity,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'order_id': order_id,
                    'timestamp': datetime.now().isoformat()
                }
                # Protective stop ON THE EXCHANGE: protects the position even if
                # the bot dies. The monitor still handles TP/trailing/stagnation.
                self.open_positions[symbol]['stop_order_id'] = await self._place_exchange_stop(
                    symbol, quantity, stop_loss
                )
                self._save_state()
                logger.info(f" Position tracked: {symbol} {signal.signal_type.value.upper()} @ ${current_price:,.2f}")
                logger.info(f"   TP: ${take_profit:,.2f} | SL: ${stop_loss:,.2f}")
                
                # Log entry to P&L tracker
                self.pnl_logger.log_trade_entry(
                    symbol=symbol,
                    side=signal.signal_type.value,
                    entry_price=current_price,
                    quantity=quantity,
                    order_id=order_id,
                    timestamp=datetime.now()
                )
                
                # TODO: Implement position tracking in AccountManager when method exists
                # self.account_manager.add_position(...)
            else:
                logger.error(f" {symbol} - Order failed")
            
            logger.info(f"{'='*60}\n")
                
        except Exception as e:
            logger.error(f"Error executing trade for {symbol}: {e}", exc_info=True)
    
    async def monitor_open_positions(self):
        """
        Continuously monitor open positions for Take Profit/Stop Loss.
        
        NEW FEATURES:
        - Trailing Stop Loss (breakeven at +3%, trailing at +5%)
        - Stagnation Exit (close positions >24h with <1% profit)
        
        Checks every 2 seconds if positions should be closed.
        """
        logger.info("[MONITOR] Position monitoring started")
        logger.info("[MONITOR] Features: Trailing SL, Stagnation Exit")
        
        try:
            while self.running:
                if not self.open_positions:
                    await asyncio.sleep(2)
                    continue
                
                for symbol in list(self.open_positions.keys()):
                    try:
                        position = self.open_positions[symbol]
                        
                        # Get current price
                        ticker = await self.connector.get_ticker(symbol)
                        if not ticker or 'last' not in ticker:
                            continue
                        
                        current_price = ticker['last']

                        # A position must never stay without its exchange stop
                        if not self.dry_run and not position.get('stop_order_id'):
                            await self._rearm_stop_if_due(symbol)

                        entry_price = position['entry_price']
                        take_profit = position['take_profit']
                        stop_loss = position['stop_loss']
                        side = position['side']
                        
                        # ========================================
                        # TRAILING STOP LOSS (LONG POSITIONS)
                        # ========================================
                        if side == 'buy':
                            profit_pct = (current_price - entry_price) / entry_price
                            
                            # Trailing at +5% profit (2% below current)
                            if profit_pct >= 0.05:
                                trailing_sl = current_price * 0.98  # 2% below
                                if trailing_sl > stop_loss:
                                    position['stop_loss'] = trailing_sl
                                    logger.info(
                                        f"[TRAILING SL] {symbol} updated to ${trailing_sl:.2f} "
                                        f"(trailing 2%, profit: {profit_pct:.2%})"
                                    )
                                    stop_loss = trailing_sl  # Update for checks below
                                    await self._move_exchange_stop(symbol)
                            
                            # Breakeven at +3% profit
                            elif profit_pct >= 0.03 and stop_loss < entry_price:
                                breakeven_sl = entry_price
                                position['stop_loss'] = breakeven_sl
                                logger.info(
                                    f"[BREAKEVEN SL] {symbol} updated to ${breakeven_sl:.2f} "
                                    f"(profit: {profit_pct:.2%})"
                                )
                                stop_loss = breakeven_sl
                                await self._move_exchange_stop(symbol)
                        
                        # ========================================
                        # STAGNATION EXIT (CAPITAL ROTATION)
                        # ========================================
                        entry_time = datetime.fromisoformat(position['timestamp'])
                        hours_open = (datetime.now() - entry_time).total_seconds() / 3600
                        
                        if side == 'buy':
                            profit_pct = (current_price - entry_price) / entry_price
                        else:
                            profit_pct = (entry_price - current_price) / entry_price
                        
                        # Close stagnant positions (>24h, <1% profit)
                        if hours_open > 24 and profit_pct < 0.01:
                            logger.info(
                                f"[STAGNATION EXIT] {symbol} - Open {hours_open:.1f}h, "
                                f"Profit {profit_pct:.2%} < 1% - Rotating capital"
                            )
                            await self.close_position(symbol, 'stagnation', current_price)
                            continue  # Skip TP/SL checks (already closed)
                        
                        # ========================================
                        # STANDARD TP/SL CHECKS
                        # ========================================
                        # Check Take Profit
                        if side == 'buy' and current_price >= take_profit:
                            logger.info(f"✅ {symbol} - TAKE PROFIT HIT!")
                            await self.close_position(symbol, 'take_profit', current_price)
                        elif side == 'sell' and current_price <= take_profit:
                            logger.info(f"✅ {symbol} - TAKE PROFIT HIT!")
                            await self.close_position(symbol, 'take_profit', current_price)
                        
                        # Check Stop Loss
                        elif side == 'buy' and current_price <= stop_loss:
                            logger.info(f"🛑 {symbol} - STOP LOSS HIT!")
                            await self.close_position(symbol, 'stop_loss', current_price)
                        elif side == 'sell' and current_price >= stop_loss:
                            logger.info(f"🛑 {symbol} - STOP LOSS HIT!")
                            await self.close_position(symbol, 'stop_loss', current_price)
                    
                    except Exception as e:
                        logger.error(f"Error monitoring {symbol}: {e}")
                
                await asyncio.sleep(2)  # Check every 2 seconds
                
        except asyncio.CancelledError:
            logger.info("[MONITOR] Position monitoring stopped")
    
    async def close_position(self, symbol: str, reason: str, current_price: float):
        """
        Close an open position.
        
        Args:
            symbol: Trading pair
            reason: 'take_profit' or 'stop_loss'
            current_price: Current market price
        """
        try:
            position = self.open_positions.get(symbol)
            if not position:
                logger.warning(f"️ {symbol} - No position found to close")
                return
            
            # Determine opposite side
            close_side = 'sell' if position['side'] == 'buy' else 'buy'
            
            if self.dry_run:
                # Simulate close in dry run
                entry = position['entry_price']
                quantity = position['quantity']
                
                if position['side'] == 'buy':
                    pnl = (current_price - entry) * quantity
                else:
                    pnl = (entry - current_price) * quantity
                
                logger.info(f"{'='*60}")
                logger.info(f" DRY RUN - POSITION CLOSED: {symbol}")
                logger.info(f"{'='*60}")
                logger.info(f"Reason: {reason.upper()}")
                logger.info(f"Entry Price: ${entry:,.2f}")
                logger.info(f"Exit Price: ${current_price:,.2f}")
                logger.info(f"Quantity: {quantity:.6f}")
                logger.info(f"Simulated PNL: ${pnl:,.2f}")
                self._record_realized_pnl(pnl)
                logger.info(f"{'='*60}\n")
                
                del self.open_positions[symbol]
                self._save_state()
                return

            # Remove the exchange stop first, otherwise it locks the coins
            await self._cancel_exchange_stop(symbol)
            
            # Never sell more than what is actually free in the wallet
            close_quantity = position['quantity']
            if close_side == 'sell':
                balances = await self.connector.get_balance()
                free_base = balances.get(base_asset(symbol), {}).get('free', 0.0)
                close_quantity = min(close_quantity, free_base)

                if close_quantity * current_price < self.risk_manager.cfg.min_notional_usdt:
                    # Nothing left to sell: the exchange stop already filled
                    stop = position['stop_loss']
                    pnl = (stop - position['entry_price']) * position['quantity']
                    logger.warning(
                        f"{symbol} - No free balance to sell; assuming exchange stop filled "
                        f"near ${stop:,.4f} (approx PnL ${pnl:,.2f})"
                    )
                    self._record_realized_pnl(pnl)
                    del self.open_positions[symbol]
                    self._save_state()
                    return

            # Execute real closing order
            order_result = await self.connector.place_order(
                symbol=symbol,
                side=close_side,
                quantity=close_quantity,
                price=current_price,
                order_type='market'
            )
            
            if order_result:
                entry = position['entry_price']
                quantity, filled_price, quote_fee = fill_summary(order_result, base_asset(symbol))
                if filled_price > 0:
                    current_price = filled_price
                
                if position['side'] == 'buy':
                    pnl = (current_price - entry) * quantity - quote_fee
                else:
                    pnl = (entry - current_price) * quantity - quote_fee
                
                logger.info(f"{'='*60}")
                logger.info(f"POSITION CLOSED: {symbol}")
                logger.info(f"{'='*60}")
                logger.info(f"Reason: {reason.upper()}")
                logger.info(f"Entry Price: ${entry:,.2f}")
                logger.info(f"Exit Price: ${current_price:,.2f}")
                logger.info(f"Quantity: {quantity:.6f}")
                
                # Calculate ROI
                roi = (pnl / (entry * quantity)) * 100
                
                logger.info(f"Realized PNL: ${pnl:,.2f} ({'+' if pnl > 0 else ''}{roi:.2f}%)")
                logger.info(f"Order ID: {order_result.get('orderId', 'N/A')}")
                logger.info(f"{'='*60}\n")
                
                self._record_realized_pnl(pnl)

                # Log exit to P&L tracker
                self.pnl_logger.log_trade_exit(
                    symbol=symbol,
                    exit_price=current_price,
                    pnl=pnl,
                    roi=roi,
                    reason=reason,
                    timestamp=datetime.now(),
                    entry_price=entry,
                    quantity=quantity
                )
                
                # Remove from tracking
                del self.open_positions[symbol]
                self._save_state()
            else:
                logger.error(f" {symbol} - Failed to close position")
        
        except Exception as e:
            logger.error(f"Error closing position for {symbol}: {e}", exc_info=True)
    
    def _load_state(self):
        """Load open positions persisted by a previous run."""
        if not os.path.exists(STATE_FILE):
            return
        try:
            with open(STATE_FILE) as f:
                self.open_positions = json.load(f)
            logger.info(f"Restored {len(self.open_positions)} open position(s) from {STATE_FILE}")
        except Exception as e:
            logger.error(f"Could not load {STATE_FILE}: {e}")

    def _save_state(self):
        """Persist open positions atomically."""
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            tmp = STATE_FILE + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(self.open_positions, f, indent=2, default=str)
            os.replace(tmp, STATE_FILE)
        except Exception as e:
            logger.error(f"Could not save {STATE_FILE}: {e}")

    def _alert(self, message: str):
        """Raise an operator alert (CRITICAL log + in-memory record)."""
        logger.critical(f"[ALERT] {message}")
        self.alerts.append({'time': datetime.now().isoformat(), 'message': message})

    def _retry_schedule(self):
        """Delays before each attempt: first attempt immediately, then the retries."""
        return (0.0,) + tuple(self.stop_retry_delays)

    async def _find_open_stop(self, symbol: str) -> Optional[Dict]:
        """Return an open SELL STOP_LOSS order for symbol on the exchange, if any."""
        try:
            orders = await self.connector.get_positions(symbol)
        except Exception as e:
            logger.warning(f"{symbol} - Could not list open orders: {e}")
            return None
        for order in orders or []:
            if order.get('side') == 'SELL' and str(order.get('type', '')).startswith('STOP_LOSS'):
                return order
        return None

    async def _place_exchange_stop(self, symbol: str, quantity: float, stop_price: float):
        """
        Place a STOP_LOSS sell order for a long position, with retries.

        Before every retry the open orders are checked, so a stop placed by
        an attempt whose answer got lost is adopted instead of duplicated.
        Returns the order id, or None (after an alert) if the position is
        left without an exchange stop.
        """
        if self.dry_run:
            return None
        last_error = None
        attempts = 0
        for attempt, delay in enumerate(self._retry_schedule()):
            attempts = attempt + 1
            if delay:
                await asyncio.sleep(delay)
            if attempt > 0:
                existing = await self._find_open_stop(symbol)
                if existing:
                    logger.warning(f"{symbol} - Adopting existing exchange stop {existing.get('orderId')}")
                    return existing.get('orderId')
            try:
                order = await self.connector.create_stop_loss(symbol, 'sell', quantity, stop_price)
                return order.get('orderId')
            except Exception as e:
                last_error = e
                logger.error(f"{symbol} - Stop placement attempt {attempts} failed: {e}")
        self._alert(
            f"{symbol} - position WITHOUT exchange stop after {attempts} attempts "
            f"(client-side stop at {stop_price} still active): {last_error}"
        )
        return None

    async def _cancel_exchange_stop(self, symbol: str):
        """Cancel the position's exchange stop, if any."""
        position = self.open_positions.get(symbol, {})
        order_id = position.get('stop_order_id')
        if not order_id:
            return
        try:
            await self.connector.cancel_order(str(order_id), symbol)
        except Exception as e:
            logger.warning(f"{symbol} - Could not cancel stop order {order_id}: {e}")
        position['stop_order_id'] = None

    async def _rearm_stop_if_due(self, symbol: str):
        """Place a missing exchange stop, at most once every STOP_REARM_INTERVAL_SECONDS."""
        now = time.monotonic()
        last = self._last_stop_rearm.get(symbol)
        if last is not None and now - last < STOP_REARM_INTERVAL_SECONDS:
            return
        self._last_stop_rearm[symbol] = now
        position = self.open_positions[symbol]
        logger.warning(f"{symbol} - No exchange stop on record, re-arming")
        position['stop_order_id'] = await self._place_exchange_stop(
            symbol, position['quantity'], position['stop_loss']
        )
        self._save_state()

    async def _replace_lost_stop(self, symbol: str, reason: str):
        """The exchange stop is gone: alert and place a fresh one (with retries)."""
        position = self.open_positions[symbol]
        position['stop_order_id'] = None
        self._save_state()
        self._alert(f"{symbol} - position unprotected on the exchange ({reason}); placing a new stop")
        position['stop_order_id'] = await self._place_exchange_stop(
            symbol, position['quantity'], position['stop_loss']
        )
        self._save_state()

    async def _move_exchange_stop(self, symbol: str):
        """
        Move the exchange stop after a trailing/breakeven update.

        Uses POST /api/v3/order/cancelReplace with STOP_ON_FAILURE, so the
        old stop is only cancelled if the new one can be attempted:
        - both legs succeed: track the new order id;
        - cancel failed (STOP_ON_FAILURE): the old stop is intact; retry;
        - cancel succeeded but the new stop was rejected, or the old stop no
          longer exists (-2011): the position is unprotected -> alert and
          place a fresh stop with retries;
        - unknown outcome (timeout / 5xx): reconcile with the open orders.
        If every retry fails the old stop stays at its previous level and an
        alert is raised (the client-side stop keeps the new level).
        """
        position = self.open_positions[symbol]
        if self.dry_run:
            self._save_state()
            return

        quantity = position['quantity']
        stop_price = position['stop_loss']
        old_id = position.get('stop_order_id')
        if not old_id:
            position['stop_order_id'] = await self._place_exchange_stop(symbol, quantity, stop_price)
            self._save_state()
            return

        last_error = None
        attempts = 0
        for attempt, delay in enumerate(self._retry_schedule()):
            attempts = attempt + 1
            if delay:
                await asyncio.sleep(delay)
            try:
                new_order = await self.connector.replace_stop_loss(
                    symbol, str(old_id), 'sell', quantity, stop_price
                )
                position['stop_order_id'] = new_order.get('orderId')
                self._save_state()
                return
            except CancelReplaceError as e:
                last_error = e
                if e.cancel_succeeded:
                    await self._replace_lost_stop(symbol, f"stop {old_id} cancelled, new stop rejected: {e}")
                    return
                if e.cancel_error_code == BINANCE_UNKNOWN_ORDER:
                    await self._replace_lost_stop(symbol, f"stop {old_id} no longer exists: {e}")
                    return
                if e.outcome_unknown:
                    existing = await self._find_open_stop(symbol)
                    if existing is None:
                        await self._replace_lost_stop(symbol, f"unknown cancelReplace outcome: {e}")
                        return
                    old_id = existing.get('orderId')
                    position['stop_order_id'] = old_id
                    self._save_state()
                    if _same_price(existing.get('stopPrice'), stop_price):
                        return  # the replace went through, only the answer was lost
                logger.error(f"{symbol} - Stop move attempt {attempts} failed: {e}")
            except Exception as e:
                last_error = e
                logger.error(f"{symbol} - Stop move attempt {attempts} failed: {e}")

        self._save_state()
        self._alert(
            f"{symbol} - could not move exchange stop to {stop_price} after {attempts} attempts; "
            f"stop {old_id} stays at its previous level (client-side stop active): {last_error}"
        )

    def _roll_trading_day(self):
        """Reset daily counters at the start of a new (local) day."""
        today = datetime.now().date()
        if today != self.trading_day:
            self.trading_day = today
            self.daily_realized_pnl = 0.0
            self.daily_trades = {}
            self.risk_manager.update_daily_pnl(0.0)

    def _record_realized_pnl(self, pnl: float):
        """Accumulate realized P&L so the daily drawdown kill switch works."""
        self._roll_trading_day()
        self.daily_realized_pnl += pnl
        self.risk_manager.update_daily_pnl(self.daily_realized_pnl)
        logger.info(f"Daily realized PnL: ${self.daily_realized_pnl:,.2f}")

    async def stop(self):
        """Stop the engine and cleanup resources."""
        logger.info("Stopping Multi-Symbol Trading Engine...")
        self.running = False
        
        await self.connector.close()
        self.zmq_socket.close()
        self.zmq_context.term()
        
        logger.info("Engine stopped")


def resolve_engine_mode(cfg=None) -> ExecutionMode:
    """
    Resolve the execution mode of the spot engine from settings.

    dry_run is the default; live needs LIVE_TRADING_CONFIRM=I_UNDERSTAND; 1m
    profiles are forced to dry_run unless ALLOW_1M_LIVE=true. The legacy
    USE_TESTNET flag is ignored: the network follows TRADING_MODE.

    Raises:
        TradingModeError: invalid mode, unconfirmed live, or futures_testnet
            (this engine only trades spot).
    """
    cfg = cfg or settings
    mode = resolve_settings_mode(cfg)
    if mode.mode == 'futures_testnet':
        raise TradingModeError(
            "multi_symbol_engine is a spot engine; TRADING_MODE=futures_testnet is not supported here"
        )
    return mode


async def main():
    """Main entry point."""
    mode = resolve_engine_mode()
    logger.info(
        f"TRADING_MODE requested={mode.requested} effective={mode.mode} "
        f"(dry_run={mode.dry_run}, testnet={mode.use_testnet})"
    )
    if mode.reason:
        logger.warning(f"Execution mode downgraded: {mode.reason}")

    # Symbols come from safe_list
    engine = MultiSymbolEngine(
        use_testnet=mode.use_testnet,
        dry_run=mode.dry_run
    )
    
    await engine.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Multi-Symbol Engine stopped by user")
