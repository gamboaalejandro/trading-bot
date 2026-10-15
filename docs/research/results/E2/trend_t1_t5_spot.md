# E2 — TREND T1-T5 spot

Generated 2026-10-15 21:51 UTC. Market: **spot**. Trials: `TREND-01`, `TREND-02`, `TREND-03`, `TREND-04`, `TREND-05`. Holdout: closed (not used).

## Warnings

- **Survivorship bias.** Every symbol of the universe is still listed in 2026; delisted coins (LUNA, FTT, SRM and others) are missing. Conclusions focus on BTC/ETH and every basket result carries this warning (PLAN §5.1).
- Published figures (papers, debate) are not targets; only these OOS numbers count.

## Data provenance

- Harness git sha: `c60c2a25b92fe5e7933af812547ea94bfd07883e`
- Data commits (upstream sources): futures `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, funding `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, spot `4d33a56f2b3930376fc778522770c6e84855be7e`
- Manifest digest: `d37784f18b2b5c51c51330b62b95b786f0a4cc20a2587681e1326e40a6da6e2c`

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
- `spot/ADAUSDT_1d.csv`: `b3acd5f72498d72449a4692eedf9963092827fd62345db3c510dafa68362c64b`
- `spot/AVAXUSDT_1d.csv`: `2b117fb6848226ecec76a3ad94825e9ffa9a75f87f5be9aefb763ae611b475a7`
- `spot/BTCUSDT_1d.csv`: `a8b34b72f3e9434e02929658d495db6dd872789eff6faf8c89282ec56c6807d0`
- `spot/DOGEUSDT_1d.csv`: `703025b51ebd1cb11b4ba412031b42c7067a45283f2789cc3a9ccb9362dda664`
- `spot/DOTUSDT_1d.csv`: `fcebf79b88207de5bb255d7aee72659a94f02d5841291f39d15d9c9ef68393e8`
- `spot/ETHUSDT_1d.csv`: `647b97d96833b426484e5674db3f2d6ee149dffa32f21aec927fad82ccfa84c7`
- `spot/LINKUSDT_1d.csv`: `45b75b4886fed76a1430b00c9a29b1cc6c0bc50600c0fe7825dc11514267b1df`
- `spot/SOLUSDT_1d.csv`: `2408659f4e1a6420c6b53f448d3d379a84befdb70e8324b306bf4320e6ef71d8`
- `spot/XRPUSDT_1d.csv`: `61c0e6747f56636396e5a632b6b3514907b9ed3ebca45fcfee370e31b783606c`

</details>

## Summary (OOS)

| series | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| OOS | 1529 | 16.21% | 3.65% | 9.21% | 0.436 | [-0.826, 1.698] | 0.645 | 16.21% | 0.225 | 1.17% | 1.089 |

| gross_mean | turnover_daily | n_trades_final_cfg |
|---|---|---|
| 0.088 | 0.028 | 3142 |

## Configurations (each alone, OOS)

| config | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | 1529 | 16.21% | 3.65% | 9.21% | 0.436 | [-0.826, 1.698] | 0.645 | 16.21% | 0.225 | 1.17% | 1.089 |
| T2 | 1529 | -0.37% | -0.09% | 8.81% | 0.034 | [-1.221, 1.287] | 0.048 | 19.08% | -0.005 | 1.10% | 1.006 |
| T3 | 1529 | 16.09% | 3.62% | 9.85% | 0.411 | [-0.876, 1.673] | 0.607 | 18.22% | 0.199 | 1.22% | 1.080 |
| T4 | 1529 | 28.31% | 6.13% | 12.14% | 0.551 | [-0.735, 1.808] | 0.827 | 19.92% | 0.308 | 1.43% | 1.112 |
| T5 | 1529 | 17.13% | 3.85% | 9.81% | 0.434 | [-0.834, 1.705] | 0.640 | 17.71% | 0.217 | 1.21% | 1.084 |

## Walk-forward selections (training only)

