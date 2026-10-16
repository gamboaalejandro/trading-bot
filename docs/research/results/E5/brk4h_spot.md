# E5 — BRK4H spot

Generated 2026-10-15 23:03 UTC. Market: **spot**. Trials: `BRK4H-01`, `BRK4H-02`, `BRK4H-03`, `BRK4H-04`, `BRK4H-05`. Holdout: closed (not used).

## Warnings

- **Survivorship bias.** Every symbol of the universe is still listed in 2026; delisted coins (LUNA, FTT, SRM and others) are missing. Conclusions focus on BTC/ETH and every basket result carries this warning (PLAN §5.1).
- **Funding not verified.** The local funding is sampled at 00/08/16 UTC and may be the predicted rate, not the settled one; symbols moved to 4h/1h intervals are under-counted. P&L that depends on funding is UNVERIFIED until checked against `/fapi/v1/fundingRate` and `/fapi/v1/fundingInfo` (PLAN §2.7, §5.2.3, §8). BNBUSDT funding is excluded.
- Published figures (papers, debate) are not targets; only these OOS numbers count.

## Data provenance

- Harness git sha: `d6004c56aa38371f75ce52804982bd05409668ec`
- Data commits (upstream sources): futures `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, funding `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, spot `4d33a56f2b3930376fc778522770c6e84855be7e`
- Manifest digest: `409452ac0ee43d7964697c3c8fe9e8016ead6737aa100f3409b34293d37260fe`

<details><summary>CSV SHA-256 (19 files)</summary>

- `funding/ADAUSDT.csv`: `64411b95e03c131f132d153f844037612a726ef18c988180a912446e0b669eff`
- `funding/AVAXUSDT.csv`: `ff110bfb29dd6d60d6058cf0ed6da5d1489985f52ccde94454243484280e3ff5`
- `funding/BTCUSDT.csv`: `bed68ff8e480c6dc987dff31080cff2c612fa292bb33faa27db15b8146fd8b4a`
- `funding/DOGEUSDT.csv`: `a23583aeca171b437853fb2889d7f6f470b9d7afa5ff16d0ebb864316ffcedf0`
- `funding/DOTUSDT.csv`: `c524bd82553269714d0ddb0c033e284f6d5cfa11bdf56fa074fb71fe536b5ffa`
- `funding/ETHUSDT.csv`: `16542a31bca233c366d64dd054b5c9fe313362943db77d230aeacb4e0d2138fd`
- `funding/LINKUSDT.csv`: `970d7504d12f8d9c3426f48766fd42dd1300b100ebdf855c032888883e4cb51b`
- `funding/SOLUSDT.csv`: `bbc5852b0f57c0804ee51d1508f22f0fcd49356a77bc27ffddd858596ec7d830`
- `funding/XRPUSDT.csv`: `05071ac0c27a260619896a1497cfd691aa5ef2cd856dbb84c837e229fd8341cc`
- `spot/ADAUSDT_4h.csv`: `e086f9dcae40036885c071695f9be5a27d337590ba0993d6e1ae0493cd808720`
- `spot/AVAXUSDT_4h.csv`: `4c7a5fcb5a9632ab4ab801899b2e994edac4354ce681e5ef5da122c49d3c3e1d`
- `spot/BNBUSDT_4h.csv`: `58cabcedad8302e2ffa0de11052851fd0b0186191954812b1f4c25004ff0fe63`
- `spot/BTCUSDT_4h.csv`: `3fdca05b00339f1775998005dbcf0969aaca785f7205b57707463bb89df92b5c`
- `spot/DOGEUSDT_4h.csv`: `7725e5aad3eada58191e515b4183aaa5f0a3f96391dabbbac529c7f8ff1659b7`
- `spot/DOTUSDT_4h.csv`: `a1cab600c72b7ee7539ed9a93d4723955c2047b109676db40ff0c4d311c2876d`
- `spot/ETHUSDT_4h.csv`: `efa2d9429c2c4a0e0efc727d3b937b3d44880db9d493578144a108818f1a10b7`
- `spot/LINKUSDT_4h.csv`: `54826218f0534fd25036529b9354d24679b27321eaa8e4716dbaad177d602d6b`
- `spot/SOLUSDT_4h.csv`: `c23089c65df013bf2f1d5ec2d91cb58af1aebe03f33af1ef9693f06de8baccb6`
- `spot/XRPUSDT_4h.csv`: `91920e537adec956ae89811430839531106e297c90524b03d7ff571e4d805c10`

