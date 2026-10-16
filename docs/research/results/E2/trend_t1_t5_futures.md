# E2 — TREND T1-T5 futures

Generated 2026-10-15 22:09 UTC. Market: **futures**. Trials: `TREND-01`, `TREND-02`, `TREND-03`, `TREND-04`, `TREND-05`. Holdout: closed (not used).

## Warnings

- **Survivorship bias.** Every symbol of the universe is still listed in 2026; delisted coins (LUNA, FTT, SRM and others) are missing. Conclusions focus on BTC/ETH and every basket result carries this warning (PLAN §5.1).
- **Funding not verified.** The local funding is sampled at 00/08/16 UTC and may be the predicted rate, not the settled one; symbols moved to 4h/1h intervals are under-counted. P&L that depends on funding is UNVERIFIED until checked against `/fapi/v1/fundingRate` and `/fapi/v1/fundingInfo` (PLAN §2.7, §5.2.3, §8). BNBUSDT funding is excluded.
- Published figures (papers, debate) are not targets; only these OOS numbers count.

## Data provenance

- Harness git sha: `c60c2a25b92fe5e7933af812547ea94bfd07883e`
- Data commits (upstream sources): futures `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, funding `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, spot `4d33a56f2b3930376fc778522770c6e84855be7e`
- Manifest digest: `438da63967d4bb72ed21e3fd890853d72407c7406d979d893026850809f1a9d4`

<details><summary>CSV SHA-256 (18 files)</summary>

- `funding/ADAUSDT.csv`: `64411b95e03c131f132d153f844037612a726ef18c988180a912446e0b669eff`
- `funding/AVAXUSDT.csv`: `ff110bfb29dd6d60d6058cf0ed6da5d1489985f52ccde94454243484280e3ff5`
- `funding/BTCUSDT.csv`: `bed68ff8e480c6dc987dff31080cff2c612fa292bb33faa27db15b8146fd8b4a`
- `funding/DOGEUSDT.csv`: `a23583aeca171b437853fb2889d7f6f470b9d7afa5ff16d0ebb864316ffcedf0`
- `funding/DOTUSDT.csv`: `c524bd82553269714d0ddb0c033e284f6d5cfa11bdf56fa074fb71fe536b5ffa`
- `funding/ETHUSDT.csv`: `16542a31bca233c366d64dd054b5c9fe313362943db77d230aeacb4e0d2138fd`
- `funding/LINKUSDT.csv`: `970d7504d12f8d9c3426f48766fd42dd1300b100ebdf855c032888883e4cb51b`
- `funding/SOLUSDT.csv`: `bbc5852b0f57c0804ee51d1508f22f0fcd49356a77bc27ffddd858596ec7d830`
- `funding/XRPUSDT.csv`: `05071ac0c27a260619896a1497cfd691aa5ef2cd856dbb84c837e229fd8341cc`
- `futures/ADAUSDT_1d.csv`: `80135a2a0743772a0c8cc7d0f564305e033b139c4b69f3f066cad01b921727b2`
- `futures/AVAXUSDT_1d.csv`: `fa9476c6cbd92a8ffee5f10dd40df6928fafc6b7204904822f117f6a494543a3`
- `futures/BTCUSDT_1d.csv`: `9a28da68ff94306ad603e2d32729bfe472cdcd9b99bff2fea3ec916bd6879d7e`
- `futures/DOGEUSDT_1d.csv`: `01431fd6d06b3035fd044c20d222270bcbe56d19e26c962ff1a3e9241736ac07`
- `futures/DOTUSDT_1d.csv`: `29af13c1b42b2d1de36dc505a45bbdbfd558c7d35231212ad94ae5ef59ddc612`
- `futures/ETHUSDT_1d.csv`: `5e888c4bdc2e31fb5afc212623248de855984db98b1e1adcb53515f50ea12662`
- `futures/LINKUSDT_1d.csv`: `5a61bf6272a2b2b682da1f15b25c37d7b6cdfe79ed44cd2123fe8edcce22fc4d`
- `futures/SOLUSDT_1d.csv`: `6e2942eb6e7057b1ccc9cd1e232c42d69a0de2387432c9cf8ca10c58a8e9a3d8`
- `futures/XRPUSDT_1d.csv`: `fb6f6533b18c91ea5e0494ab3659f4f849980ae32fc9c3cb2ae59f0d7baf03e7`