| fold | train_start | train_end | test_start | test_end | selected | test_days | train_sr[T1] | train_sr[T2] | train_sr[T3] | train_sr[T4] | train_sr[T5] |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2020-09-01 | 2021-12-31 | 2022-01-01 | 2022-03-31 | T1 | 90 | 1.462 | 0.760 | 1.090 | 1.154 | 1.088 |
| 1 | 2020-09-01 | 2022-03-31 | 2022-04-01 | 2022-06-30 | T1 | 91 | 1.230 | 0.651 | 0.900 | 0.909 | 0.842 |
| 2 | 2020-09-01 | 2022-06-30 | 2022-07-01 | 2022-09-30 | T1 | 92 | 0.947 | 0.429 | 0.571 | 0.611 | 0.509 |
| 3 | 2020-09-01 | 2022-09-30 | 2022-10-01 | 2022-12-31 | T1 | 92 | 0.894 | 0.442 | 0.601 | 0.615 | 0.550 |
| 4 | 2020-09-01 | 2022-12-31 | 2023-01-01 | 2023-03-31 | T1 | 90 | 0.809 | 0.386 | 0.529 | 0.535 | 0.473 |
| 5 | 2020-09-01 | 2023-03-31 | 2023-04-01 | 2023-06-30 | T1 | 91 | 0.804 | 0.432 | 0.593 | 0.659 | 0.579 |
| 6 | 2020-09-01 | 2023-06-30 | 2023-07-01 | 2023-09-30 | T1 | 92 | 0.744 | 0.380 | 0.507 | 0.579 | 0.479 |
| 7 | 2020-09-01 | 2023-09-30 | 2023-10-01 | 2023-12-31 | T1 | 92 | 0.699 | 0.374 | 0.491 | 0.564 | 0.470 |
| 8 | 2020-09-01 | 2023-12-31 | 2024-01-01 | 2024-03-31 | T1 | 91 | 1.149 | 0.712 | 0.983 | 1.098 | 0.998 |
| 9 | 2020-09-01 | 2024-03-31 | 2024-04-01 | 2024-06-30 | T1 | 91 | 1.144 | 0.641 | 1.003 | 1.112 | 1.013 |
| 10 | 2020-09-01 | 2024-06-30 | 2024-07-01 | 2024-09-30 | T1 | 92 | 1.054 | 0.518 | 0.894 | 0.992 | 0.894 |
| 11 | 2020-09-01 | 2024-09-30 | 2024-10-01 | 2024-12-31 | T1 | 92 | 0.934 | 0.452 | 0.779 | 0.893 | 0.778 |
| 12 | 2020-09-01 | 2024-12-31 | 2025-01-01 | 2025-03-31 | T1 | 90 | 1.131 | 0.607 | 0.996 | 1.081 | 1.011 |
| 13 | 2020-09-01 | 2025-03-31 | 2025-04-01 | 2025-06-30 | T1 | 91 | 0.943 | 0.482 | 0.826 | 0.914 | 0.830 |
| 14 | 2020-09-01 | 2025-06-30 | 2025-07-01 | 2025-09-30 | T1 | 92 | 0.933 | 0.470 | 0.807 | 0.901 | 0.809 |
| 15 | 2020-09-01 | 2025-09-30 | 2025-10-01 | 2025-12-31 | T1 | 92 | 0.912 | 0.464 | 0.786 | 0.897 | 0.803 |
| 16 | 2020-09-01 | 2025-12-31 | 2026-01-01 | 2026-03-09 | T1 | 68 | 0.851 | 0.379 | 0.691 | 0.802 | 0.702 |

## By year

| year | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | 365 | -8.03% | -8.03% | 7.29% | -1.112 | [-2.852, 0.449] | -1.485 | 11.41% | -0.704 | 1.03% | 0.803 |
| 2023 | 365 | 26.85% | 26.85% | 10.55% | 2.308 | [-0.259, 4.373] | 3.900 | 4.58% | 5.857 | 1.17% | 1.499 |
| 2024 | 366 | 12.51% | 12.47% | 11.60% | 1.071 | [-1.984, 3.688] | 1.648 | 11.71% | 1.064 | 1.39% | 1.232 |
| 2025 | 365 | -8.69% | -8.69% | 7.18% | -1.231 | [-3.055, 0.710] | -1.505 | 9.28% | -0.936 | 1.08% | 0.779 |
| 2026 | 68 | -3.03% | -15.24% | 3.72% | -4.428 | [-7.296, -1.411] | -5.084 | 3.96% | -3.852 | 0.51% | 0.398 |

## By symbol

Daily contribution of each symbol to the portfolio return (net of its costs).