</details>

## Summary (OOS)

| series | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| OOS | 1529 | 9.61% | 2.22% | 6.52% | 0.368 | [-0.600, 1.169] | 0.636 | 8.87% | 0.250 | 0.74% | 1.117 |

| gross_mean | turnover_daily | n_trades_final_cfg |
|---|---|---|
| 0.048 | 0.007 | 1968 |

## Configurations (each alone, OOS)

| config | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | 1529 | 5.70% | 1.33% | 5.96% | 0.252 | [-0.668, 1.089] | 0.414 | 10.55% | 0.126 | 0.69% | 1.073 |
| B2 | 1529 | -3.92% | -0.95% | 4.23% | -0.205 | [-1.314, 0.821] | -0.302 | 11.40% | -0.083 | 0.57% | 0.943 |
| B3 | 1529 | 24.88% | 5.45% | 8.39% | 0.674 | [-0.231, 1.558] | 1.170 | 9.71% | 0.561 | 0.96% | 1.188 |
| B4 | 1529 | -6.26% | -1.53% | 4.47% | -0.323 | [-1.170, 0.507] | -0.467 | 9.99% | -0.153 | 0.60% | 0.917 |
| B5 | 1529 | 6.99% | 1.63% | 4.85% | 0.357 | [-0.524, 1.154] | 0.577 | 6.81% | 0.239 | 0.58% | 1.112 |

## Walk-forward selections (training only)

| fold | train_start | train_end | test_start | test_end | selected | test_days | train_sr[B1] | train_sr[B2] | train_sr[B3] | train_sr[B4] | train_sr[B5] |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2020-09-01 | 2021-12-31 | 2022-01-01 | 2022-03-31 | B5 | 90 | 1.590 | 1.672 | 1.469 | 1.543 | 1.676 |
| 1 | 2020-09-01 | 2022-03-31 | 2022-04-01 | 2022-06-30 | B5 | 91 | 1.400 | 1.492 | 1.344 | 1.368 | 1.519 |
| 2 | 2020-09-01 | 2022-06-30 | 2022-07-01 | 2022-09-30 | B2 | 92 | 1.234 | 1.350 | 1.107 | 1.217 | 1.342 |
| 3 | 2020-09-01 | 2022-09-30 | 2022-10-01 | 2022-12-31 | B2 | 92 | 1.003 | 1.126 | 0.847 | 1.015 | 1.112 |
| 4 | 2020-09-01 | 2022-12-31 | 2023-01-01 | 2023-03-31 | B2 | 90 | 0.945 | 1.110 | 0.761 | 0.958 | 1.084 |
| 5 | 2020-09-01 | 2023-03-31 | 2023-04-01 | 2023-06-30 | B5 | 91 | 0.783 | 0.749 | 0.781 | 0.645 | 0.932 |
| 6 | 2020-09-01 | 2023-06-30 | 2023-07-01 | 2023-09-30 | B5 | 92 | 0.759 | 0.713 | 0.592 | 0.579 | 0.839 |
| 7 | 2020-09-01 | 2023-09-30 | 2023-10-01 | 2023-12-31 | B5 | 92 | 0.734 | 0.705 | 0.524 | 0.549 | 0.759 |
| 8 | 2020-09-01 | 2023-12-31 | 2024-01-01 | 2024-03-31 | B2 | 91 | 0.961 | 1.085 | 0.791 | 0.668 | 0.968 |
| 9 | 2020-09-01 | 2024-03-31 | 2024-04-01 | 2024-06-30 | B2 | 91 | 1.036 | 1.158 | 0.981 | 0.573 | 1.075 |
| 10 | 2020-09-01 | 2024-06-30 | 2024-07-01 | 2024-09-30 | B5 | 92 | 0.805 | 0.884 | 0.801 | 0.432 | 0.899 |
| 11 | 2020-09-01 | 2024-09-30 | 2024-10-01 | 2024-12-31 | B5 | 92 | 0.586 | 0.625 | 0.630 | 0.330 | 0.716 |
| 12 | 2020-09-01 | 2024-12-31 | 2025-01-01 | 2025-03-31 | B3 | 90 | 0.590 | 0.585 | 0.802 | 0.357 | 0.741 |
| 13 | 2020-09-01 | 2025-03-31 | 2025-04-01 | 2025-06-30 | B3 | 91 | 0.694 | 0.601 | 0.872 | 0.414 | 0.767 |
| 14 | 2020-09-01 | 2025-06-30 | 2025-07-01 | 2025-09-30 | B3 | 92 | 0.546 | 0.418 | 0.760 | 0.343 | 0.624 |
| 15 | 2020-09-01 | 2025-09-30 | 2025-10-01 | 2025-12-31 | B3 | 92 | 0.612 | 0.410 | 0.869 | 0.381 | 0.729 |
| 16 | 2020-09-01 | 2025-12-31 | 2026-01-01 | 2026-03-09 | B3 | 68 | 0.643 | 0.422 | 0.891 | 0.390 | 0.745 |

