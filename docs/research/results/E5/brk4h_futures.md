# E5 — BRK4H futures

Generated 2026-10-16 02:00 UTC. Market: **futures**. Trials: `BRK4H-01`, `BRK4H-02`, `BRK4H-03`, `BRK4H-04`, `BRK4H-05`. Holdout: closed (not used).

## Warnings

- **Survivorship bias.** Every symbol of the universe is still listed in 2026; delisted coins (LUNA, FTT, SRM and others) are missing. Conclusions focus on BTC/ETH and every basket result carries this warning (PLAN §5.1).
- **Funding not verified.** The local funding is sampled at 00/08/16 UTC and may be the predicted rate, not the settled one; symbols moved to 4h/1h intervals are under-counted. P&L that depends on funding is UNVERIFIED until checked against `/fapi/v1/fundingRate` and `/fapi/v1/fundingInfo` (PLAN §2.7, §5.2.3, §8). BNBUSDT funding is excluded.
- Published figures (papers, debate) are not targets; only these OOS numbers count.

## Data provenance

- Harness git sha: `aa96cd7603efce574a8673f0e6944606e83e4e15`
- Data commits (upstream sources): futures `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, funding `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, spot `4d33a56f2b3930376fc778522770c6e84855be7e`
- Manifest digest: `b7812d94b720b4d48b1c954c434388d4fc46e6e06599633c106cb6402c2ad9d5`

<details><summary>CSV SHA-256 (35 files)</summary>

- `funding/ADAUSDT.csv`: `64411b95e03c131f132d153f844037612a726ef18c988180a912446e0b669eff`
- `funding/APTUSDT.csv`: `4ecc3579ce5113a4b5fc4d918dd5c7fce9dfc963057b017762da9c73e48bbdca`
- `funding/ARBUSDT.csv`: `bc4f0be38685497ec1656a25c8e5ba152c562ce25594b1ba5aa140bd080f09dd`
- `funding/AVAXUSDT.csv`: `ff110bfb29dd6d60d6058cf0ed6da5d1489985f52ccde94454243484280e3ff5`
- `funding/BCHUSDT.csv`: `37fadd11849dc5c13d686d25e5aceae4dcdf2787d72bbde37f521eba83f787fd`
- `funding/BTCUSDT.csv`: `bed68ff8e480c6dc987dff31080cff2c612fa292bb33faa27db15b8146fd8b4a`
- `funding/DOGEUSDT.csv`: `a23583aeca171b437853fb2889d7f6f470b9d7afa5ff16d0ebb864316ffcedf0`
- `funding/DOTUSDT.csv`: `c524bd82553269714d0ddb0c033e284f6d5cfa11bdf56fa074fb71fe536b5ffa`
- `funding/ETHUSDT.csv`: `16542a31bca233c366d64dd054b5c9fe313362943db77d230aeacb4e0d2138fd`
- `funding/LINKUSDT.csv`: `970d7504d12f8d9c3426f48766fd42dd1300b100ebdf855c032888883e4cb51b`
- `funding/LTCUSDT.csv`: `d3e1ee5dcf315930c51c5bef1a64f58475a0e2b54e1d6bb4e7c76a57f2b10ef2`
- `funding/NEARUSDT.csv`: `524daf275aa2b990a0f798aff3697095e1d7350ce5426ab1694ef01028d1bdd3`
- `funding/OPUSDT.csv`: `74ba7bd51b513ce3e342de0001f6d75f26dc418765fa5992a0b7c8a11d39b3ee`
- `funding/SOLUSDT.csv`: `bbc5852b0f57c0804ee51d1508f22f0fcd49356a77bc27ffddd858596ec7d830`
- `funding/SUIUSDT.csv`: `6cffd42c6512568387fa9c9592218349888ed1fb006560b056b5e0726820a923`
- `funding/TRXUSDT.csv`: `b2fa7ed917eb7356533c7a33741ccca25b9116f5b2a8622e6e674c3c7f8a5d35`
- `funding/XRPUSDT.csv`: `05071ac0c27a260619896a1497cfd691aa5ef2cd856dbb84c837e229fd8341cc`
- `futures/ADAUSDT_4h.csv`: `eae979a4ab13108b1b09f9c46bc316d066070ef481fa4f313cad1e128206ac76`
- `futures/APTUSDT_4h.csv`: `3c68afcae3821876fb49e79a001c4214bd7cbbf3211f026a8abe24f15a029b14`
- `futures/ARBUSDT_4h.csv`: `18c82db74245b76464f2b570e0938407e2a93377bed69c6d85656c3143613f36`
- `futures/AVAXUSDT_4h.csv`: `8b030068952dd864b080fed4f5a183f1f696b47a625ba53ae1a61d5d243d0c00`
- `futures/BCHUSDT_4h.csv`: `ef2e77b91c85be9ebc3649867bf0c51140aa80dbe59b7f94ee080e2f7fafad7a`
- `futures/BNBUSDT_4h.csv`: `45aa933e5eb8e92748e2ba8a326be89f2422d7977cb0f72a2beef3a155b93cdc`
- `futures/BTCUSDT_4h.csv`: `4c67ae1dde25cfa9dc451b9b16622dff4910729949e03bfe19b9f19efe108b4a`
- `futures/DOGEUSDT_4h.csv`: `05397fa3613f872e0e39985466033666327a554792cef7beff1b918306e2f544`
- `futures/DOTUSDT_4h.csv`: `18ee78f2e31311a6987dee34495f495073a0abf84daad4917533f425f62187e0`
- `futures/ETHUSDT_4h.csv`: `00ea44b05550d7b1c611592fc9e207c35c4793649b2d7dc77a06cd5efc1aded5`
- `futures/LINKUSDT_4h.csv`: `d7344429ad47da520ca0481037c934473f60e9cbc99103fe719e892eccce50f3`
- `futures/LTCUSDT_4h.csv`: `7575dcfb6bc40fe4e1deebf142fcbf8da13914696f19897fcf16f8f952599487`
- `futures/NEARUSDT_4h.csv`: `1a6ee445b1342542b83184c1f1789bba574de385bb6cdc8a09316190fc0d9aaa`
- `futures/OPUSDT_4h.csv`: `5f84d19f1812cff42e7db9d179c42b8a15f03a742494e386c4589fb677269e20`
- `futures/SOLUSDT_4h.csv`: `d67f0449dfea47ae931d5079b0335611e82e6beff2b24e47a4cef223b22c2878`
- `futures/SUIUSDT_4h.csv`: `65fd3f2867a9b1c2c9fcc48800febf5faa5acc7bf09fcd4cbe1b9d0e2fbddc15`
- `futures/TRXUSDT_4h.csv`: `761dfa00fc88f92f027f819c5d3b20d897e334b84e10ef523db3bf0713e5264c`
- `futures/XRPUSDT_4h.csv`: `abd05de2a064874f020a2a519fdb907b351bd9c0f5de34c5508786c60da832f8`