| symbol | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 1529 | 1.42% | 0.34% | 1.34% | 0.257 | [-0.915, 1.225] | 0.403 | 2.78% | 0.121 | 0.16% | 1.093 |
| ETHUSDT | 1529 | 1.24% | 0.29% | 1.49% | 0.204 | [-0.667, 1.085] | 0.296 | 2.43% | 0.121 | 0.18% | 1.069 |
| SOLUSDT | 1529 | 5.20% | 1.22% | 2.26% | 0.546 | [-0.597, 1.800] | 0.859 | 3.80% | 0.320 | 0.26% | 1.184 |
| XRPUSDT | 1529 | 7.76% | 1.80% | 2.40% | 0.755 | [-0.394, 1.814] | 1.349 | 3.25% | 0.555 | 0.24% | 1.318 |
| ADAUSDT | 1529 | 0.08% | 0.02% | 1.91% | 0.020 | [-1.453, 1.292] | 0.029 | 4.28% | 0.004 | 0.24% | 1.006 |
| DOGEUSDT | 1529 | 1.88% | 0.44% | 2.26% | 0.208 | [-1.353, 1.141] | 0.368 | 3.78% | 0.118 | 0.21% | 1.088 |
| AVAXUSDT | 1529 | 1.80% | 0.43% | 1.55% | 0.282 | [-1.137, 1.582] | 0.437 | 3.26% | 0.131 | 0.19% | 1.087 |
| LINKUSDT | 1529 | 1.83% | 0.43% | 1.78% | 0.252 | [-0.707, 1.038] | 0.420 | 3.45% | 0.125 | 0.21% | 1.080 |
| DOTUSDT | 1529 | -4.42% | -1.07% | 2.30% | -0.457 | [-1.484, 0.446] | -0.595 | 9.32% | -0.115 | 0.27% | 0.847 |

## By regime (ex-ante cell: trend_BTC x vol tercile)

| regime | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| down_high | 100 | -2.75% | -9.68% | 2.01% | -5.050 | [-7.331, -2.245] | -5.187 | 2.77% | -3.488 | 0.38% | 0.175 |
| down_low | 298 | -6.49% | -7.89% | 6.18% | -1.299 | [-3.100, 0.728] | -1.613 | 7.97% | -0.991 | 0.94% | 0.785 |
| down_mid | 277 | -2.08% | -2.73% | 6.57% | -0.389 | [-2.125, 1.309] | -0.572 | 5.36% | -0.510 | 0.86% | 0.922 |
| up_high | 20 | 0.00% | 0.00% | 0.00% | n/a | [n/a, n/a] | n/a | 0.00% | n/a | -0.00% | n/a |
| up_low | 662 | 36.09% | 18.52% | 11.55% | 1.529 | [-0.218, 3.143] | 2.380 | 7.89% | 2.347 | 1.38% | 1.303 |
| up_mid | 172 | -4.10% | -8.50% | 9.97% | -0.842 | [-3.747, 2.216] | -1.136 | 8.52% | -0.998 | 1.39% | 0.836 |

## Costs (USDT, final configuration)

| commission | slippage | funding |
|---|---|---|
| 723.549 | 565.137 | 0.000 |

## Mandatory stress (PLAN §5.4; not new trials)

| run | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cost_x2 | 1529 | 11.37% | 2.60% | 9.06% | 0.329 | [-0.940, 1.561] | 0.491 | 16.61% | 0.157 | 1.14% | 1.066 |
| delay_1 | 1529 | 10.01% | 2.30% | 9.40% | 0.289 | [-0.893, 1.444] | 0.425 | 13.61% | 0.169 | 1.21% | 1.057 |
| worst_bar | 1529 | 8.25% | 1.91% | 9.21% | 0.252 | [-0.958, 1.481] | 0.361 | 16.71% | 0.114 | 1.18% | 1.052 |

## Benchmarks

| benchmark | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B&H BTC (vol-matched) | 1529 | 16.42% | 3.70% | 9.21% | 0.440 | [-0.538, 1.486] | 0.643 | 15.89% | 0.233 | 1.11% | 1.070 |
| B&H basket (vol-matched) | 1529 | 5.04% | 1.18% | 9.21% | 0.173 | [-0.792, 1.255] | 0.244 | 13.80% | 0.086 | 1.13% | 1.025 |

## Random entries

- Candidate Sharpe 0.478, 95th percentile of 100 random draws 0.536, percentile 92.000.

## Tail events (2021-05-19, 2022-11-09, 2025-10-10)

