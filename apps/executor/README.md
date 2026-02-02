# Risk Management & Executor Module

## Overview

The Executor module is responsible for **position sizing** and **order execution**. Currently only the risk management framework is implemented.

## Status: ⏳ Partially Implemented

**Implemented**:
- ✅ `risk_manager.py`: Kelly Criterion, ATR stop loss

**Not Implemented**:
- ❌ `trade_executor.py`: Order placement (skeleton only)
- ❌ Position tracking
- ❌ PnL calculation
- ❌ Live order execution

## Key Files

| File | Purpose | Status | Lines |
|------|---------|--------|-------|
| `risk_manager.py` | Position sizing, stop loss | ✅ Complete | ~120 |
| `trade_executor.py` | Order execution | ❌ Skeleton | ~40 |

## Risk Manager Deep Dive

### Kelly Criterion Explained

**Formula**:
```
K% = W - (1-W)/R

Where:
  W = Win rate (probability of winning)
  R = Reward/Risk ratio (average win / average loss)
```

**Example Calculation**:
```python
# Historical performance
wins = 55  # 55% win rate
losses = 45
avg_win = 150  # $150 average profit
avg_loss = 100  # $100 average loss

W = 0.55
R = 150 / 100 = 1.5

K% = 0.55 - (0.45 / 1.5)
   = 0.55 - 0.30
   = 0.25  # Bet 25% of bankroll
```

**Interpretation**:
- K% = 0.25 → Risk 25% of capital per trade
- K% = 0 → Don't trade (no edge)
- K% < 0 → **Never trade** (negative expectancy)

**Critical Notes**:
1. **Full Kelly is aggressive**: 25% risk can lead to 50%+ drawdowns
2. **Half Kelly recommended**: Use K%/2 for safety (12.5% in example)
3. **Quarter Kelly conservative**: K%/4 = 6.25% (smoother equity curve)

### Implementation

```python
def calculate_kelly_fraction(
    self,
    win_rate: float,
    avg_win: float,
    avg_loss: float
) -> float:
    """
    Calculate optimal position size using Kelly Criterion.
    
    Args:
        win_rate: Historical win rate (0.0 to 1.0)
        avg_win: Average profit per winning trade
        avg_loss: Average loss per losing trade (positive value)
    
    Returns:
        Fraction of bankroll to risk (0.0 to 1.0)
    """
    if win_rate <= 0 or win_rate >= 1:
        return 0.0
    
    if avg_loss <= 0:
        return 0.0  # Avoid division by zero
    
    reward_risk_ratio = avg_win / avg_loss
    kelly = win_rate - ((1 - win_rate) / reward_risk_ratio)
    
    # Safety: Never risk more than configured max
    kelly = max(0.0, min(kelly, self.max_kelly_fraction))
    
    return kelly
```

**Safety Mechanisms**:
1. **Max Kelly cap**: Default 0.25 (25%)
2. **Return 0 if negative**: Don't trade if no edge
3. **Input validation**: Reject invalid win rates

### ATR Stop Loss

**What is ATR?**
Average True Range - measures volatility over N periods.

**Formula**:
```
True Range = max(
    High - Low,
    |High - Previous Close|,
    |Low - Previous Close|
)

ATR = EMA(True Range, period=14)
```

**Stop Loss Calculation**:
```
Long Position:
  Stop Loss = Entry Price - (ATR × Multiplier)

Short Position:
  Stop Loss = Entry Price + (ATR × Multiplier)
```

**Example**:
```python
entry_price = 50000  # BTC at $50k
atr = 1000  # ATR is $1,000
multiplier = 2.0

stop_loss = 50000 - (1000 * 2.0) = $48,000
risk_per_unit = 50000 - 48000 = $2,000
```

**Why ATR?**
- ✅ Adapts to volatility (tight in calm markets, wide in volatile)
- ✅ Prevents premature stop-outs
- ❌ Requires historical data (14+ candles)
- ❌ Can be too wide in extreme volatility

**Alternative Stop Methods**:
1. **Fixed percentage**: Stop at -2%
   - ✅ Simple
   - ❌ Doesn't adapt to volatility
2. **Support/Resistance**: Stop below last swing low
   - ✅ Respects market structure
   - ❌ Subjective, hard to automate
3. **Time-based**: Exit after N hours
   - ✅ Limits exposure
   - ❌ Ignores price action