</details>

## Summary (OOS)

| series | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| OOS | 1529 | 7.58% | 1.76% | 11.84% | 0.206 | [-0.596, 0.941] | 0.341 | 16.44% | 0.107 | 1.40% | 1.049 |

| gross_mean | turnover_daily | n_trades_final_cfg |
|---|---|---|
| 0.099 | 0.016 | 4683 |

## Configurations (each alone, OOS)

| config | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | 1529 | 3.80% | 0.89% | 9.28% | 0.142 | [-0.826, 0.961] | 0.246 | 14.87% | 0.060 | 1.01% | 1.035 |
| B2 | 1529 | -0.79% | -0.19% | 7.65% | 0.013 | [-0.998, 0.828] | 0.023 | 16.52% | -0.011 | 0.82% | 1.004 |
| B3 | 1529 | 15.60% | 3.52% | 12.54% | 0.338 | [-0.465, 1.085] | 0.559 | 14.99% | 0.235 | 1.47% | 1.075 |
| B4 | 1529 | 1.13% | 0.27% | 9.03% | 0.074 | [-0.869, 0.911] | 0.128 | 16.92% | 0.016 | 0.99% | 1.018 |
| B5 | 1529 | 0.17% | 0.04% | 7.40% | 0.042 | [-0.989, 0.946] | 0.075 | 14.73% | 0.003 | 0.79% | 1.012 |

## Walk-forward selections (training only)