| config | day | return | gross_prev_close | stops_filled | stops_gapped | stop_slip_bps | liquidations | ret_cost_x2 | ret_delay_1 | ret_worst_bar | stops_filled_worst_bar | stops_total | liq_rejected_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | 2021-05-19 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 117 | 0 |
| T1 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | -0.019 | 0.000 | 0 | 117 | 0 |
| T1 | 2025-10-10 | -0.000 | 0.040 | 0 | 0 | n/a | 0 | -0.000 | -0.007 | -0.000 | 0 | 117 | 0 |
| T2 | 2021-05-19 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 137 | 0 |
| T2 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | -0.012 | 0.000 | 0 | 137 | 0 |
| T2 | 2025-10-10 | -0.008 | 0.093 | 1 | 0 | 30.000 | 0 | 0.000 | -0.009 | -0.076 | 1 | 137 | 0 |
| T3 | 2021-05-19 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 136 | 0 |
| T3 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | -0.031 | 0.000 | 0 | 136 | 0 |
| T3 | 2025-10-10 | -0.004 | 0.083 | 1 | 0 | 30.000 | 0 | -0.005 | -0.017 | -0.038 | 1 | 136 | 0 |
| T4 | 2021-05-19 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 136 | 0 |
| T4 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | -0.021 | 0.000 | 0 | 136 | 0 |
| T4 | 2025-10-10 | -0.004 | 0.083 | 1 | 0 | 30.000 | 0 | -0.005 | -0.009 | 0.000 | 0 | 136 | 0 |
| T5 | 2021-05-19 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 136 | 0 |
| T5 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | -0.031 | 0.000 | 0 | 136 | 0 |
| T5 | 2025-10-10 | -0.004 | 0.083 | 1 | 0 | 30.000 | 0 | -0.005 | -0.016 | -0.038 | 1 | 136 | 0 |

## Gate (PLAN §5.6)

**Level: C**

| level | check | status | value | threshold | detail |
|---|---|---|---|---|---|
| A | dsr | fail | 0.581 | 0.950 | N=13, V[SR]=0.000107/day |
| A | pbo | fail | 0.375 | 0.300 |  |
| A | random_entries | fail | 0.478 | 0.536 | 100 random draws |
| A | vs_bh | fail | BTC: 0.491, basket: 0.263 | 0.050 | one-sided p |
| A | no_catastrophe | fail | n/a | dSR>-1SE, DD<=B&H | 2022/BTC: ok dSR=0.18 (SE 1.01), MaxDD 11.4% vs B&H 15.9%; 2022/basket: ok dSR=0.15 (SE 0.95), MaxDD 11.4% vs B&H 13.8%; 2023-24/BTC: FAIL dSR=-0.36 (SE 0.66), MaxDD 11.7% vs B&H 4.5%; 2023-24/basket: FAIL dSR=-0.00 (SE 0.51), MaxDD 11.7% vs B&H 6.5%; 2025-26/BTC: FAIL dSR=-1.14 (SE 0.98), MaxDD 12.0% vs B&H 10.8%; 2025-26/basket: FAIL dSR=-0.97 (SE 0.85), MaxDD 12.0% vs B&H 11.9% |
| A | cost_stress | pass | 0.329 | >0 and >= 50% of 0.44 |  |
| A | delay_stress | pass | 0.289 | >= 50% of 0.44 |  |
| A | frozen_spot | pass | sharpe: 1.397, max_dd: 0.095 | SR>0, DD<=10.8% |  |
| A | max_dd | pass | 0.162 | 0.200 |  |
| A | holdout | pending | n/a | n/a | holdout not opened (E9) |
| A | significance | fail | 0.891 | 3.000 | t=0.89 |
| B | pbo | fail | 0.375 | 0.300 |  |
| B | random_entries | fail | 0.478 | 0.536 | 100 random draws |
| B | cost_stress | pass | 0.329 | > 0 |  |
| B | frozen_spot | pass | n/a | no catastrophe | dSR=0.60 (SE 0.69), MaxDD 9.5% vs B&H 10.8% |
| B | psr | fail | 0.814 | 0.900 |  |
| B | adaptability | fail | -0.905 | > 0 |  |

## Adaptability A_k (PLAN §3.3)

