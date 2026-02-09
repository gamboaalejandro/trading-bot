"""
Account Manager - Track positions, P&L, and trading metrics
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum

logger = logging.getLogger(__name__)


class PositionSide(Enum):
    """Position side enum."""
    LONG = "long"
    SHORT = "short"


@dataclass
class Position:
    """Represents an open trading position."""
    symbol: str
    side: PositionSide
    entry_price: float
    size: float  # Amount in base currency
    entry_time: datetime = field(default_factory=datetime.now)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    unrealized_pnl: float = 0.0
    
    def update_pnl(self, current_price: float):
        """Update unrealized P&L based on current price."""
        if self.side == PositionSide.LONG:
            self.unrealized_pnl = (current_price - self.entry_price) * self.size
        else:  # SHORT
            self.unrealized_pnl = (self.entry_price - current_price) * self.size
    
    def get_roi(self) -> float:
        """Get return on investment percentage."""
        investment = self.entry_price * self.size
        if investment == 0:
            return 0.0
        return (self.unrealized_pnl / investment) * 100
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'side': self.side.value,
            'entry_price': self.entry_price,
            'size': self.size,
            'entry_time': self.entry_time.isoformat(),
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'unrealized_pnl': self.unrealized_pnl,
            'roi_pct': self.get_roi()
        }


@dataclass
class ClosedTrade:
    """Represents a closed trade."""
    symbol: str
    side: PositionSide
    entry_price: float
    exit_price: float
    size: float
    realized_pnl: float
    entry_time: datetime
    exit_time: datetime
    duration_seconds: float
    
    def was_winner(self) -> bool:
        """Check if trade was profitable."""
        return self.realized_pnl > 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'side': self.side.value,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'size': self.size,
            'realized_pnl': self.realized_pnl,
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat(),
            'duration_seconds': self.duration_seconds,
            'was_winner': self.was_winner()
        }


class AccountManager:
    """
    Manages trading account state, positions, and metrics.
    
    Features:
    - Position tracking (open and closed)
    - Daily P&L calculation
    - Circuit breaker integration
    - Trading statistics (win rate, profit factor, etc.)
    """
    
    def __init__(self, initial_balance: float = 10000.0):
        """
        Initialize account manager.
        
        Args:
            initial_balance: Starting USDT balance
        """
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        
        # Position tracking
        self.open_positions: Dict[str, Position] = {}
        self.closed_trades: List[ClosedTrade] = []
        
        # Daily tracking
        self.today = date.today()
        self.daily_pnl = 0.0
        self.daily_trades = 0
        
        # All-time metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0.0
        self.total_loss = 0.0
        
        logger.info(f"Account Manager initialized with ${initial_balance:.2f}")
    
    def reset_daily_metrics(self):
        """Reset daily metrics (call at start of new trading day)."""
        today = date.today()
        if today != self.today:
            logger.info(
                f"New trading day. Previous day P&L: ${self.daily_pnl:.2f} "
                f"({self.daily_trades} trades)"
            )
            self.today = today
            self.daily_pnl = 0.0
            self.daily_trades = 0
    
    def open_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Position:
        """
        Open a new position.
        
        Args:
            symbol: Trading pair
            side: 'long' or 'short'
            entry_price: Entry price
            size: Position size in base currency
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            
        Returns:
            Created Position object
        """
        if symbol in self.open_positions:
            logger.warning(f"Position already exists for {symbol}. Closing old position first.")
            self.close_position(symbol, entry_price)  # Close at same price
        
        position_side = PositionSide.LONG if side.lower() == 'long' else PositionSide.SHORT
        
        position = Position(
            symbol=symbol,
            side=position_side,
            entry_price=entry_price,
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        self.open_positions[symbol] = position
        
        sl_str = f"${stop_loss:.2f}" if stop_loss else "None"
        tp_str = f"${take_profit:.2f}" if take_profit else "None"
        logger.info(
            f"[OK] Opened {side.upper()} position: {size} {symbol} @ ${entry_price:.2f} "
            f"(SL: {sl_str}, TP: {tp_str})"
        )
        
        return position
    
    def close_position(
        self,
        symbol: str,
        exit_price: float
    ) -> Optional[ClosedTrade]:
        """
        Close an open position.
        
        Args:
            symbol: Trading pair
            exit_price: Exit price
            
        Returns:
            ClosedTrade object or None if position doesn't exist
        """
        position = self.open_positions.get(symbol)
        
        if not position:
            logger.warning(f"No open position found for {symbol}")
            return None
        
        # Calculate realized P&L
        if position.side == PositionSide.LONG:
            realized_pnl = (exit_price - position.entry_price) * position.size
        else:  # SHORT
            realized_pnl = (position.entry_price - exit_price) * position.size
        
        # Calculate duration
        exit_time = datetime.now()
        duration = (exit_time - position.entry_time).total_seconds()
        
        # Create closed trade record
        closed_trade = ClosedTrade(
            symbol=symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=exit_price,
            size=position.size,
            realized_pnl=realized_pnl,
            entry_time=position.entry_time,
            exit_time=exit_time,
            duration_seconds=duration
        )
        
        # Update metrics
        self.closed_trades.append(closed_trade)
        self.current_balance += realized_pnl
        self.daily_pnl += realized_pnl
        self.daily_trades += 1
        self.total_trades += 1
        
        if realized_pnl > 0:
            self.winning_trades += 1
            self.total_profit += realized_pnl
        else:
            self.losing_trades += 1
            self.total_loss += abs(realized_pnl)
        
        # Remove from open positions
        del self.open_positions[symbol]
        
        logger.info(
            f"[OK] Closed {position.side.value.upper()} position: {symbol} @ ${exit_price:.2f} | "
            f"P&L: ${realized_pnl:+.2f} ({closed_trade.get_roi():+.2f}%)"
        )
        
        return closed_trade
    
    def update_position_pnl(self, symbol: str, current_price: float):
        """Update unrealized P&L for a position."""
        position = self.open_positions.get(symbol)
        if position:
            position.update_pnl(current_price)
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get open position for symbol."""
        return self.open_positions.get(symbol)
    
    def get_daily_pnl(self) -> float:
        """Get today's realized P&L."""
        self.reset_daily_metrics()
        return self.daily_pnl
    
    def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized P&L from all open positions."""
        return sum(pos.unrealized_pnl for pos in self.open_positions.values())
    
    def get_equity(self) -> float:
        """Get total account equity (balance + unrealized P&L)."""
        return self.current_balance + self.get_total_unrealized_pnl()
    
    def get_win_rate(self) -> float:
        """Get win rate percentage."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    def get_profit_factor(self) -> float:
        """Get profit factor (total profit / total loss)."""
        if self.total_loss == 0:
            return float('inf') if self.total_profit > 0 else 0.0
        return self.total_profit / self.total_loss
    
    def get_average_win(self) -> float:
        """Get average winning trade size."""
        if self.winning_trades == 0:
            return 0.0
        return self.total_profit / self.winning_trades
    
    def get_average_loss(self) -> float:
        """Get average losing trade size."""
        if self.losing_trades == 0:
            return 0.0
        return self.total_loss / self.losing_trades
    
    def get_reward_risk_ratio(self) -> float:
        """Get average win / average loss ratio."""
        avg_loss = self.get_average_loss()
        if avg_loss == 0:
            return 0.0
        return self.get_average_win() / avg_loss
    
    def get_stats(self) -> Dict:
        """Get comprehensive account statistics."""
        self.reset_daily_metrics()
        
        return {
            'balance': self.current_balance,
            'equity': self.get_equity(),
            'unrealized_pnl': self.get_total_unrealized_pnl(),
            'daily_pnl': self.daily_pnl,
            'daily_trades': self.daily_trades,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.get_win_rate(),
            'profit_factor': self.get_profit_factor(),
            'avg_win': self.get_average_win(),
            'avg_loss': self.get_average_loss(),
            'reward_risk_ratio': self.get_reward_risk_ratio(),
            'open_positions': len(self.open_positions),
            'total_return_pct': ((self.current_balance - self.initial_balance) / self.initial_balance) * 100
        }
    
    def print_stats(self):
        """Print formatted account statistics."""
        stats = self.get_stats()
        
        print("\n" + "="*60)
        print("ACCOUNT STATISTICS")
        print("="*60)
        print(f"Balance:        ${stats['balance']:>12,.2f}")
        print(f"Equity:         ${stats['equity']:>12,.2f}")
        print(f"Unrealized P&L: ${stats['unrealized_pnl']:>12,.2f}")
        print(f"Total Return:   {stats['total_return_pct']:>12.2f}%")
        print("-"*60)
        print(f"Today's P&L:    ${stats['daily_pnl']:>12,.2f}")
        print(f"Today's Trades: {stats['daily_trades']:>13}")
        print("-"*60)
        print(f"Total Trades:   {stats['total_trades']:>13}")
        print(f"Wins / Losses:  {stats['winning_trades']:>6} / {stats['losing_trades']:<6}")
        print(f"Win Rate:       {stats['win_rate']:>12.2f}%")
        print(f"Profit Factor:  {stats['profit_factor']:>12.2f}")
        print(f"Avg Win:        ${stats['avg_win']:>12,.2f}")
        print(f"Avg Loss:       ${stats['avg_loss']:>12,.2f}")
        print(f"R:R Ratio:      {stats['reward_risk_ratio']:>12.2f}")
        print("-"*60)
        print(f"Open Positions: {stats['open_positions']:>13}")
        print("="*60)