### Implementation

```python
def calculate_dynamic_stop_loss(
    self,
    entry_price: float,
    atr: float,
    position_side: str,
    multiplier: float = 2.0
) -> float:
    """
    Calculate ATR-based stop loss.
    
    Args:
        entry_price: Entry price level
        atr: Average True Range (14 periods)
        position_side: 'long' or 'short'
        multiplier: ATR multiplier (default 2.0)
    
    Returns:
        Stop loss price level
    """
    stop_distance = atr * multiplier
    
    if position_side == 'long':
        return entry_price - stop_distance
    else:  # short
        return entry_price + stop_distance
```

**Multiplier Selection**:
- 1.0× ATR: Very tight (high win rate, low R:R)
- 2.0× ATR: **Balanced** (recommended)
- 3.0× ATR: Wide (low win rate, high R:R)

## Critical Design Flaws

### 🔴 Problem 1: Risk Manager Not Enforced

**Current state**: Risk Manager is a library, not a service.

**Risk**:
```python
# Developer can bypass risk checks!
exchange.create_order(
    symbol='BTC/USDT',
    size=1000,  # ❌ No Kelly check!
    stopLoss=None  # ❌ No stop loss!
)
```

**Impact**: Can blow up account with single fat-finger trade.

**Solution**: Make Risk Manager a gatekeeper:
```python
class TradeExecutor:
    async def execute_signal(self, signal: Signal):
        # ✅ Mandatory risk check
        approved = await risk_manager.approve_trade(signal)
        if not approved:
            logger.warning("Trade rejected by risk manager")
            return None
        
        # Only execute if approved
        order = await exchange.create_order(...)
```

### 🔴 Problem 2: No Historical Win Rate Tracking

**Current state**: Win rate is hardcoded.

```python
# In risk_manager.py
win_rate = 0.55  # ❌ Made up!
```

**Risk**: Kelly calculation is garbage-in, garbage-out.

**Solution**: Track actual performance:
```python
class PerformanceTracker:
    def record_trade(self, pnl: float):
        self.trades.append(pnl)
    
    def calculate_win_rate(self) -> float:
        if not self.trades:
            return 0.5  # Default to 50/50
        
        wins = sum(1 for pnl in self.trades if pnl > 0)
        return wins / len(self.trades)
```

### 🔴 Problem 3: No Position Monitoring

**Current state**: Set stop loss and forget.

**Risk**: What if stop loss order fails? What if it gets cancelled?

**Solution**: Active monitoring:
```python
async def monitor_position(position):
    while position.is_open:
        current_price = await get_current_price()
        
        # Manual stop loss check
        if position.side == 'long' and current_price <= position.stop_loss:
            await close_position(position, reason='stop_loss_hit')
        
        # Trailing stop
        if current_price > position.entry * 1.02:  # 2% profit
            new_stop = position.entry * 1.01  # Move to 1% profit
            await update_stop_loss(new_stop)
        
        await asyncio.sleep(1)  # Check every second
```

## Future Implementation: Trade Executor

### Design (Not Implemented)

```python
class TradeExecutor:
    async def execute_signal(self, signal: Signal) -> Optional[Order]:
        # 1. Risk check
        kelly_size = risk_manager.calculate_kelly_size(
            balance=await get_balance(),
            win_rate=performance.get_win_rate(),
            avg_win=performance.get_avg_win(),
            avg_loss=performance.get_avg_loss()
        )
        
        # 2. Calculate stop loss
        atr = await indicators.calculate_atr(symbol, period=14)
        stop_loss = risk_manager.calculate_dynamic_stop_loss(
            entry_price=signal.price,
            atr=atr,
            position_side=signal.side
        )
        
        # 3. Submit order
        order = await exchange.create_order(
            symbol=signal.symbol,
            type='market',  # Or 'limit' for better price
            side=signal.side,
            amount=kelly_size,
            params={'stopLoss': {'price': stop_loss}}
        )
        
        # 4. Confirm execution
        if order['status'] == 'filled':
            await performance.record_entry(order)
            return order
        
        return None
```

### Order Types

| Type | Use Case | Pros | Cons |
|------|----------|------|------|
| **Market** | Immediate execution | ✅ Fast | ❌ Slippage |
| **Limit** | Better price | ✅ No slippage | ❌ May not fill |
| **Stop Market** | Stop loss | ✅ Guaranteed execution | ❌ Slippage in fast markets |
| **Stop Limit** | Stop loss (limit) | ✅ Price control | ❌ May not fill |