</details>

## Summary (OOS)

| series | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| OOS | 1529 | 17.78% | 3.98% | 10.53% | 0.424 | [-0.872, 1.658] | 0.630 | 19.08% | 0.209 | 1.23% | 1.086 |

| gross_mean | turnover_daily | n_trades_final_cfg |
|---|---|---|
| 0.105 | 0.040 | 4367 |

## Configurations (each alone, OOS)

| config | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | 1529 | 14.16% | 3.21% | 9.16% | 0.391 | [-0.867, 1.660] | 0.573 | 15.85% | 0.203 | 1.16% | 1.082 |
| T2 | 1529 | -2.15% | -0.52% | 8.45% | -0.019 | [-1.264, 1.188] | -0.027 | 18.18% | -0.029 | 1.07% | 0.996 |
| T3 | 1529 | 14.61% | 3.31% | 9.95% | 0.377 | [-0.869, 1.598] | 0.560 | 17.59% | 0.188 | 1.22% | 1.073 |
| T4 | 1529 | 29.07% | 6.28% | 12.09% | 0.564 | [-0.708, 1.772] | 0.852 | 19.08% | 0.329 | 1.44% | 1.114 |
| T5 | 1529 | 16.60% | 3.73% | 9.90% | 0.420 | [-0.864, 1.637] | 0.627 | 17.69% | 0.211 | 1.21% | 1.082 |

## Walk-forward selections (training only)

| fold | train_start | train_end | test_start | test_end | selected | test_days | train_sr[T1] | train_sr[T2] | train_sr[T3] | train_sr[T4] | train_sr[T5] |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2020-09-01 | 2021-12-31 | 2022-01-01 | 2022-03-31 | T2 | 90 | -0.285 | -0.120 | -0.302 | -0.259 | -0.303 |
| 1 | 2020-09-01 | 2022-03-31 | 2022-04-01 | 2022-06-30 | T2 | 91 | -0.396 | -0.215 | -0.406 | -0.480 | -0.450 |
| 2 | 2020-09-01 | 2022-06-30 | 2022-07-01 | 2022-09-30 | T2 | 92 | -0.789 | -0.737 | -0.940 | -0.921 | -0.945 |
| 3 | 2020-09-01 | 2022-09-30 | 2022-10-01 | 2022-12-31 | T2 | 92 | -0.647 | -0.515 | -0.658 | -0.703 | -0.663 |
| 4 | 2020-09-01 | 2022-12-31 | 2023-01-01 | 2023-03-31 | T2 | 90 | -0.685 | -0.539 | -0.660 | -0.709 | -0.671 |
| 5 | 2020-09-01 | 2023-03-31 | 2023-04-01 | 2023-06-30 | T2 | 91 | -0.503 | -0.308 | -0.404 | -0.330 | -0.414 |
| 6 | 2020-09-01 | 2023-06-30 | 2023-07-01 | 2023-09-30 | T2 | 92 | -0.490 | -0.360 | -0.485 | -0.416 | -0.478 |
| 7 | 2020-09-01 | 2023-09-30 | 2023-10-01 | 2023-12-31 | T2 | 92 | -0.480 | -0.288 | -0.437 | -0.347 | -0.422 |
| 8 | 2020-09-01 | 2023-12-31 | 2024-01-01 | 2024-03-31 | T4 | 91 | 0.505 | 0.555 | 0.534 | 0.654 | 0.576 |
| 9 | 2020-09-01 | 2024-03-31 | 2024-04-01 | 2024-06-30 | T4 | 91 | 0.558 | 0.365 | 0.614 | 0.710 | 0.647 |
| 10 | 2020-09-01 | 2024-06-30 | 2024-07-01 | 2024-09-30 | T4 | 92 | 0.462 | 0.151 | 0.480 | 0.563 | 0.505 |
| 11 | 2020-09-01 | 2024-09-30 | 2024-10-01 | 2024-12-31 | T4 | 92 | 0.272 | 0.059 | 0.342 | 0.437 | 0.361 |
| 12 | 2020-09-01 | 2024-12-31 | 2025-01-01 | 2025-03-31 | T4 | 90 | 0.626 | 0.341 | 0.653 | 0.783 | 0.699 |
| 13 | 2020-09-01 | 2025-03-31 | 2025-04-01 | 2025-06-30 | T4 | 91 | 0.387 | 0.124 | 0.443 | 0.585 | 0.486 |
| 14 | 2020-09-01 | 2025-06-30 | 2025-07-01 | 2025-09-30 | T4 | 92 | 0.401 | 0.127 | 0.436 | 0.587 | 0.477 |
| 15 | 2020-09-01 | 2025-09-30 | 2025-10-01 | 2025-12-31 | T4 | 92 | 0.398 | 0.151 | 0.427 | 0.589 | 0.463 |
| 16 | 2020-09-01 | 2025-12-31 | 2026-01-01 | 2026-03-09 | T4 | 68 | 0.337 | 0.018 | 0.319 | 0.481 | 0.352 |

