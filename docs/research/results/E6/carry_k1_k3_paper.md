# E6 — CARRY K1-K3 (paper)

Generated 2026-10-15 22:21 UTC. Market: **futures**. Trials: `CARRY-01`, `CARRY-02`, `CARRY-03`. Holdout: closed (not used).

## Warnings

- **Survivorship bias.** Every symbol of the universe is still listed in 2026; delisted coins (LUNA, FTT, SRM and others) are missing. Conclusions focus on BTC/ETH and every basket result carries this warning (PLAN §5.1).
- **Funding not verified.** The local funding is sampled at 00/08/16 UTC and may be the predicted rate, not the settled one; symbols moved to 4h/1h intervals are under-counted. P&L that depends on funding is UNVERIFIED until checked against `/fapi/v1/fundingRate` and `/fapi/v1/fundingInfo` (PLAN §2.7, §5.2.3, §8). BNBUSDT funding is excluded.
- Published figures (papers, debate) are not targets; only these OOS numbers count.

## Data provenance

- Harness git sha: `d6004c56aa38371f75ce52804982bd05409668ec`
- Data commits (upstream sources): futures `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, funding `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, spot `4d33a56f2b3930376fc778522770c6e84855be7e`
- Manifest digest: `bc0d179888ee0b8c8a40b71a02e7e28ebc512609726d08290fafbf177211310a`

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
- `spot/ADAUSDT_4h.csv`: `e086f9dcae40036885c071695f9be5a27d337590ba0993d6e1ae0493cd808720`
- `spot/AVAXUSDT_4h.csv`: `4c7a5fcb5a9632ab4ab801899b2e994edac4354ce681e5ef5da122c49d3c3e1d`
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
| OOS | 1528 | 0.65% | 0.16% | 1.12% | 0.145 | [-0.534, 3.600] | 0.148 | 2.27% | 0.069 | 0.04% | 1.214 |

| gross_mean | turnover_daily | n_trades_final_cfg |
|---|---|---|
| 0.035 | 0.001 | 244 |

## Configurations (each alone, OOS)

| config | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| K1 | 1528 | 2.64% | 0.63% | 1.12% | 0.563 | [-0.404, 4.570] | 0.589 | 2.27% | 0.275 | 0.04% | 1.941 |
| K2 | 1528 | 1.33% | 0.32% | 1.29% | 0.251 | [-0.476, 4.757] | 0.256 | 2.44% | 0.129 | 0.05% | 1.322 |
| K3 | 1528 | 1.88% | 0.45% | 0.42% | 1.053 | [-0.097, 3.194] | 1.199 | 0.57% | 0.786 | 0.02% | 2.224 |

## Walk-forward selections (training only)

| fold | train_start | train_end | test_start | test_end | selected | test_days | train_sr[K1] | train_sr[K2] | train_sr[K3] |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 2020-09-01 | 2021-12-31 | 2022-01-01 | 2022-03-31 | K3 | 90 | 2.988 | 2.684 | 3.365 |
| 1 | 2020-09-01 | 2022-03-31 | 2022-04-01 | 2022-06-30 | K3 | 91 | 2.741 | 2.469 | 3.084 |
| 2 | 2020-09-01 | 2022-06-30 | 2022-07-01 | 2022-09-30 | K3 | 92 | 2.544 | 2.292 | 2.861 |
| 3 | 2020-09-01 | 2022-09-30 | 2022-10-01 | 2022-12-31 | K3 | 92 | 2.383 | 2.147 | 2.679 |
| 4 | 2020-09-01 | 2022-12-31 | 2023-01-01 | 2023-03-31 | K3 | 90 | 2.248 | 2.026 | 2.528 |
| 5 | 2020-09-01 | 2023-03-31 | 2023-04-01 | 2023-06-30 | K3 | 91 | 2.167 | 1.962 | 2.402 |
| 6 | 2020-09-01 | 2023-06-30 | 2023-07-01 | 2023-09-30 | K3 | 92 | 2.059 | 1.868 | 2.292 |
| 7 | 2020-09-01 | 2023-09-30 | 2023-10-01 | 2023-12-31 | K3 | 92 | 1.972 | 1.789 | 2.195 |
| 8 | 2020-09-01 | 2023-12-31 | 2024-01-01 | 2024-03-31 | K3 | 91 | 2.030 | 1.874 | 2.180 |
| 9 | 2020-09-01 | 2024-03-31 | 2024-04-01 | 2024-06-30 | K1 | 91 | 2.496 | 1.919 | 2.274 |
| 10 | 2020-09-01 | 2024-06-30 | 2024-07-01 | 2024-09-30 | K1 | 92 | 2.450 | 1.880 | 2.223 |
| 11 | 2020-09-01 | 2024-09-30 | 2024-10-01 | 2024-12-31 | K1 | 92 | 2.372 | 1.821 | 2.153 |
| 12 | 2020-09-01 | 2024-12-31 | 2025-01-01 | 2025-03-31 | K3 | 90 | 1.613 | 1.356 | 2.039 |
| 13 | 2020-09-01 | 2025-03-31 | 2025-04-01 | 2025-06-30 | K3 | 91 | 1.569 | 1.320 | 1.983 |
| 14 | 2020-09-01 | 2025-06-30 | 2025-07-01 | 2025-09-30 | K3 | 92 | 1.528 | 1.285 | 1.931 |
| 15 | 2020-09-01 | 2025-09-30 | 2025-10-01 | 2025-12-31 | K3 | 92 | 1.489 | 1.253 | 1.882 |
| 16 | 2020-09-01 | 2025-12-31 | 2026-01-01 | 2026-03-09 | K3 | 67 | 1.454 | 1.223 | 1.836 |