| fold | train_start | train_end | test_start | test_end | selected | test_days | train_sr[B1] | train_sr[B2] | train_sr[B3] | train_sr[B4] | train_sr[B5] |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2020-09-01 | 2021-12-31 | 2022-01-01 | 2022-03-31 | B3 | 90 | 0.620 | 0.742 | 0.787 | 0.701 | 0.575 |
| 1 | 2020-09-01 | 2022-03-31 | 2022-04-01 | 2022-06-30 | B3 | 91 | 0.861 | 0.866 | 0.968 | 0.893 | 0.866 |
| 2 | 2020-09-01 | 2022-06-30 | 2022-07-01 | 2022-09-30 | B1 | 92 | 1.007 | 0.941 | 0.869 | 1.007 | 0.914 |
| 3 | 2020-09-01 | 2022-09-30 | 2022-10-01 | 2022-12-31 | B4 | 92 | 0.741 | 0.650 | 0.492 | 0.754 | 0.617 |
| 4 | 2020-09-01 | 2022-12-31 | 2023-01-01 | 2023-03-31 | B1 | 90 | 0.486 | 0.463 | 0.384 | 0.478 | 0.338 |
| 5 | 2020-09-01 | 2023-03-31 | 2023-04-01 | 2023-06-30 | B1 | 91 | 0.432 | 0.325 | 0.409 | 0.405 | 0.228 |
| 6 | 2020-09-01 | 2023-06-30 | 2023-07-01 | 2023-09-30 | B1 | 92 | 0.444 | 0.335 | 0.358 | 0.395 | 0.248 |
| 7 | 2020-09-01 | 2023-09-30 | 2023-10-01 | 2023-12-31 | B1 | 92 | 0.391 | 0.291 | 0.276 | 0.342 | 0.184 |
| 8 | 2020-09-01 | 2023-12-31 | 2024-01-01 | 2024-03-31 | B1 | 91 | 0.451 | 0.383 | 0.364 | 0.402 | 0.253 |
| 9 | 2020-09-01 | 2024-03-31 | 2024-04-01 | 2024-06-30 | B1 | 91 | 0.519 | 0.368 | 0.481 | 0.359 | 0.304 |
| 10 | 2020-09-01 | 2024-06-30 | 2024-07-01 | 2024-09-30 | B1 | 92 | 0.387 | 0.287 | 0.355 | 0.289 | 0.194 |
| 11 | 2020-09-01 | 2024-09-30 | 2024-10-01 | 2024-12-31 | B1 | 92 | 0.307 | 0.278 | 0.295 | 0.243 | 0.112 |
| 12 | 2020-09-01 | 2024-12-31 | 2025-01-01 | 2025-03-31 | B3 | 90 | 0.309 | 0.264 | 0.365 | 0.255 | 0.152 |
| 13 | 2020-09-01 | 2025-03-31 | 2025-04-01 | 2025-06-30 | B3 | 91 | 0.326 | 0.246 | 0.437 | 0.285 | 0.167 |
| 14 | 2020-09-01 | 2025-06-30 | 2025-07-01 | 2025-09-30 | B3 | 92 | 0.226 | 0.177 | 0.320 | 0.201 | 0.111 |
| 15 | 2020-09-01 | 2025-09-30 | 2025-10-01 | 2025-12-31 | B3 | 92 | 0.250 | 0.188 | 0.411 | 0.222 | 0.157 |
| 16 | 2020-09-01 | 2025-12-31 | 2026-01-01 | 2026-03-09 | B3 | 68 | 0.224 | 0.139 | 0.384 | 0.195 | 0.122 |

## By year

| year | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | 365 | -2.56% | -2.56% | 13.48% | -0.125 | [-2.159, 1.657] | -0.204 | 15.00% | -0.170 | 1.56% | 0.974 |
| 2023 | 365 | 1.89% | 1.89% | 4.87% | 0.408 | [-1.048, 1.831] | 0.660 | 3.64% | 0.519 | 0.50% | 1.099 |
| 2024 | 366 | -2.85% | -2.84% | 6.11% | -0.442 | [-2.520, 1.367] | -0.698 | 8.40% | -0.338 | 0.69% | 0.919 |
| 2025 | 365 | 6.27% | 6.27% | 15.77% | 0.464 | [-0.872, 1.616] | 0.748 | 11.33% | 0.554 | 1.91% | 1.100 |
| 2026 | 68 | 4.94% | 29.56% | 22.86% | 1.244 | [-5.518, 4.584] | 2.414 | 7.45% | 3.967 | 2.02% | 1.289 |

