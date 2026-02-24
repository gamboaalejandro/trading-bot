# AI Trading Roadmap: From Rules to Reinforcement Learning

## 1. Introduction
The current bot uses **Rule-Based Strategies** (Momentum, Mean Reversion) optimized via Grid Search. This roadmap outlines the transition to **Machine Learning (ML)** and **Reinforcement Learning (RL)** to capture non-linear patterns and adapt to changing market regimes.

---

## 2. Data Collection (The Foundation)

Before training any model, we need a massive, clean dataset.

### A. OHLCV Data
- **Source:** Binance Historical Data (Klines)
- **Granularity:** 1m, 5m, 1h, 4h, 1d
- **Features to Engineer:**
  - Technical Indicators (RSI, MACD, Bollinger Bands, ATR, OBV)
  - Log Returns
  - Volatility (Rolling Std Dev)
  - Lagged features (t-1, t-2, t-5)

### B. Sentiment Data (The "Alpha")
- **Crypto Fear & Greed Index:** Daily historical data.
- **Social Volume:** Reddit/Twitter mentions (via LunarCrush or Santiment API).
- **News Sentiment:** BERT-based sentiment scoring of headlines from CryptoPanic.

### C. Market Microstructure
- **Order Book Imbalance:** (Bid Vol - Ask Vol) / (Bid Vol + Ask Vol)
- **Funding Rates:** (Futures only)

**Action Item:** Create a `DataCollector` service that runs daily and saves these features to a Parquet database (e.g., `data/historical.parquet`).

---

## 3. Phase 1: Supervised Learning (Prediction)

**Goal:** Predict the probability of price going UP or DOWN in the next $n$ periods.

### Model Architecture
- **LSTM / GRU (Recurrent Neural Networks):** Good for time-series sequences.
- **XGBoost / LightGBM:** Excellent for tabular data with engineered features.
- **Transformer (Time-Series):** State-of-the-art for capturing long-range dependencies.

### Target Variable
- **Binary Classification:** 1 if `Close[t+10] > Close[t] + Threshold`, else 0.
- **Regression:** Predict `log(Close[t+1] / Close[t])`.

### Evaluation
- **Accuracy / F1-Score:** Standard metrics.
- **Profitability Simulation:** If model says BUY, what is the PnL?

---

## 4. Phase 2: Reinforcement Learning (Decision Making)

**Goal:** Train an agent to *manage* trades (Entry, Exit, Size) to maximize Sharpe Ratio.

### Environment (`gym-trading-env`)
- **State:** [OHLCV window, Account Balance, Open Positions, Unrealized PnL, Sentiment Score]
- **Action:** [Hold, Buy 10%, Buy 50%, Sell 10%, Sell 100%]
- **Reward:** Change in Portfolio Value - Penalty for Drawdown.

### Algorithms
- **PPO (Proximal Policy Optimization):** Stable and standard for continuous control.
- **DQN (Deep Q-Network):** For discrete actions.
- **A2C (Advantage Actor-Critic).**

### Training Pipeline
1. **Train** on 2018-2023 data.
2. **Validate** on 2024 data (unseen).
3. **Stress Test** on "Crash Periods" (e.g., May 2021, Nov 2022).

---

## 5. Integration Plan

1. **Shadow Mode:** Run the AI model alongside the Rule-Based bot. Log its "decisions" without executing them.
2. **Ensemble:** Use the AI score as a *filter* for the Rule-Based strategies (e.g., if Momentum says BUY but AI says DOWN -> NO TRADE).
3. **Full Control:** Allow the AI to allocate capital dynamically.

---

## 6. Recommended Tech Stack

- **Data:** Pandas, Polars
- **ML:** PyTorch, Scikit-Learn, Stable-Baselines3 (for RL)
- **Backtesting:** Backtrader or Vectorbt (faster)
- **Deployment:** ONNX Runtime (for fast inference)

---

## 7. Next Steps for Developer

1. Implement `apps/analytics/data_collector.py`.
2. Collect 1 year of 5m data for BTC and SOL.
3. Train a simple XGBoost model to predict "Next Candle Green/Red".
4. Integrate the prediction as a `confidence_multiplier` in `StrategyManager`.
