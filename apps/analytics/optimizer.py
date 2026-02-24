"""
Strategy Optimizer - Grid Search Engine
Finds the best parameters to maximize Risk-Adjusted Returns (Sharpe Ratio).
"""
import logging
import itertools
import pandas as pd
from typing import Dict, List, Any

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.analytics.backtester import Backtester

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Optimizer")

class StrategyOptimizer:
    """
    Grid Search Optimizer for Trading Strategies.
    """

    def __init__(self, symbol: str, timeframe: str = '1h', limit: int = 1000):
        self.symbol = symbol
        self.backtester = Backtester(symbol, timeframe, limit)
        # Fetch data once
        self.backtester.fetch_data()

    def optimize_momentum(self) -> Dict[str, Any]:
        """
        Optimize Momentum Strategy parameters.
        Grid Search over:
        - RSI Period: [10, 14, 21]
        - MA Fast: [8, 10, 12, 20]
        - MA Slow: [21, 30, 50, 100, 200]
        """
        logger.info(f"Optimizing Momentum for {self.symbol}...")

        # Define Grid
        rsi_periods = [10, 14, 21]
        ma_fasts = [8, 10, 12, 20]
        ma_slows = [21, 30, 50, 100, 200]

        best_sharpe = -float('inf')
        best_params = {}
        best_metrics = {}

        total_combinations = len(rsi_periods) * len(ma_fasts) * len(ma_slows)
        count = 0

        for rsi, fast, slow in itertools.product(rsi_periods, ma_fasts, ma_slows):
            if fast >= slow:
                continue

            metrics = self.backtester.run_momentum(
                rsi_period=rsi,
                ma_fast=fast,
                ma_slow=slow
            )

            # Optimization Goal: Maximize Sharpe Ratio
            # Penalty for very low trade count (< 10) to avoid overfitting small samples
            sharpe = metrics['sharpe_ratio']
            if metrics['trades'] < 10:
                sharpe = -10

            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = {
                    'rsi_period': rsi,
                    'ma_fast': fast,
                    'ma_slow': slow
                }
                best_metrics = metrics

            count += 1
            if count % 10 == 0:
                print(f"Progress: {count}/{total_combinations}...", end='\r')

        logger.info(f"\n[DONE] Best Momentum Params: {best_params}")
        logger.info(f"Sharpe: {best_sharpe:.2f} | Return: {best_metrics['total_return']:.2%} | DD: {best_metrics['max_drawdown']:.2%}")

        return {
            'params': best_params,
            'metrics': best_metrics
        }

    def optimize_mean_reversion(self) -> Dict[str, Any]:
        """
        Optimize Mean Reversion Strategy parameters.
        Grid Search over:
        - RSI Period: [10, 14, 21]
        - BB Period: [20, 30]
        - BB Std: [1.5, 2.0, 2.5, 3.0]
        """
        logger.info(f"Optimizing Mean Reversion for {self.symbol}...")

        # Define Grid
        rsi_periods = [10, 14, 21]
        bb_periods = [20, 30]
        bb_stds = [1.5, 2.0, 2.5, 3.0]

        best_sharpe = -float('inf')
        best_params = {}
        best_metrics = {}

        total_combinations = len(rsi_periods) * len(bb_periods) * len(bb_stds)
        count = 0

        for rsi, bb_p, bb_s in itertools.product(rsi_periods, bb_periods, bb_stds):
            metrics = self.backtester.run_mean_reversion(
                rsi_period=rsi,
                bb_period=bb_p,
                bb_std=bb_s
            )

            # Optimization Goal: Maximize Sharpe Ratio
            sharpe = metrics['sharpe_ratio']
            if metrics['trades'] < 5:
                sharpe = -10

            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = {
                    'rsi_period': rsi,
                    'bb_period': bb_p,
                    'bb_std': bb_s
                }
                best_metrics = metrics

            count += 1
            if count % 5 == 0:
                print(f"Progress: {count}/{total_combinations}...", end='\r')

        logger.info(f"\n[DONE] Best Mean Reversion Params: {best_params}")
        logger.info(f"Sharpe: {best_sharpe:.2f} | Return: {best_metrics['total_return']:.2%} | DD: {best_metrics['max_drawdown']:.2%}")

        return {
            'params': best_params,
            'metrics': best_metrics
        }

if __name__ == "__main__":
    # Batch Optimization for Key Pairs
    pairs = ["BTC/USDT", "SOL/USDT", "DOGE/USDT"]

    for pair in pairs:
        print("\n" + "#"*60)
        print(f"OPTIMIZING {pair}")
        print("#"*60)

        opt = StrategyOptimizer(pair, timeframe="1h", limit=1000)

        print(f"\n--- Momentum ({pair}) ---")
        res_mom = opt.optimize_momentum()

        print(f"\n--- Mean Reversion ({pair}) ---")
        res_mr = opt.optimize_mean_reversion()

        print(f"\n>>> RECOMMENDATION FOR {pair} <<<")
        if res_mom['metrics']['sharpe_ratio'] > res_mr['metrics']['sharpe_ratio']:
            print(f"WINNER: MOMENTUM")
            print(f"Stats: Sharpe={res_mom['metrics']['sharpe_ratio']:.2f}, Ret={res_mom['metrics']['total_return']:.2%}")
            print(f"Optimal Params: {res_mom['params']}")
        else:
            print(f"WINNER: MEAN REVERSION")
            print(f"Stats: Sharpe={res_mr['metrics']['sharpe_ratio']:.2f}, Ret={res_mr['metrics']['total_return']:.2%}")
            print(f"Optimal Params: {res_mr['params']}")