## By year

| year | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | 365 | 0.00% | 0.00% | 0.00% | n/a | [n/a, n/a] | n/a | 0.00% | n/a | -0.00% | n/a |
| 2023 | 365 | 0.48% | 0.48% | 0.16% | 2.951 | [-0.445, 5.362] | 9.287 | 0.07% | 7.020 | 0.00% | 7.542 |
| 2024 | 366 | 0.17% | 0.17% | 2.28% | 0.087 | [-1.179, 7.137] | 0.089 | 2.27% | 0.076 | 0.16% | 1.064 |
| 2025 | 365 | 0.00% | 0.00% | 0.00% | n/a | [n/a, n/a] | n/a | 0.00% | n/a | -0.00% | n/a |
| 2026 | 67 | 0.00% | 0.00% | 0.00% | n/a | [n/a, n/a] | n/a | 0.00% | n/a | -0.00% | n/a |

## By symbol

_Single series: no per-symbol breakdown available._

## By regime (ex-ante cell: trend_BTC x vol tercile)

| regime | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| down_high | 100 | 0.00% | 0.00% | 0.00% | n/a | [n/a, n/a] | n/a | 0.00% | n/a | -0.00% | n/a |
| down_low | 298 | 0.00% | 0.00% | 0.00% | n/a | [n/a, n/a] | n/a | 0.00% | n/a | -0.00% | n/a |
| down_mid | 276 | 0.00% | 0.00% | 0.00% | n/a | [n/a, n/a] | n/a | 0.00% | n/a | -0.00% | n/a |
| up_high | 20 | 0.07% | 1.20% | 0.23% | 5.288 | [n/a, n/a] | 9.012 | 0.04% | 28.977 | 0.02% | 2.579 |
| up_low | 662 | 1.34% | 0.73% | 0.45% | 1.628 | [0.166, 5.219] | 1.941 | 0.57% | 1.291 | 0.02% | 2.723 |
| up_mid | 172 | -0.74% | -1.56% | 3.22% | -0.474 | [-2.100, 10.450] | -0.479 | 2.21% | -0.709 | 0.26% | 0.695 |

## Costs (USDT, final configuration)

| commission | slippage | funding |
|---|---|---|
| 474.861 | 101.594 | 2311.309 |

## Mandatory stress (PLAN §5.4; not new trials)

| run | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cost_x2 | 1528 | 0.09% | 0.02% | 1.14% | 0.024 | [-0.620, 2.840] | 0.024 | 2.47% | 0.008 | 0.05% | 1.031 |
| funding_x0.5 | 1528 | -1.30% | -0.31% | 1.11% | -0.274 | [-0.752, 2.354] | -0.276 | 2.36% | -0.132 | 0.04% | 0.628 |
| funding_x2 | 1528 | 4.65% | 1.09% | 1.15% | 0.950 | [-0.165, 4.640] | 1.014 | 2.18% | 0.500 | 0.04% | 2.598 |

## Benchmarks

| benchmark | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B&H BTC (vol-matched) | 1528 | 1.97% | 0.47% | 1.12% | 0.424 | [-0.534, 1.445] | 0.618 | 2.03% | 0.230 | 0.13% | 1.067 |
| B&H basket (vol-matched) | 1528 | 0.74% | 0.18% | 1.12% | 0.163 | [-0.802, 1.185] | 0.229 | 1.73% | 0.102 | 0.14% | 1.024 |

