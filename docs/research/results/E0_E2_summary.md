# E0-E2 summary (phase F0)

Generated 2026-10-15 from the reports in this directory (every number below is copied from
`E0/`, `E1/` and `E2/`; nothing was computed by hand). Branch `feature/experiments`,
harness commit `c60c2a2`. Data commits: futures/funding `735eb87…`, spot `4d33a56…`.
Holdout: **closed (not used)**. OOS = anchored walk-forward, 17 quarterly folds,
2022-01-01..2026-03-09 (1529 days). Sharpe IC95 = stationary bootstrap, mean block 20 days.

Warnings carried by every report: survivorship bias (all symbols are listed in 2026), funding
**not verified** against `/fapi/v1/fundingRate`, BNBUSDT funding excluded.

## Trial budget

| family | used | quota |
|---|---|---|
| DEBATE (exploratory, preloaded) | 8 | 8 |
| TREND (T1-T5, registered once by E2) | 5 | 5 |
| **N total** | **13** | 40 |

E0 and E1 are not trials. The perp run, the spot-vs-perp comparison, the stress runs and the
frozen spot 2017-2020 runs are not trials (PLAN §2.1). TREND quota is exhausted (remaining 0).

E2 was executed twice with the same five registered configurations: the second run only added
report sections (tail-event detail, kill-switch activity, frozen run of every configuration;
commit `c60c2a2`). Re-registration is idempotent (N stays 13) and the OOS return CSVs of both
runs are byte-identical.

## E0 — data audit (`E0/data_audit.md`)

- 10 spot and 18 futures symbols load for 1d/4h/1h/15m; spot 4h has 0-17 NaN bars (2017-2019
  exchange outages, not filled); spot 1h has 2 NaN bars; futures 15m has 6 `volume == 0` bars
  per symbol (masked as NaN by the loader; 0 at 1h/4h/1d).
- Funding is in fraction: median 0.82 bps (BTC), 0.83 (ETH), 1.00 (most alts) per 8h.
- BNBUSDT funding: 49.8% exact zeros, 0% at 1e-4, negative annual sums 2022-2025 -> excluded.
- Only SOLUSDT shows non-8h funding intervals (94 gaps, 98.6% at 8h).
- Mean funding APR (8h assumed): BTC 11.1%, ETH 12.3%, LINK 14.2%, XRP 13.0%.

## E1 — buy & hold benchmarks, WF window (`E1/`)

| series (spot) | CAGR | vol | Sharpe [IC95] | MaxDD |
|---|---|---|---|---|
| B&H BTC | 9.82% | 52.09% | 0.440 [-0.538, 1.486] | 66.93% |
| B&H basket EW (9 common coins) | -12.79% | 72.17% | 0.173 [-0.792, 1.255] | 77.24% |

Perp B&H BTC: CAGR 9.81%, Sharpe 0.440 [-0.537, 1.484], MaxDD 66.94% (funding not included).

## E2 — TREND T1-T5 (`E2/`)

### Walk-forward OOS of the family (per-fold selection on training only)

| market | selection | CAGR | vol | Sharpe [IC95] | MaxDD | gate |
|---|---|---|---|---|---|---|
| spot | T1 in 17/17 folds | 3.65% | 9.21% | 0.436 [-0.826, 1.698] | 16.21% | **C** |
| perp (L = 1) | T2 in folds 0-7, T4 in folds 8-16 | 3.98% | 10.53% | 0.424 [-0.872, 1.658] | 19.08% | **C** |

Each configuration alone (OOS):

| config | spot Sharpe [IC95] | spot CAGR / MaxDD | perp Sharpe [IC95] | perp CAGR / MaxDD |
|---|---|---|---|---|
| T1 DON | 0.436 [-0.826, 1.698] | 3.65% / 16.21% | 0.391 [-0.867, 1.660] | 3.21% / 15.85% |
| T2 TSM | 0.034 [-1.221, 1.287] | -0.09% / 19.08% | -0.019 [-1.264, 1.188] | -0.52% / 18.18% |
| **T3 MIX (primary)** | 0.411 [-0.876, 1.673] | 3.62% / 18.22% | 0.377 [-0.869, 1.598] | 3.31% / 17.59% |
| T4 MIX σ 20% | 0.551 [-0.735, 1.808] | 6.13% / 19.92% | 0.564 [-0.708, 1.772] | 6.28% / 19.08% |
| T5 MIX b 0.10 | 0.434 [-0.834, 1.705] | 3.85% / 17.71% | 0.420 [-0.864, 1.637] | 3.73% / 17.69% |

Vol-matched B&H on the same window: BTC Sharpe 0.440 (MaxDD 15.89% spot / 17.99% perp),
basket 0.173-0.180.

### Gate (§5.6) — both markets level C