## By year

| year | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | 365 | -7.37% | -7.37% | 5.88% | -1.271 | [-3.470, 0.546] | -1.722 | 9.45% | -0.780 | 0.75% | 0.810 |
| 2023 | 365 | 25.69% | 25.69% | 9.84% | 2.373 | [-0.054, 4.206] | 4.066 | 3.90% | 6.595 | 1.01% | 1.505 |
| 2024 | 366 | 17.57% | 17.52% | 15.61% | 1.112 | [-1.794, 3.552] | 1.717 | 14.27% | 1.228 | 1.78% | 1.249 |
| 2025 | 365 | -10.86% | -10.86% | 8.88% | -1.250 | [-3.411, 0.697] | -1.554 | 11.71% | -0.928 | 1.28% | 0.792 |
| 2026 | 68 | -3.48% | -17.29% | 6.61% | -2.839 | [-6.409, 0.380] | -3.846 | 5.30% | -3.260 | 0.74% | 0.591 |

## By symbol

Daily contribution of each symbol to the portfolio return (net of its costs).

| symbol | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 1529 | 4.01% | 0.94% | 1.72% | 0.554 | [-0.493, 1.583] | 0.825 | 3.29% | 0.286 | 0.19% | 1.191 |
| ETHUSDT | 1529 | -2.68% | -0.65% | 1.52% | -0.418 | [-1.189, 0.515] | -0.522 | 4.22% | -0.153 | 0.19% | 0.864 |
| SOLUSDT | 1529 | 8.65% | 2.00% | 1.98% | 1.012 | [0.005, 1.955] | 1.698 | 2.11% | 0.947 | 0.23% | 1.298 |
| XRPUSDT | 1529 | 5.96% | 1.39% | 2.64% | 0.537 | [-0.809, 1.751] | 0.904 | 4.17% | 0.334 | 0.27% | 1.206 |
| ADAUSDT | 1529 | 2.76% | 0.65% | 1.92% | 0.347 | [-0.959, 1.411] | 0.573 | 2.99% | 0.218 | 0.23% | 1.105 |
| DOGEUSDT | 1529 | 11.03% | 2.53% | 4.28% | 0.604 | [-1.049, 1.387] | 1.214 | 4.32% | 0.585 | 0.25% | 1.384 |
| AVAXUSDT | 1529 | 3.44% | 0.81% | 1.85% | 0.445 | [-0.736, 1.601] | 0.676 | 2.64% | 0.307 | 0.22% | 1.124 |
| LINKUSDT | 1529 | 0.84% | 0.20% | 1.78% | 0.121 | [-0.872, 0.967] | 0.195 | 3.53% | 0.056 | 0.21% | 1.033 |
| DOTUSDT | 1529 | -5.49% | -1.34% | 1.84% | -0.724 | [-1.462, 0.227] | -0.851 | 7.49% | -0.179 | 0.23% | 0.791 |

## By regime (ex-ante cell: trend_BTC x vol tercile)