| A_k | q20 | penalty | frac_positive | worst_regime | worst_regime_cvar95 | tau2 | n_cells | t_years | N_eff (PR) | N_eff n/(1+(n-1)rho) |
|---|---|---|---|---|---|---|---|---|---|---|
| -0.905 | -0.856 | 0.049 | 0.289 | up_low | 0.013 | 0.968 | 45 | 4.189 | 6.760 | 3.691 |

## Simulated kill-switch (user limits; whole run from the training anchor)

| config | run | halted_on | days_halted | days_block_entries | days_flatten_leveraged | days_half_risk | max_dd_run |
|---|---|---|---|---|---|---|---|
| T1 | base | - | 0 | 10 | 0 | 946 | 16.21% |
| T2 | base | - | 0 | 11 | 0 | 1147 | 19.08% |
| T3 | base | - | 0 | 11 | 0 | 997 | 18.22% |
| T4 | base | - | 0 | 20 | 1 | 1117 | 19.92% |
| T5 | base | - | 0 | 11 | 0 | 1010 | 17.71% |
| T1 | cost_x2 | - | 0 | 9 | 0 | 988 | 16.61% |
| T2 | cost_x2 | 2023-06-07 | 1007 | 3 | 0 | 1526 | 20.04% |
| T3 | cost_x2 | - | 0 | 11 | 0 | 1073 | 19.24% |
| T4 | cost_x2 | 2026-02-26 | 12 | 17 | 1 | 1164 | 20.06% |
| T5 | cost_x2 | - | 0 | 11 | 0 | 1073 | 19.24% |
| T1 | delay_1 | - | 0 | 10 | 0 | 904 | 14.44% |
| T2 | delay_1 | 2026-02-22 | 16 | 13 | 0 | 1162 | 20.58% |
| T3 | delay_1 | - | 0 | 15 | 1 | 1011 | 19.69% |
| T4 | delay_1 | 2026-02-18 | 20 | 22 | 1 | 1244 | 20.07% |
| T5 | delay_1 | - | 0 | 15 | 1 | 1014 | 19.04% |
| T1 | worst_bar | - | 0 | 14 | 0 | 1096 | 16.71% |
| T2 | worst_bar | 2025-11-03 | 127 | 12 | 1 | 1257 | 20.44% |
| T3 | worst_bar | 2026-01-20 | 49 | 15 | 1 | 1124 | 20.07% |
| T4 | worst_bar | 2022-09-15 | 1272 | 10 | 1 | 1544 | 20.16% |
| T5 | worst_bar | 2026-01-20 | 49 | 15 | 1 | 1141 | 20.04% |

## Frozen spot 2017-2020 (frozen configuration T1)

| series | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| candidate | 751 | 34.20% | 15.37% | 10.64% | 1.397 | [-0.001, 2.490] | 2.267 | 9.55% | 1.610 | 1.27% | 1.349 |
| B&H BTC vol-matched | 751 | 17.70% | 8.24% | 10.64% | 0.798 | [-0.665, 2.058] | 1.129 | 10.77% | 0.765 | 1.27% | 1.143 |

## Frozen spot 2017-2020, every configuration (informative; gate uses the final one)

| series | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | 751 | 34.20% | 15.37% | 10.64% | 1.397 | [-0.001, 2.490] | 2.267 | 9.55% | 1.610 | 1.27% | 1.349 |
| T2 | 751 | -8.52% | -4.24% | 7.28% | -0.558 | [-2.018, 0.644] | -0.767 | 15.28% | -0.277 | 0.99% | 0.886 |
| T3 | 751 | -4.48% | -2.20% | 8.02% | -0.237 | [-1.591, 0.846] | -0.334 | 13.28% | -0.166 | 1.09% | 0.948 |
| T4 | 751 | -4.52% | -2.22% | 9.28% | -0.196 | [-1.505, 0.944] | -0.271 | 14.29% | -0.155 | 1.29% | 0.956 |
| T5 | 751 | -3.81% | -1.87% | 8.12% | -0.192 | [-1.587, 0.950] | -0.272 | 13.62% | -0.137 | 1.09% | 0.958 |
| B&H BTC vol-matched (final) | 751 | 17.70% | 8.24% | 10.64% | 0.798 | [-0.665, 2.058] | 1.129 | 10.77% | 0.765 | 1.27% | 1.143 |

## Notes

- T3 is the primary preregistered configuration.
- The perp run (L = 1) reports the funding cost; it is not a new trial.