**Recommendation**: Market for entries (speed), Stop Market for exits (safety).

### Slippage Model

**Slippage**: Difference between expected price and fill price.

```python
expected_price = 50000
actual_fill = 50050
slippage = 50050 - 50000 = $50 (0.1%)
```

**Factors**:
1. **Volatility**: Higher volatility = more slippage
2. **Order size**: Larger orders = more slippage
3. **Liquidity**: Low liquidity = more slippage

**Estimation**:
```python
def estimate_slippage(order_size, liquidity):
    # Rule of thumb: 0.05% for every 1% of daily volume
    volume_pct = order_size / daily_volume
    slippage_bps = volume_pct * 5  # basis points
    return slippage_bps
```

## Testing

### Unit Tests (To Implement)

```python
def test_kelly_criterion():
    rm = RiskManager()
    
    # Test positive edge
    kelly = rm.calculate_kelly_fraction(
        win_rate=0.6,
        avg_win=150,
        avg_loss=100
    )
    assert kelly > 0
    assert kelly < rm.max_kelly_fraction
    
    # Test no edge
    kelly = rm.calculate_kelly_fraction(
        win_rate=0.4,
        avg_win=100,
        avg_loss=100
    )
    assert kelly == 0  # Don't trade

def test_atr_stop_loss():
    rm = RiskManager()
    
    # Long position
    stop = rm.calculate_dynamic_stop_loss(
        entry_price=50000,
        atr=1000,
        position_side='long',
        multiplier=2.0
    )
    assert stop == 48000  # 50000 - (1000*2)
    
    # Short position
    stop = rm.calculate_dynamic_stop_loss(
        entry_price=50000,
        atr=1000,
        position_side='short',
        multiplier=2.0
    )
    assert stop == 52000  # 50000 + (1000*2)
```

### Backtest (To Implement)

```python
# Test on historical data
results = backtest(
    strategy=MyStrategy(),
    risk_manager=RiskManager(max_kelly_fraction=0.25),
    data=historical_data,
    initial_capital=10000
)

print(f"Final balance: ${results.final_balance}")
print(f"Max drawdown: {results.max_drawdown:.2%}")
print(f"Sharpe ratio: {results.sharpe_ratio:.2f}")
```

## Real-World Examples

### Example 1: Conservative Trader

```python
# Configuration
win_rate = 0.52  # Slight edge
avg_win = 100
avg_loss = 90
capital = 10000

# Full Kelly
kelly = 0.52 - (0.48 / (100/90))
      = 0.52 - 0.432
      = 0.088  # 8.8%

# Quarter Kelly (conservative)
position_size = 10000 * (0.088 / 4)
              = 10000 * 0.022
              = $220 per trade

# Stop loss (ATR = $500, 2x multiplier)
entry = 50000
stop = 50000 - (500 * 2) = $49,000
risk = $1,000

# Shares to buy
shares = 220 / 1000 = 0.0044 BTC
```

### Example 2: Aggressive Trader (⚠️ Risky)

```python
# Configuration
win_rate = 0.65  # Strong edge (overconfident?)
avg_win = 200
avg_loss = 100
capital = 10000

# Full Kelly
kelly = 0.65 - (0.35 / 2.0) = 0.475  # 47.5%!

# Half Kelly (still aggressive)
position_size = 10000 * (0.475 / 2) = $2,375 per trade

# If wrong, lose 23.75% of capital in one trade!
```

**Lesson**: Never use full Kelly. Even half Kelly can be dangerous.

## FAQ

**Q: What if I don't have historical win rate?**

A: Start conservatively:
- Use 50% win rate (no edge)
- Risk only 1-2% per trade
- Build track record over 50+ trades

**Q: Should I use Kelly for crypto?**

A: With caveats:
- Crypto is more volatile than stocks (use Quarter Kelly)
- Win rates change quickly (recalculate monthly)
- Black swan events (cap max position at 10%)

**Q: What if ATR is very small (low volatility)?**

A: Set minimum stop distance:
```python
stop_distance = max(atr * multiplier, min_stop_distance)
```

---

**Last Updated**: 2026-02-02  
**Maintainer**: Alejandro G.  
**Status**: ⚠️ Framework only - NOT connected to live trading