| check | spot | perp |
|---|---|---|
| DSR (N = 13) | 0.581 fail | 0.543 fail |
| PSR(0) | 0.814 fail (B needs 0.90) | 0.807 fail |
| PBO (CSCV S=16) | 0.375 fail | 0.137 pass |
| random entries (p95 of 100) | 0.478 vs 0.536 fail (pctl 92) | 0.617 vs 0.416 pass (pctl 97) |
| vs B&H vol-matched, one-sided p | BTC 0.491, basket 0.263 fail | BTC 0.498, basket 0.258 fail |
| no catastrophe per subperiod | fail 2023-24 and 2025-26 | fail 2023-24 and 2025-26 |
| costs x2 | 0.329 pass | 0.144 fail for A (< 50% of base), pass for B |
| +1 bar delay | 0.289 pass | 0.244 pass |
| frozen spot 2017-2020 | T1: SR 1.397, MaxDD 9.55% vs B&H 10.77% pass | T4: SR -0.196 fail |
| MaxDD OOS ≤ 20% | 16.2% pass | 19.1% pass |
| t-stat ≥ 3 | 0.89 fail | 0.87 fail |
| A_k (adaptability) | -0.905 fail | -0.388 fail |

By year (spot family OOS): 2022 -8.03%, 2023 +26.85%, 2024 +12.51%, 2025 -8.69%,
2026 (to 03-09) -3.03%. Perp: -7.37%, +25.69%, +17.57%, -10.86%, -3.48%.
Only the `up_low` regime cell is clearly positive (spot SR 1.529, perp 1.177).

### Spot vs perp (`E2/trend_spot_vs_perp.md`)

One-sided bootstrap p (perp > spot) = 0.4215 -> the preregistered rule keeps the **long leg in
spot**. Funding paid by the final perp configuration over its whole run (2020-09..2026-03, 10k
USDT start): 716.77 USDT (commission 385.45, slippage 302.24). Funding stress (perp family OOS):
x0.5 -> SR 0.462, x2 -> SR 0.271.

### Frozen OOS spot 2017-08-17..2020-08-31 (360-day warm-up, evaluated 2018-08..2020-08, 751 days)

| config | Sharpe [IC95] | CAGR | MaxDD |
|---|---|---|---|
| T1 | 1.397 [-0.001, 2.490] | 15.37% | 9.55% |
| T2 | -0.558 [-2.018, 0.644] | -4.24% | 15.28% |
| T3 (primary) | -0.237 [-1.591, 0.846] | -2.20% | 13.28% |
| T4 | -0.196 [-1.505, 0.944] | -2.22% | 14.29% |
| T5 | -0.192 [-1.587, 0.950] | -1.87% | 13.62% |
| B&H BTC vol-matched to T1 | 0.798 [-0.665, 2.058] | 8.24% | 10.77% |

### Stress (§5.4, family OOS)

| run | spot Sharpe / MaxDD | perp Sharpe / MaxDD |
|---|---|---|
| base | 0.436 / 16.21% | 0.424 / 19.08% |
| costs x2 | 0.329 / 16.61% | 0.144 / 20.06% |
| +1 bar delay | 0.289 / 13.61% | 0.244 / 19.94% |
| stop at worst price of the bar | 0.252 / 16.71% | 0.389 / 10.69% |
| funding x0.5 | — | 0.462 / 19.45% |
| funding x2 | — | 0.271 / 19.20% |

The simulated kill-switch (user limits: -2% / -5% daily, 10% DD half risk, 20% DD halt,
latched) halts several stress runs; the worst-bar run of T4 halts on 2022-09-15 (spot) and
2022-07-11 (perp) and stays flat afterwards, which explains the low perp worst-bar MaxDD.
The 10% DD half-risk rule is active on roughly half of the days of every base run.

### Tail events

| day | exposure | base P&L (T3) | worst-bar stop P&L (T3) |
|---|---|---|---|
| 2021-05-19 | flat in every configuration (gross 0) | 0.00% | 0.00% |
| 2022-11-09 | flat in every configuration | 0.00% | 0.00% (+1 bar delay: -3.1%) |
| 2025-10-10 | gross 0.083 (T3) | -0.4%, 1 stop, 30 bps spot / 10 bps perp slippage | -3.8% spot / -3.4% perp |

Simulated liquidations: 0 (longs at L <= 1 on isolated margin; no liquidation-check rejections).

## Caveats for the review

1. **Perp warm-up.** Futures data start on 2020-09-01, so the perp signals become defined on
   2021-08-27 (DON/MIX) and 2021-03-19 (TSM). The perp training Sharpe of folds 0-7 is built on
   a few months of trading and was negative for every configuration, which is why T2 was
   selected there. Spot signals are warm since 2018.
2. The WF window has one bear (2022) and one choppy year (2025); the family loses in both and
   only the `up_low` regime cell is clearly positive.
3. t ≈ 0.9 on 4.2 years: the plan's power analysis (§1.1.8) already expected no level-A result.

## Verdict

TREND (T1-T5) is **level C in spot and in perp**. Neither the WF family result nor the primary
T3 beats the vol-matched B&H of BTC (one-sided p ≈ 0.49), PSR(0) < 0.90 and A_k < 0. Per PLAN
§2.1 the TREND quota is exhausted and the family is closed; the gate is not relaxed. The overlays
of E3/E4 were designed as increments over T3 or the accepted TREND, so the review must decide
whether to run them over a level-C base.