## By year

| year | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | 365 | -1.48% | -1.48% | 1.73% | -0.852 | [-2.451, 0.701] | -1.179 | 2.31% | -0.642 | 0.24% | 0.733 |
| 2023 | 365 | 0.66% | 0.66% | 5.12% | 0.153 | [-2.452, 2.027] | 0.270 | 6.66% | 0.099 | 0.56% | 1.038 |
| 2024 | 366 | -2.60% | -2.59% | 4.87% | -0.515 | [-3.746, 1.388] | -0.783 | 7.89% | -0.328 | 0.63% | 0.878 |
| 2025 | 365 | 13.70% | 13.70% | 11.19% | 1.203 | [-0.340, 2.484] | 2.142 | 8.87% | 1.545 | 1.27% | 1.345 |
| 2026 | 68 | -0.19% | -1.01% | 0.44% | -2.317 | [-4.074, 0.000] | -2.317 | 0.19% | -5.346 | 0.05% | 0.000 |

## By symbol

_Single series: no per-symbol breakdown available._

## By regime (ex-ante cell: trend_BTC x vol tercile)

| regime | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| down_high | 100 | 0.00% | 0.00% | 0.00% | n/a | [n/a, n/a] | n/a | 0.00% | n/a | -0.00% | n/a |
| down_low | 298 | -0.69% | -0.84% | 2.29% | -0.358 | [-1.975, 1.046] | -0.542 | 2.02% | -0.416 | 0.30% | 0.886 |
| down_mid | 277 | -0.41% | -0.54% | 0.48% | -1.124 | [-2.662, 1.040] | -1.322 | 0.52% | -1.032 | 0.06% | 0.510 |
| up_high | 20 | 0.00% | 0.05% | 0.65% | 0.087 | [n/a, n/a] | 0.128 | 0.10% | 0.529 | 0.05% | 1.030 |
| up_low | 662 | 13.79% | 7.38% | 9.66% | 0.786 | [-0.442, 1.910] | 1.376 | 8.87% | 0.832 | 1.06% | 1.194 |
| up_mid | 172 | -2.61% | -5.45% | 3.14% | -1.766 | [-4.690, 1.009] | -2.302 | 3.02% | -1.805 | 0.47% | 0.672 |