## By symbol

_Single series: no per-symbol breakdown available._

## By regime (ex-ante cell: trend_BTC x vol tercile)

| regime | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| down_high | 112 | -11.38% | -32.55% | 17.28% | -2.194 | [-5.211, -0.257] | -3.169 | 12.10% | -2.690 | 2.17% | 0.618 |
| down_low | 317 | 0.98% | 1.13% | 12.12% | 0.153 | [-2.710, 2.191] | 0.282 | 14.57% | 0.078 | 1.24% | 1.034 |
| down_mid | 246 | 10.27% | 15.60% | 13.56% | 1.137 | [-0.597, 2.961] | 1.983 | 5.71% | 2.735 | 1.50% | 1.256 |
| up_high | 32 | 0.61% | 7.18% | 5.13% | 1.375 | [-3.069, 5.576] | 2.134 | 1.18% | 6.090 | 0.59% | 1.283 |
| up_low | 614 | 7.63% | 4.47% | 11.05% | 0.451 | [-0.590, 1.469] | 0.705 | 11.33% | 0.394 | 1.37% | 1.113 |
| up_mid | 208 | 0.68% | 1.19% | 8.02% | 0.187 | [-3.366, 2.225] | 0.414 | 5.83% | 0.205 | 0.68% | 1.054 |

## Costs (USDT, final configuration)

| commission | slippage | funding |
|---|---|---|
| 1107.816 | 1165.974 | -824.417 |

## Mandatory stress (PLAN §5.4; not new trials)

| run | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cost_x2 | 1529 | -6.09% | -1.49% | 8.70% | -0.129 | [-0.988, 0.671] | -0.207 | 20.62% | -0.072 | 1.05% | 0.971 |
| delay_1 | 1529 | 7.58% | 1.76% | 11.35% | 0.210 | [-0.547, 0.922] | 0.332 | 15.32% | 0.115 | 1.41% | 1.049 |
| worst_bar | 1529 | -11.84% | -2.96% | 5.35% | -0.536 | [-1.395, 0.285] | -0.769 | 18.35% | -0.162 | 0.66% | 0.824 |
| funding_x0.5 | 1529 | 8.76% | 2.02% | 11.88% | 0.228 | [-0.580, 0.973] | 0.377 | 15.99% | 0.127 | 1.40% | 1.054 |
| funding_x2 | 1529 | 4.86% | 1.14% | 11.63% | 0.155 | [-0.655, 0.878] | 0.254 | 17.26% | 0.066 | 1.39% | 1.036 |

## Benchmarks

| benchmark | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B&H BTC (vol-matched) | 1529 | 20.80% | 4.62% | 11.84% | 0.440 | [-0.537, 1.484] | 0.643 | 20.05% | 0.230 | 1.42% | 1.070 |
| B&H basket (vol-matched) | 1529 | 4.15% | 0.97% | 11.84% | 0.141 | [-0.775, 1.189] | 0.196 | 16.37% | 0.060 | 1.47% | 1.021 |

## Random entries

- Candidate Sharpe 0.250, 95th percentile of 100 random draws 0.253, percentile 94.000.

## Tail events (2021-05-19, 2022-11-09, 2025-10-10)

