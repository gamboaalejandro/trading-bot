"""
Profit & Loss Logger
Dedicated logging module for tracking trading performance

Logs to: logs/pnl_tracker.log
- Trade-level entries (entry/exit)
- Profit/Loss calculations
- Daily summaries
- ROI tracking
"""
import logging
from datetime import datetime, date
from typing import Optional, Dict
from pathlib import Path


class PnLLogger:
    """Dedicated P&L tracking logger."""
    
    def __init__(self, log_file: str = "logs/pnl_tracker.log"):
        """
        Initialize P&L logger.
        
        Args:
            log_file: Path to P&L log file
        """
        # Create logs directory if it doesn't exist
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Create dedicated logger
        self.logger = logging.getLogger("PnL_Tracker")
        self.logger.setLevel(logging.INFO)
        
        # Remove any existing handlers
        self.logger.handlers = []
        
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        
        # Also log to console for visibility
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Daily tracking
        self.daily_trades: Dict[str, list] = {}  # {date: [pnl1, pnl2, ...]}
        
        # Log initialization
        self.logger.info("=" * 80)
        self.logger.info("P&L LOGGER INITIALIZED")
        self.logger.info("=" * 80)
    
    def log_trade_entry(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        order_id: str,
        timestamp: datetime
    ):
        """
        Log trade entry.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            entry_price: Entry price
            quantity: Position size
            order_id: Exchange order ID
            timestamp: Trade timestamp
        """
        position_value = entry_price * quantity
        
        self.logger.info("")
        self.logger.info("=" * 80)
        self.logger.info(f" TRADE ENTRY: {symbol}")
        self.logger.info("=" * 80)
        self.logger.info(f"Order ID:      {order_id}")
        self.logger.info(f"Side:          {side.upper()}")
        self.logger.info(f"Entry Price:   ${entry_price:,.2f}")
        self.logger.info(f"Quantity:      {quantity:.6f}")
        self.logger.info(f"Position Size: ${position_value:,.2f}")
        self.logger.info(f"Timestamp:     {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 80)
    
    def log_trade_exit(
        self,
        symbol: str,
        exit_price: float,
        pnl: float,
        roi: float,
        reason: str,
        timestamp: datetime,
        entry_price: Optional[float] = None,
        quantity: Optional[float] = None
    ):
        """
        Log trade exit with P&L.
        
        Args:
            symbol: Trading pair
            exit_price: Exit price
            pnl: Profit/Loss in USD
            roi: Return on Investment (%)
            reason: Exit reason ('take_profit', 'stop_loss', 'manual')
            timestamp: Exit timestamp
            entry_price: Original entry price (optional, for reference)
            quantity: Position size (optional, for reference)
        """
        # Determine emoji based on P&L
        if pnl > 0:
            emoji = "[PROFIT]"
            result = "WIN"
        elif pnl < 0:
            emoji = " LOSS"
            result = "LOSS"
        else:
            emoji = " BREAK EVEN"
            result = "NEUTRAL"
        
        # Track daily P&L
        today = date.today().isoformat()
        if today not in self.daily_trades:
            self.daily_trades[today] = []
        self.daily_trades[today].append(pnl)
        
        # Log trade exit
        self.logger.info("")
        self.logger.info("=" * 80)
        self.logger.info(f"{emoji}: {symbol}")
        self.logger.info("=" * 80)
        self.logger.info(f"Exit Reason:   {reason.upper()}")
        self.logger.info(f"Result:        {result}")
        
        if entry_price and quantity:
            self.logger.info(f"Entry Price:   ${entry_price:,.2f}")
            self.logger.info(f"Exit Price:    ${exit_price:,.2f}")
            self.logger.info(f"Quantity:      {quantity:.6f}")
        else:
            self.logger.info(f"Exit Price:    ${exit_price:,.2f}")
        
        self.logger.info(f"P&L:           ${pnl:+,.2f}")
        self.logger.info(f"ROI:           {roi:+.2f}%")
        self.logger.info(f"Timestamp:     {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 80)
        
        # Log daily summary
        self._log_daily_summary()
    
    def _log_daily_summary(self):
        """Log daily P&L summary."""
        today = date.today().isoformat()
        
        if today not in self.daily_trades or not self.daily_trades[today]:
            return
        
        trades = self.daily_trades[today]
        total_pnl = sum(trades)
        num_trades = len(trades)
        wins = sum(1 for pnl in trades if pnl > 0)
        losses = sum(1 for pnl in trades if pnl < 0)
        win_rate = (wins / num_trades * 100) if num_trades > 0 else 0
        
        avg_win = sum(pnl for pnl in trades if pnl > 0) / wins if wins > 0 else 0
        avg_loss = sum(pnl for pnl in trades if pnl < 0) / losses if losses > 0 else 0
        
        self.logger.info("")
        self.logger.info("┌" + "─" * 78 + "┐")
        self.logger.info("│" + " " * 25 + f"DAILY SUMMARY - {today}" + " " * 26 + "│")
        self.logger.info("├" + "─" * 78 + "┤")
        self.logger.info(f"│  Total P&L:      ${total_pnl:+,.2f}" + " " * (54 - len(f"${total_pnl:+,.2f}")) + "│")
        self.logger.info(f"│  Total Trades:   {num_trades}" + " " * (64 - len(str(num_trades))) + "│")
        self.logger.info(f"│  Wins:           {wins} ({win_rate:.1f}%)" + " " * (56 - len(f"{wins} ({win_rate:.1f}%)")) + "│")
        self.logger.info(f"│  Losses:         {losses}" + " " * (64 - len(str(losses))) + "│")
        
        if wins > 0:
            self.logger.info(f"│  Avg Win:        ${avg_win:,.2f}" + " " * (54 - len(f"${avg_win:,.2f}")) + "│")
        if losses > 0:
            self.logger.info(f"│  Avg Loss:       ${avg_loss:,.2f}" + " " * (54 - len(f"${avg_loss:,.2f}")) + "│")
        
        self.logger.info("└" + "─" * 78 + "┘")
        self.logger.info("")
    
    def log_manual_summary(self, date_str: Optional[str] = None):
        """
        Manually trigger a daily summary log.
        
        Args:
            date_str: Date in 'YYYY-MM-DD' format. If None, uses today.
        """
        if date_str is None:
            date_str = date.today().isoformat()
        
        if date_str not in self.daily_trades:
            self.logger.info(f"No trades recorded for {date_str}")
            return
        
        self._log_daily_summary()


# Convenience function for testing
if __name__ == "__main__":
    # Test the logger
    logger = PnLLogger()
    
    # Simulate trade entry
    logger.log_trade_entry(
        symbol="BTC/USDT",
        side="buy",
        entry_price=71000.0,
        quantity=0.001,
        order_id="TEST_12345",
        timestamp=datetime.now()
    )
    
    # Simulate profitable exit
    logger.log_trade_exit(
        symbol="BTC/USDT",
        exit_price=72500.0,
        pnl=1.50,  # $1.50 profit
        roi=2.11,  # 2.11% ROI
        reason="take_profit",
        timestamp=datetime.now(),
        entry_price=71000.0,
        quantity=0.001
    )
    
    # Simulate losing trade
    logger.log_trade_exit(
        symbol="ETH/USDT",
        exit_price=2100.0,
        pnl=-5.00,  # $5 loss
        roi=-2.38,  # -2.38% ROI
        reason="stop_loss",
        timestamp=datetime.now()
    )
    
    print("\n P&L Logger test completed. Check logs/pnl_tracker.log")