## Random entries

- Candidate Sharpe 0.497, 95th percentile of 100 random draws 0.840, percentile 78.000.

## Tail events (2021-05-19, 2022-11-09, 2025-10-10)

| config | day | return | gross_prev_close | stops_filled | stops_gapped | stop_slip_bps | liquidations | ret_cost_x2 | ret_funding_x0.5 | ret_funding_x2 | stops_total | liq_rejected_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| K1 | 2021-05-19 | -0.001 | 0.331 | 0 | 0 | n/a | 0 | -0.001 | -0.001 | -0.001 | — | — |
| K1 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | — | — |
| K1 | 2025-10-10 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | — | — |
| K2 | 2021-05-19 | -0.001 | 0.335 | 0 | 0 | n/a | 0 | -0.001 | -0.001 | -0.001 | — | — |
| K2 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | — | — |
| K2 | 2025-10-10 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | — | — |
| K3 | 2021-05-19 | -0.002 | 0.368 | 0 | 0 | n/a | 0 | -0.002 | -0.001 | -0.002 | — | — |
| K3 | 2022-11-09 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | — | — |
| K3 | 2025-10-10 | 0.000 | 0.000 | 0 | 0 | n/a | 0 | 0.000 | 0.000 | 0.000 | — | — |

## Gate (PLAN §5.6)

**Level: C**

| level | check | status | value | threshold | detail |
|---|---|---|---|---|---|
| A | dsr | fail | 0.210 | 0.950 | N=21, V[SR]=0.000258/day |
| A | pbo | fail | 1.000 | 0.300 |  |
| A | random_entries | fail | 0.497 | 0.840 | 100 random draws |
| A | vs_bh | fail | BTC: 0.668, basket: 0.536 | 0.050 | one-sided p |
| A | no_catastrophe | fail | n/a | dSR>-1SE, DD<=B&H | 2022/BTC: FAIL dSR=nan (SE nan), MaxDD 0.0% vs B&H 2.0%; 2022/basket: FAIL dSR=nan (SE nan), MaxDD 0.0% vs B&H 1.7%; 2023-24/BTC: FAIL dSR=-1.81 (SE 0.99), MaxDD 2.3% vs B&H 0.6%; 2023-24/basket: FAIL dSR=-1.45 (SE 1.02), MaxDD 2.3% vs B&H 0.8%; 2025-26/BTC: FAIL dSR=nan (SE nan), MaxDD 0.0% vs B&H 1.4%; 2025-26/basket: FAIL dSR=nan (SE nan), MaxDD 0.0% vs B&H 1.5% |
| A | cost_stress | fail | 0.024 | >0 and >= 50% of 0.14 |  |
| A | delay_stress | fail | n/a | >= 50% of 0.14 | +1 bar delay run missing |
| A | frozen_spot | n/a | n/a | n/a | not a daily family |
| A | max_dd | pass | 0.023 | 0.200 |  |
| A | holdout | pending | n/a | n/a | holdout not opened (E9) |
| A | significance | fail | 0.296 | 3.000 | t=0.30 |
| B | pbo | fail | 1.000 | 0.300 |  |
| B | random_entries | fail | 0.497 | 0.840 | 100 random draws |
| B | cost_stress | pass | 0.024 | > 0 |  |
| B | frozen_spot | n/a | n/a | n/a | not a daily family |
| B | psr | fail | 0.603 | 0.900 |  |
| B | adaptability | pass | 1.647 | > 0 |  |

## Adaptability A_k (PLAN §3.3)

| A_k | q20 | penalty | frac_positive | worst_regime | worst_regime_cvar95 | tau2 | n_cells | t_years | N_eff (PR) | N_eff n/(1+(n-1)rho) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.647 | 1.744 | 0.098 | 1.000 | up_mid | 0.003 | 0.274 | 3 | 4.186 | 1.000 | 1.000 |

## Simulated kill-switch (user limits; whole run from the training anchor)

_no kill-switch data_

## Frozen spot 2017-2020

_not applicable_

## Notes

- unverified P&L: local funding not checked against /fapi/v1/fundingRate and /fapi/v1/fundingInfo (PLAN §2.7, §8)
- PAPER ONLY. The +1 bar delay stress is not supported by the carry simulator, so the delay check of the gate fails by construction.