| config | day | return | gross_prev_close | stops_filled | stops_gapped | stop_slip_bps | liquidations | ret_cost_x2 | ret_delay_1 | ret_worst_bar | stops_filled_worst_bar | ret_funding_x0.5 | ret_funding_x2 | stops_total | liq_rejected_total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | 2021-05-19 | -0.002 | 0.015 | 1 | 0 | 10.457 | 0 | -0.002 | -0.010 | -0.003 | 1 | -0.002 | -0.002 | 884 | — |
| B1 | 2022-11-09 | 0.012 | 0.115 | 1 | 0 | 10.929 | 0 | 0.012 | 0.016 | 0.005 | 1 | 0.012 | 0.012 | 884 | — |
| B1 | 2025-10-10 | -0.000 | 0.000 | 1 | 0 | 10.000 | 0 | -0.000 | -0.001 | 0.000 | 0 | -0.000 | -0.000 | 884 | — |
| B2 | 2021-05-19 | -0.002 | 0.015 | 1 | 0 | 10.457 | 0 | -0.002 | -0.003 | -0.003 | 1 | -0.002 | -0.002 | 1010 | — |
| B2 | 2022-11-09 | 0.010 | 0.106 | 1 | 0 | 10.929 | 0 | 0.010 | 0.009 | 0.004 | 1 | 0.010 | 0.010 | 1010 | — |
| B2 | 2025-10-10 | -0.000 | 0.000 | 1 | 0 | 10.000 | 0 | -0.000 | -0.001 | 0.000 | 0 | -0.000 | -0.000 | 1010 | — |
| B3 | 2021-05-19 | -0.003 | 0.030 | 1 | 0 | 10.457 | 0 | -0.003 | -0.013 | -0.004 | 1 | -0.003 | -0.003 | 1242 | — |
| B3 | 2022-11-09 | 0.014 | 0.106 | 1 | 0 | 10.929 | 0 | 0.014 | 0.019 | 0.013 | 1 | 0.014 | 0.014 | 1242 | — |
| B3 | 2025-10-10 | -0.003 | 0.000 | 1 | 0 | 10.000 | 0 | -0.001 | -0.004 | 0.000 | 0 | -0.003 | -0.003 | 1242 | — |
| B4 | 2021-05-19 | -0.002 | 0.015 | 1 | 0 | 10.457 | 0 | -0.002 | -0.010 | -0.003 | 1 | -0.002 | -0.002 | 1081 | — |
| B4 | 2022-11-09 | 0.012 | 0.115 | 1 | 0 | 10.929 | 0 | 0.012 | 0.008 | 0.005 | 1 | 0.012 | 0.012 | 1081 | — |
| B4 | 2025-10-10 | -0.000 | 0.000 | 1 | 0 | 10.000 | 0 | 0.000 | -0.001 | 0.000 | 0 | -0.000 | -0.000 | 1081 | — |
| B5 | 2021-05-19 | -0.002 | 0.015 | 1 | 0 | 10.457 | 0 | -0.002 | -0.003 | -0.003 | 1 | -0.002 | -0.002 | 677 | — |
| B5 | 2022-11-09 | 0.010 | 0.049 | 0 | 0 | n/a | 0 | 0.010 | 0.014 | 0.005 | 0 | 0.010 | 0.010 | 677 | — |
| B5 | 2025-10-10 | -0.000 | 0.000 | 1 | 0 | 10.000 | 0 | -0.000 | -0.001 | 0.000 | 0 | -0.000 | -0.000 | 677 | — |

## Gate (PLAN §5.6)

**Level: C**

| level | check | status | value | threshold | detail |
|---|---|---|---|---|---|
| A | dsr | fail | 0.225 | 0.950 | N=21, V[SR]=0.000242/day |
| A | pbo | fail | 0.332 | 0.300 |  |
| A | random_entries | fail | 0.250 | 0.253 | 100 random draws |
| A | vs_bh | fail | BTC: 0.628, basket: 0.449 | 0.050 | one-sided p |
| A | no_catastrophe | fail | n/a | dSR>-1SE, DD<=B&H | 2022/BTC: ok dSR=1.16 (SE 1.75), MaxDD 15.0% vs B&H 20.0%; 2022/basket: ok dSR=0.98 (SE 1.76), MaxDD 15.0% vs B&H 16.4%; 2023-24/BTC: FAIL dSR=-2.08 (SE 0.84), MaxDD 8.4% vs B&H 5.8%; 2023-24/basket: FAIL dSR=-1.64 (SE 0.82), MaxDD 8.4% vs B&H 9.9%; 2025-26/BTC: ok dSR=0.97 (SE 1.39), MaxDD 11.3% vs B&H 13.7%; 2025-26/basket: ok dSR=1.30 (SE 1.28), MaxDD 11.3% vs B&H 14.8% |
| A | cost_stress | fail | -0.129 | >0 and >= 50% of 0.21 |  |
| A | delay_stress | pass | 0.210 | >= 50% of 0.21 |  |
| A | frozen_spot | n/a | n/a | n/a | not a daily family |
| A | max_dd | pass | 0.164 | 0.200 |  |
| A | holdout | pending | n/a | n/a | holdout not opened (E9) |
| A | significance | fail | 0.422 | 3.000 | t=0.42; trades 1539 vs needed 2793 |
| B | pbo | fail | 0.332 | 0.300 |  |
| B | random_entries | fail | 0.250 | 0.253 | 100 random draws |
| B | cost_stress | fail | -0.129 | > 0 |  |
| B | frozen_spot | n/a | n/a | n/a | not a daily family |
| B | psr | fail | 0.665 | 0.900 |  |
| B | adaptability | fail | -0.206 | > 0 |  |