## Costs (USDT, final configuration)

| commission | slippage | funding |
|---|---|---|
| 1529.357 | 917.420 | 0.000 |

## Mandatory stress (PLAN §5.4; not new trials)

| run | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cost_x2 | 1529 | -2.39% | -0.58% | 6.27% | -0.061 | [-1.012, 0.724] | -0.098 | 9.73% | -0.059 | 0.76% | 0.982 |
| delay_1 | 1529 | 21.85% | 4.83% | 7.51% | 0.665 | [-0.327, 1.521] | 1.174 | 8.97% | 0.538 | 0.82% | 1.236 |
| worst_bar | 1529 | -7.91% | -1.95% | 3.71% | -0.511 | [-1.419, 0.294] | -0.731 | 11.61% | -0.168 | 0.50% | 0.858 |

## Benchmarks

| benchmark | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B&H BTC (vol-matched) | 1529 | 11.79% | 2.70% | 6.52% | 0.440 | [-0.538, 1.486] | 0.643 | 11.46% | 0.235 | 0.78% | 1.070 |
| B&H basket (vol-matched) | 1529 | 4.51% | 1.06% | 6.52% | 0.194 | [-0.766, 1.275] | 0.271 | 9.73% | 0.109 | 0.81% | 1.028 |

## Random entries

- Candidate Sharpe 0.379, 95th percentile of 100 random draws 0.199, percentile 99.000.

## Tail events (2021-05-19, 2022-11-09, 2025-10-10)

| config | day | return | gross_prev_close | stops_filled | stops_gapped | stop_slip_bps | liquidations | ret_cost_x2 | ret_delay_1 | ret_worst_bar | stops_filled_worst_bar | stops_total | liq_rejected_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | 2021-05-19 | -0.002 | 0.014 | 1 | 0 | 10.469 | 0 | -0.002 | -0.011 | -0.003 | 1 | 367 | — |
| B1 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 367 | — |
| B1 | 2025-10-10 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 367 | — |
| B2 | 2021-05-19 | -0.002 | 0.014 | 1 | 0 | 10.469 | 0 | -0.002 | -0.003 | -0.003 | 1 | 411 | — |
| B2 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 411 | — |
| B2 | 2025-10-10 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 411 | — |
| B3 | 2021-05-19 | -0.003 | 0.030 | 1 | 0 | 10.469 | 0 | -0.003 | -0.014 | -0.004 | 1 | 549 | — |
| B3 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 549 | — |
| B3 | 2025-10-10 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 549 | — |
| B4 | 2021-05-19 | -0.002 | 0.014 | 1 | 0 | 10.469 | 0 | -0.002 | -0.011 | -0.003 | 1 | 494 | — |
| B4 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 494 | — |
| B4 | 2025-10-10 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 494 | — |
| B5 | 2021-05-19 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 289 | — |
| B5 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 289 | — |
| B5 | 2025-10-10 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | 0 | 289 | — |

## Gate (PLAN §5.6)

**Level: C**