| regime | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| down_high | 112 | -3.78% | -11.79% | 4.54% | -2.740 | [-5.346, -0.225] | -3.439 | 3.86% | -3.056 | 0.64% | 0.577 |
| down_low | 317 | -3.09% | -3.55% | 6.07% | -0.565 | [-2.935, 1.496] | -0.765 | 6.36% | -0.558 | 0.80% | 0.915 |
| down_mid | 246 | -1.35% | -1.99% | 5.86% | -0.314 | [-2.343, 1.439] | -0.475 | 3.89% | -0.511 | 0.65% | 0.948 |
| up_high | 32 | 0.71% | 8.43% | 4.49% | 1.824 | [-4.289, 4.734] | 4.180 | 0.46% | 18.194 | 0.38% | 1.748 |
| up_low | 614 | 29.20% | 16.45% | 13.74% | 1.177 | [-0.566, 2.777] | 1.824 | 13.26% | 1.241 | 1.58% | 1.233 |
| up_mid | 208 | -1.61% | -2.81% | 12.10% | -0.175 | [-3.226, 2.264] | -0.236 | 9.30% | -0.302 | 1.60% | 0.962 |

## Costs (USDT, final configuration)

| commission | slippage | funding |
|---|---|---|
| 385.454 | 302.239 | -716.766 |

## Mandatory stress (PLAN §5.4; not new trials)

| run | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cost_x2 | 1529 | 4.01% | 0.94% | 10.07% | 0.144 | [-1.095, 1.336] | 0.208 | 20.06% | 0.047 | 1.19% | 1.028 |
| delay_1 | 1529 | 8.98% | 2.07% | 10.78% | 0.244 | [-0.988, 1.403] | 0.355 | 19.94% | 0.104 | 1.31% | 1.048 |
| worst_bar | 1529 | 8.17% | 1.89% | 5.16% | 0.389 | [-0.836, 1.587] | 0.586 | 10.69% | 0.177 | 0.66% | 1.101 |
| funding_x0.5 | 1529 | 20.20% | 4.49% | 10.76% | 0.462 | [-0.854, 1.704] | 0.686 | 19.45% | 0.231 | 1.27% | 1.094 |
| funding_x2 | 1529 | 9.94% | 2.29% | 10.28% | 0.271 | [-0.958, 1.445] | 0.397 | 19.20% | 0.119 | 1.21% | 1.054 |

## Benchmarks

| benchmark | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B&H BTC (vol-matched) | 1529 | 18.65% | 4.17% | 10.53% | 0.440 | [-0.537, 1.484] | 0.643 | 17.99% | 0.232 | 1.27% | 1.070 |
| B&H basket (vol-matched) | 1529 | 5.77% | 1.35% | 10.53% | 0.180 | [-0.787, 1.255] | 0.253 | 15.41% | 0.087 | 1.29% | 1.026 |

## Random entries

- Candidate Sharpe 0.617, 95th percentile of 100 random draws 0.416, percentile 97.000.

## Tail events (2021-05-19, 2022-11-09, 2025-10-10)

| config | day | return | gross_prev_close | stops_filled | stops_gapped | stop_slip_bps | liquidations | ret_cost_x2 | ret_delay_1 | ret_worst_bar | stops_filled_worst_bar | ret_funding_x0.5 | ret_funding_x2 | stops_total | liq_rejected_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | 2021-05-19 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 104 | 0 |
| T1 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | -0.019 | 0.000 | 0 | 0.000 | 0.000 | 104 | 0 |
| T1 | 2025-10-10 | -0.000 | 0.040 | 0 | 0 | n/a | 0 | -0.000 | -0.007 | -0.000 | 0 | -0.000 | -0.000 | 104 | 0 |
| T2 | 2021-05-19 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 135 | 0 |
| T2 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | -0.012 | 0.000 | 0 | 0.000 | 0.000 | 135 | 0 |
| T2 | 2025-10-10 | -0.008 | 0.093 | 1 | 0 | 10.000 | 0 | -0.008 | -0.009 | -0.069 | 1 | -0.008 | -0.008 | 135 | 0 |
| T3 | 2021-05-19 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 125 | 0 |
| T3 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | -0.031 | 0.000 | 0 | 0.000 | 0.000 | 125 | 0 |
| T3 | 2025-10-10 | -0.004 | 0.083 | 1 | 0 | 10.000 | 0 | -0.004 | -0.016 | -0.034 | 1 | -0.004 | -0.004 | 125 | 0 |
| T4 | 2021-05-19 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 125 | 0 |
| T4 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | -0.021 | 0.000 | 0 | 0.000 | 0.000 | 125 | 0 |
| T4 | 2025-10-10 | -0.004 | 0.083 | 1 | 0 | 10.000 | 0 | -0.004 | -0.016 | 0.000 | 0 | -0.004 | -0.004 | 125 | 0 |
| T5 | 2021-05-19 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 125 | 0 |
| T5 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | -0.031 | 0.000 | 0 | 0.000 | 0.000 | 125 | 0 |
| T5 | 2025-10-10 | -0.004 | 0.083 | 1 | 0 | 10.000 | 0 | -0.004 | -0.016 | -0.034 | 1 | -0.004 | -0.004 | 125 | 0 |

