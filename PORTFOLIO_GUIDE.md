# Portfolio Selection Guide: How to Maximize "Semi-Safe" Gains

## The Philosophy
To maximize gains while keeping risk "semi-safe", we use a **Core-Satellite** approach:
- **Core (60-70%):** Stable assets (BTC, ETH) using Mean Reversion.
- **Satellite (30-40%):** High-growth assets (SOL, DOGE) using Momentum.

## How to Select Coins

### 1. Run the Optimizer
Use the included `apps/analytics/optimizer.py` to check the **Sharpe Ratio** of a potential coin.

```bash
python apps/analytics/optimizer.py
```

### 2. Interpret the Sharpe Ratio
- **Sharpe > 2.0:** Excellent. High return for low volatility. (e.g., BTC in bull markets)
- **Sharpe 1.0 - 2.0:** Good. Acceptable for "Sweet Spot" allocation.
- **Sharpe < 0.5:** Avoid. Too much risk for the return.

### 3. Check Volatility (ATR)
- If `ATR % > 5%`: Classify as **CASINO**. Max allocation 5%.
- If `ATR % 2-5%`: Classify as **SWEET SPOT**. Max allocation 15%.
- If `ATR % < 2%`: Classify as **STABLE**. Max allocation 30%.

## Current "Semi-Safe" Portfolio Configuration

Based on our latest optimization (Feb 2026):

| Asset | Role | Strategy | Allocation | Why? |
|---|---|---|---|---|
| **BTC** | Anchor | Mean Reversion | 25% | Consistent compounding, low drawdown. |
| **ETH** | Anchor | Mean Reversion | 20% | Follows BTC but with slightly higher beta. |
| **SOL** | Growth | Momentum (MA 200) | 17.5% | **Best Performer.** Strong trends, optimized to filter chops. |
| **BNB** | Hybrid | Mean Reversion | 20% | Very stable, acts like an index fund. |
| **DOGE**| Speculative | Momentum (MA 100) | 7.5% | High risk, but MA 100 filter removes most losses. |
| **AVAX**| Growth | Momentum | 10% | Diversification against SOL. |

## Maximizing Gains (The "Semi-Safe" Way)

1. **Re-optimize Monthly:** Market regimes change. Run the optimizer every month to adjust `RSI` and `MA` periods.
2. **Sentiment Filter:** The bot now checks the "Fear & Greed Index".
   - **Strategy:** When Index < 20 (Extreme Fear), the bot reduces position sizes automatically. **Do not override this.** It saves you from crashes.
3. **Compound Profits:** Leave profits in the account. The `RiskManager` automatically increases position sizes as the balance grows (fixed % risk).

## Warning Signs
- If **Correlation** between BTC and SOL > 0.9 for > 1 week, reduce SOL allocation.
- If **Sharpe Ratio** drops below 0.5 for any asset, disable it in `config/safe_list.py`.