## Adaptability A_k (PLAN §3.3)

| A_k | q20 | penalty | frac_positive | worst_regime | worst_regime_cvar95 | tau2 | n_cells | t_years | N_eff (PR) | N_eff n/(1+(n-1)rho) |
|---|---|---|---|---|---|---|---|---|---|---|
| -0.206 | 0.185 | 0.391 | 1.000 | down_high | 0.022 | 0.000 | 6 | 4.189 | 1.000 | 1.000 |

## Simulated kill-switch (user limits; whole run from the training anchor)

| config | run | halted_on | days_halted | days_block_entries | days_flatten_leveraged | days_half_risk | max_dd_run |
|---|---|---|---|---|---|---|---|
| B1 | base | - | 0 | 4 | 0 | 872 | 14.87% |
| B2 | base | - | 0 | 4 | 0 | 1132 | 16.52% |
| B3 | base | - | 0 | 16 | 0 | 681 | 14.99% |
| B4 | base | - | 0 | 3 | 0 | 1192 | 16.92% |
| B5 | base | - | 0 | 3 | 0 | 1119 | 14.73% |
| B1 | cost_x2 | - | 0 | 4 | 0 | 1185 | 17.49% |
| B2 | cost_x2 | - | 0 | 5 | 0 | 1183 | 18.91% |
| B3 | cost_x2 | - | 0 | 4 | 0 | 1309 | 18.61% |
| B4 | cost_x2 | 2025-06-06 | 277 | 4 | 0 | 1210 | 20.19% |
| B5 | cost_x2 | - | 0 | 3 | 0 | 1186 | 16.92% |
| B1 | delay_1 | - | 0 | 4 | 0 | 893 | 14.20% |
| B2 | delay_1 | - | 0 | 4 | 0 | 1214 | 16.72% |
| B3 | delay_1 | - | 0 | 18 | 0 | 849 | 17.35% |
| B4 | delay_1 | - | 0 | 3 | 0 | 1274 | 19.86% |
| B5 | delay_1 | - | 0 | 3 | 0 | 1186 | 16.24% |
| B1 | worst_bar | 2023-09-27 | 895 | 7 | 0 | 1326 | 20.09% |
| B2 | worst_bar | 2023-03-16 | 1090 | 4 | 0 | 1552 | 20.45% |
| B3 | worst_bar | 2022-12-13 | 1183 | 5 | 0 | 1502 | 20.07% |
| B4 | worst_bar | 2023-01-31 | 1134 | 3 | 0 | 1730 | 20.15% |
| B5 | worst_bar | 2024-07-06 | 612 | 5 | 0 | 1288 | 20.12% |
| B1 | funding_x0.5 | - | 0 | 4 | 0 | 836 | 14.54% |
| B2 | funding_x0.5 | - | 0 | 4 | 0 | 1123 | 16.19% |
| B3 | funding_x0.5 | - | 0 | 16 | 0 | 665 | 15.05% |
| B4 | funding_x0.5 | - | 0 | 3 | 0 | 1182 | 16.26% |
| B5 | funding_x0.5 | - | 0 | 4 | 0 | 1102 | 14.59% |
| B1 | funding_x2 | - | 0 | 4 | 0 | 916 | 14.87% |
| B2 | funding_x2 | - | 0 | 4 | 0 | 1145 | 16.96% |
| B3 | funding_x2 | - | 0 | 15 | 0 | 779 | 15.92% |
| B4 | funding_x2 | - | 0 | 3 | 0 | 1197 | 18.46% |
| B5 | funding_x2 | - | 0 | 3 | 0 | 1138 | 14.84% |

## Frozen spot 2017-2020

_not applicable_