## Gate (PLAN §5.6)

**Level: C**

| level | check | status | value | threshold | detail |
|---|---|---|---|---|---|
| A | dsr | fail | 0.543 | 0.950 | N=13, V[SR]=0.00013/day |
| A | pbo | pass | 0.137 | 0.300 |  |
| A | random_entries | pass | 0.617 | 0.416 | 100 random draws |
| A | vs_bh | fail | BTC: 0.498, basket: 0.258 | 0.050 | one-sided p |
| A | no_catastrophe | fail | n/a | dSR>-1SE, DD<=B&H | 2022/BTC: ok dSR=0.01 (SE 0.89), MaxDD 9.4% vs B&H 18.0%; 2022/basket: ok dSR=-0.04 (SE 0.82), MaxDD 9.4% vs B&H 15.4%; 2023-24/BTC: FAIL dSR=-0.45 (SE 0.66), MaxDD 14.3% vs B&H 5.2%; 2023-24/basket: FAIL dSR=-0.10 (SE 0.52), MaxDD 14.3% vs B&H 7.4%; 2025-26/BTC: FAIL dSR=-1.09 (SE 0.96), MaxDD 14.8% vs B&H 12.3%; 2025-26/basket: FAIL dSR=-0.92 (SE 0.80), MaxDD 14.8% vs B&H 13.4% |
| A | cost_stress | fail | 0.144 | >0 and >= 50% of 0.42 |  |
| A | delay_stress | pass | 0.244 | >= 50% of 0.42 |  |
| A | frozen_spot | fail | sharpe: -0.196, max_dd: 0.143 | SR>0, DD<=9.4% |  |
| A | max_dd | pass | 0.191 | 0.200 |  |
| A | holdout | pending | n/a | n/a | holdout not opened (E9) |
| A | significance | fail | 0.867 | 3.000 | t=0.87 |
| B | pbo | pass | 0.137 | 0.300 |  |
| B | random_entries | pass | 0.617 | 0.416 | 100 random draws |
| B | cost_stress | pass | 0.144 | > 0 |  |
| B | frozen_spot | fail | n/a | no catastrophe | dSR=-0.99 (SE 0.74), MaxDD 14.3% vs B&H 9.4% |
| B | psr | fail | 0.807 | 0.900 |  |
| B | adaptability | fail | -0.388 | > 0 |  |

## Adaptability A_k (PLAN §3.3)

| A_k | q20 | penalty | frac_positive | worst_regime | worst_regime_cvar95 | tau2 | n_cells | t_years | N_eff (PR) | N_eff n/(1+(n-1)rho) |
|---|---|---|---|---|---|---|---|---|---|---|
| -0.388 | -0.242 | 0.147 | 0.148 | up_low | 0.015 | 0.209 | 54 | 4.189 | 5.990 | 3.359 |

## Simulated kill-switch (user limits; whole run from the training anchor)