| level | check | status | value | threshold | detail |
|---|---|---|---|---|---|
| A | dsr | fail | 0.241 | 0.950 | N=21, V[SR]=0.000368/day |
| A | pbo | pass | 0.088 | 0.300 |  |
| A | random_entries | pass | 0.379 | 0.199 | 100 random draws |
| A | vs_bh | fail | BTC: 0.547, basket: 0.365 | 0.050 | one-sided p |
| A | no_catastrophe | fail | n/a | dSR>-1SE, DD<=B&H | 2022/BTC: ok dSR=0.44 (SE 1.31), MaxDD 2.3% vs B&H 11.5%; 2022/basket: ok dSR=0.37 (SE 1.28), MaxDD 2.3% vs B&H 9.7%; 2023-24/BTC: FAIL dSR=-2.19 (SE 0.79), MaxDD 7.9% vs B&H 3.2%; 2023-24/basket: FAIL dSR=-1.85 (SE 0.78), MaxDD 7.9% vs B&H 4.5%; 2025-26/BTC: FAIL dSR=1.44 (SE 1.11), MaxDD 8.9% vs B&H 7.8%; 2025-26/basket: FAIL dSR=1.57 (SE 1.03), MaxDD 8.9% vs B&H 8.3% |
| A | cost_stress | fail | -0.061 | >0 and >= 50% of 0.37 |  |
| A | delay_stress | pass | 0.665 | >= 50% of 0.37 |  |
| A | frozen_spot | n/a | n/a | n/a | not a daily family |
| A | max_dd | pass | 0.089 | 0.200 |  |
| A | holdout | pending | n/a | n/a | holdout not opened (E9) |
| A | significance | fail | 0.754 | 3.000 | t=0.75; trades 421 vs needed 932 |
| B | pbo | pass | 0.088 | 0.300 |  |
| B | random_entries | pass | 0.379 | 0.199 | 100 random draws |
| B | cost_stress | fail | -0.061 | > 0 |  |
| B | frozen_spot | n/a | n/a | n/a | not a daily family |
| B | psr | fail | 0.780 | 0.900 |  |
| B | adaptability | fail | -0.866 | > 0 |  |

## Adaptability A_k (PLAN §3.3)

| A_k | q20 | penalty | frac_positive | worst_regime | worst_regime_cvar95 | tau2 | n_cells | t_years | N_eff (PR) | N_eff n/(1+(n-1)rho) |
|---|---|---|---|---|---|---|---|---|---|---|
| -0.866 | -0.475 | 0.391 | 0.000 | up_low | 0.011 | 0.000 | 5 | 4.189 | 1.000 | 1.000 |

## Simulated kill-switch (user limits; whole run from the training anchor)

| config | run | halted_on | days_halted | days_block_entries | days_flatten_leveraged | days_half_risk | max_dd_run |
|---|---|---|---|---|---|---|---|
| B1 | base | - | 0 | 2 | 0 | 19 | 10.55% |
| B2 | base | - | 0 | 0 | 0 | 262 | 11.40% |
| B3 | base | - | 0 | 3 | 0 | 0 | 9.71% |
| B4 | base | - | 0 | 2 | 0 | 962 | 13.89% |
| B5 | base | - | 0 | 1 | 0 | 0 | 6.81% |
| B1 | cost_x2 | - | 0 | 1 | 0 | 414 | 11.61% |
| B2 | cost_x2 | - | 0 | 0 | 0 | 763 | 12.86% |
| B3 | cost_x2 | - | 0 | 3 | 0 | 566 | 13.63% |
| B4 | cost_x2 | - | 0 | 2 | 0 | 1132 | 16.23% |
| B5 | cost_x2 | - | 0 | 1 | 0 | 0 | 9.20% |
| B1 | delay_1 | - | 0 | 2 | 0 | 504 | 12.54% |
| B2 | delay_1 | - | 0 | 0 | 0 | 401 | 11.69% |
| B3 | delay_1 | - | 0 | 2 | 0 | 547 | 12.95% |
| B4 | delay_1 | - | 0 | 1 | 0 | 1145 | 15.09% |
| B5 | delay_1 | - | 0 | 1 | 0 | 0 | 9.02% |
| B1 | worst_bar | - | 0 | 1 | 0 | 1251 | 16.35% |
| B2 | worst_bar | 2025-08-20 | 202 | 1 | 0 | 1306 | 20.05% |
| B3 | worst_bar | - | 0 | 2 | 0 | 1418 | 18.65% |
| B4 | worst_bar | 2024-05-30 | 649 | 3 | 0 | 1287 | 20.02% |
| B5 | worst_bar | - | 0 | 1 | 0 | 1049 | 14.73% |

## Frozen spot 2017-2020

_not applicable_