| config | run | halted_on | days_halted | days_block_entries | days_flatten_leveraged | days_half_risk | max_dd_run |
|---|---|---|---|---|---|---|---|
| T1 | base | - | 0 | 7 | 0 | 953 | 15.85% |
| T2 | base | - | 0 | 10 | 0 | 1187 | 18.18% |
| T3 | base | - | 0 | 9 | 0 | 953 | 17.59% |
| T4 | base | - | 0 | 16 | 0 | 1058 | 19.08% |
| T5 | base | - | 0 | 9 | 0 | 974 | 17.69% |
| T1 | cost_x2 | - | 0 | 7 | 0 | 946 | 16.01% |
| T2 | cost_x2 | - | 0 | 8 | 0 | 1264 | 19.10% |
| T3 | cost_x2 | - | 0 | 9 | 0 | 1020 | 18.06% |
| T4 | cost_x2 | 2026-03-07 | 3 | 14 | 0 | 1103 | 20.06% |
| T5 | cost_x2 | - | 0 | 9 | 0 | 1022 | 18.16% |
| T1 | delay_1 | - | 0 | 6 | 0 | 794 | 13.73% |
| T2 | delay_1 | - | 0 | 10 | 0 | 1306 | 19.33% |
| T3 | delay_1 | - | 0 | 12 | 0 | 959 | 17.83% |
| T4 | delay_1 | - | 0 | 17 | 0 | 1084 | 19.94% |
| T5 | delay_1 | - | 0 | 12 | 0 | 964 | 18.08% |
| T1 | worst_bar | - | 0 | 7 | 1 | 1121 | 16.41% |
| T2 | worst_bar | 2025-10-16 | 145 | 8 | 1 | 1414 | 20.06% |
| T3 | worst_bar | 2026-02-27 | 11 | 12 | 1 | 1163 | 20.24% |
| T4 | worst_bar | 2022-07-11 | 1338 | 2 | 1 | 1566 | 20.07% |
| T5 | worst_bar | 2026-01-29 | 40 | 11 | 2 | 1145 | 20.08% |
| T1 | funding_x0.5 | - | 0 | 8 | 0 | 923 | 15.68% |
| T2 | funding_x0.5 | - | 0 | 10 | 0 | 1171 | 18.27% |
| T3 | funding_x0.5 | - | 0 | 9 | 0 | 938 | 17.39% |
| T4 | funding_x0.5 | - | 0 | 17 | 0 | 1041 | 19.45% |
| T5 | funding_x0.5 | - | 0 | 10 | 0 | 965 | 17.64% |
| T1 | funding_x2 | - | 0 | 8 | 0 | 953 | 15.90% |
| T2 | funding_x2 | - | 0 | 9 | 0 | 1236 | 18.74% |
| T3 | funding_x2 | - | 0 | 9 | 0 | 997 | 17.75% |
| T4 | funding_x2 | - | 0 | 15 | 0 | 1090 | 19.20% |
| T5 | funding_x2 | - | 0 | 8 | 0 | 1007 | 17.29% |

## Frozen spot 2017-2020 (frozen configuration T4)

| series | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| candidate | 751 | -4.52% | -2.22% | 9.28% | -0.196 | [-1.505, 0.944] | -0.271 | 14.29% | -0.155 | 1.29% | 0.956 |
| B&H BTC vol-matched | 751 | 15.42% | 7.22% | 9.28% | 0.798 | [-0.665, 2.058] | 1.129 | 9.45% | 0.764 | 1.11% | 1.143 |

## Frozen spot 2017-2020, every configuration (informative; gate uses the final one)

| series | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | 751 | 34.20% | 15.37% | 10.64% | 1.397 | [-0.001, 2.490] | 2.267 | 9.55% | 1.610 | 1.27% | 1.349 |
| T2 | 751 | -8.52% | -4.24% | 7.28% | -0.558 | [-2.018, 0.644] | -0.767 | 15.28% | -0.277 | 0.99% | 0.886 |
| T3 | 751 | -4.48% | -2.20% | 8.02% | -0.237 | [-1.591, 0.846] | -0.334 | 13.28% | -0.166 | 1.09% | 0.948 |
| T4 | 751 | -4.52% | -2.22% | 9.28% | -0.196 | [-1.505, 0.944] | -0.271 | 14.29% | -0.155 | 1.29% | 0.956 |
| T5 | 751 | -3.81% | -1.87% | 8.12% | -0.192 | [-1.587, 0.950] | -0.272 | 13.62% | -0.137 | 1.09% | 0.958 |
| B&H BTC vol-matched (final) | 751 | 15.42% | 7.22% | 9.28% | 0.798 | [-0.665, 2.058] | 1.129 | 9.45% | 0.764 | 1.11% | 1.143 |

## Notes

- T3 is the primary preregistered configuration.
- The perp run (L = 1) reports the funding cost; it is not a new trial.
