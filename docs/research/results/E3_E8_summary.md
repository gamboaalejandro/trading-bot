# E3-E8 summary (phase F1)

Generated 2026-10-16. Branch `feature/experiments`. Every number below is copied from the
committed reports (`E5/`, `E6/`, `E2/`) or from the read-only diagnostics in `diagnostics/`
(scripts in `scripts/research_diag/`); nothing was computed by hand. Holdout (E9): **closed, not
opened**. OOS = anchored walk-forward, 17 quarterly folds, 2022-01-01..2026-03-09 (1529 days;
CARRY 1528). Sharpe IC95 = stationary bootstrap, mean block 20 days.

Warnings carried by every result: **survivorship bias** (every symbol is still listed in 2026;
LUNA, FTT, SRM... are missing), **funding not verified** against `/fapi/v1/fundingRate` and
`/fapi/v1/fundingInfo` (local funding sampled at 00/08/16 UTC, 4h/1h intervals under-counted),
BNBUSDT funding excluded. Published figures are not targets.

## Trial budget (trials log `data/trials/trials.jsonl`)

| family | used | quota | status |
|---|---|---|---|
| DEBATE (exploratory, preloaded) | 8 | 8 | closed |
| TREND T1-T5 (E2) | 5 | 5 | exhausted |
| E3 REGIME | 0 | 3 | closed by the panel (2/5 votes) |
| E3 FVETO | 0 | 3 | closed by the panel (1/5), deferred until funding is verified |
| E4 SHORT | 0 | 2 | closed by the panel (2/5) |
| **E5 BRK4H B1-B5** | **5** | 5 | run (5/5), exhausted |
| **E6 CARRY K1-K3** | **3** | 3 | run (4/5), paper only, exhausted |
| E7 PULLBACK | 0 | — | closed by the panel (0/5) |
| E7 SHOCK | 0 | — | closed by the panel (2/5) |
| E8 SELECTOR | 0 | — | closed: needs >= 2 engines at level A/B (there are none) |
| **N total** | **21** | | |

The log holds 54 records (21 trials + 33 metric records). E5 futures was resumed after a container
restart with `--resume` (BRK4H-01..05 reused, metrics not appended again). The diagnostics of this
summary are read-only: the log was checked to still hold 54 records / 5 BRK4H / 3 CARRY trials
after they ran.

## E5 — BRK4H B1-B5 (4h Donchian breakout, long-only in spot, long/short perp)

Configurations (fixed before results): B1 n=20 with all filters, B2 n=55, B3 = B1 without ADX,
B4 = B1 without the funding filter, B5 = B1 + volume/close-location filter.

### Family result (per-fold selection on training only)

| market | selection per fold | CAGR | vol | Sharpe [IC95] | MaxDD | PBO | random entries (pctl) | cost x2 Sharpe | gate |
|---|---|---|---|---|---|---|---|---|---|
| spot | B5 f0-1,5-7,10-11; B2 f2-4,8-9; B3 f12-16 | 2.22% | 6.52% | 0.368 [-0.600, 1.169] | 8.87% | 0.088 | 0.379 vs p95 0.199 (99) | -0.061 | **C** |
| perp | B3 f0-1,12-16; B1 f2,4-11; B4 f3 | 1.76% | 11.84% | 0.206 [-0.596, 0.941] | 16.44% | 0.332 | 0.250 vs p95 0.253 (94) | -0.129 | **C** |

Each configuration alone (OOS Sharpe / MaxDD): spot B1 0.252 / 10.55%, B2 -0.205 / 11.40%,
B3 0.674 / 9.71%, B4 -0.323 / 9.99%, B5 0.357 / 6.81%; perp B1 0.142 / 14.87%, B2 0.013 / 16.52%,
B3 0.338 / 14.99%, B4 0.074 / 16.92%, B5 0.042 / 14.73%.

Failed checks — spot level A: DSR 0.241, vs B&H (p 0.547 BTC / 0.365 basket), no-catastrophe
(2023-24 dSR -2.19 vs BTC), cost x2, significance (t 0.75); level B: cost x2, PSR 0.780, A_k
-0.866. Perp level A: DSR 0.225, PBO 0.332, random entries (94th pctl), vs B&H, no-catastrophe
(2023-24), cost x2, significance (t 0.42); level B: PBO, random entries, cost x2, PSR 0.665,
A_k -0.206. MaxDD <= 20 % passes in both markets, but the worst-bar stop stress halts the
kill-switch (DD >= 20 %) in 2 of 5 spot configurations and 5 of 5 perp configurations.

### Pre-registered rule 2 — "beats T3 in DSR" (same global N = 21, same V[SR] from the log)

`diagnostics/e5_rules_spot.json`, `diagnostics/e5_rules_futures.json`. V[SR] = variance of the per-day Sharpes of every logged trial
(2.42e-4/day at N = 21, after E5/E6). The committed spot report shows DSR 0.241 because it was
written when the log held fewer metric records (V[SR] 3.68e-4); the rule uses the final log for both sides.

| market | BRK4H family Sharpe / DSR | T3 alone Sharpe / DSR | BRK4H beats T3? | dSharpe (SE) |
|---|---|---|---|---|
| spot | 0.368 / 0.336 | 0.411 / 0.372 | **no** | -0.042 (0.554) |
| perp | 0.206 / 0.225 | 0.377 / 0.345 | **no** | -0.171 (0.626) |

### Pre-registered rule 3 — ablations (one-sided stationary bootstrap, block 20, 10 000 reps; Holm over 3 tests)

A filter adds value if p < 0.05 **or** dSharpe > 1 SE of the B1 Sharpe.

| market | test | Sharpe a / b | dSharpe | 1 SE(B1) | p boot | p Holm | adds value? |
|---|---|---|---|---|---|---|---|
| spot | ADX (B1 - B3) | 0.252 / 0.674 | -0.422 | 0.483 | 0.946 | 0.946 | **no** (removing ADX was better) |
| spot | funding (B1 - B4) | 0.252 / -0.323 | +0.575 | 0.483 | 0.030 | 0.091 | **yes** by the rule (p < 0.05 and dSharpe > 1 SE); not significant after Holm |
| spot | volume (B5 - B1) | 0.357 / 0.252 | +0.105 | 0.483 | 0.413 | 0.827 | **no** |
| perp | ADX (B1 - B3) | 0.142 / 0.338 | -0.196 | 0.482 | 0.855 | 1.000 | **no** |
| perp | funding (B1 - B4) | 0.142 / 0.074 | +0.067 | 0.482 | 0.258 | 0.773 | **no** |
| perp | volume (B5 - B1) | 0.042 / 0.142 | -0.100 | 0.482 | 0.749 | 1.000 | **no** |

### Rule 4 — perp folds 0-7 (short training) reported separately

| series | folds 0-7 (2022-2023) Sharpe / MaxDD | folds 8-16 (2024-2026Q1) Sharpe / MaxDD |
|---|---|---|
| BRK4H spot family | -0.091 / 6.7% | 0.596 / 8.9% |
| T3 spot | 0.981 / 12.2% | -0.054 / 18.2% |
| BRK4H perp family | 0.015 / 15.3% | 0.343 / 11.3% |
| T3 perp | 0.919 / 12.0% | -0.073 / 17.6% |

### E5 verdict

- Gate level **C** in spot and perp (MaxDD <= 20 % passes in both; DSR, cost x2, vs B&H and
  significance fail in both).
- **BRK4H does not beat T3 in DSR** in either market (spot 0.336 vs 0.372; perp 0.225 vs 0.345).
- Ablations: the ADX filter does not add value (B3, without it, is the best single configuration
  in both markets, but that is an ex-post observation, not a selectable result). The funding
  filter adds value in **spot** by the pre-registered rule (p 0.030; Holm 0.091, so not robust to
  the multiple-test correction) and not in perp (p 0.258). The volume filter adds no value.
  Note: the spot funding filter reads perp funding, which is itself **not verified**.
- The BRK4H quota is exhausted; no new variant (e.g. "B1 without ADX + funding") may be tried
  without a new pre-registered family and panel vote. Family closed at level C.

Spot per-configuration CSV (`E5/brk4h_spot_configs_returns.csv`): regenerated with
`python -m apps.research.run E5 --market spot --resume` into a scratch reports directory (the spot
report predates the per-configuration CSV). Zero new trials: `trials.jsonl` SHA-256 unchanged
(`1b83570a…`, 54 records), and the family OOS return CSV is byte-identical to the committed one.

## E6 — CARRY K1-K3 (paper only, **P&L not verified**)

| series | CAGR | vol | Sharpe [IC95] | MaxDD | PBO | random entries (pctl) | gate |
|---|---|---|---|---|---|---|---|
| family (K3 in 14/17 folds, K1 in 9-11) | 0.16% | 1.12% | 0.145 [-0.534, 3.600] | 2.27% | 1.000 | 0.497 vs p95 0.840 (78) | **C** |
| K1 alone | 0.63% | 1.12% | 0.563 | 2.27% | | | |
| K2 alone | 0.32% | 1.29% | 0.251 | 2.44% | | | |
| K3 alone | 0.45% | 0.42% | 1.053 | 0.57% | | | |

DSR 0.210 in the report (0.221 with the final V[SR] of the log; both far below 0.95). PBO = 1.0:
the configuration chosen in training (K3) was worse OOS than the median in every CSCV split.
The result is extremely funding-sensitive: funding x0.5 -> Sharpe -0.274, funding x2 -> 0.950,
so with unverified funding it says nothing about real P&L. The +1 bar delay stress fails by
construction. Destination: **paper only**, and only after the user verifies funding (§8).

## Adaptability A_k (PLAN §3.3; λ = 0.1; Q20 of EB-shrunk cell Sharpes)

| engine | market | A_k | Q20 | penalty | cells | share SR~ > 0 | worst regime (CVaR95) | source |
|---|---|---|---|---|---|---|---|---|
| TREND T3 alone | spot | -1.291 | -1.144 | 0.147 | 52 (coin x regime) | 0.21 | up_low (1.43%) | `diagnostics/t3_ak.json` |
| TREND T3 alone | perp | -0.342 | -0.196 | 0.147 | 54 | 0.11 | up_low (1.46%) | `diagnostics/t3_ak.json` |
| TREND family (T1 selected) | spot | -0.905 | | | | | | `E2/` |
| TREND family (T2/T4) | perp | -0.388 | | | | | | `E2/` |
| BRK4H family | spot | -0.866 | -0.475 | 0.391 | 5 (portfolio x regime) | 0.00 | up_low (1.1%) | `E5/brk4h_spot.md` |
| BRK4H family | perp | -0.206 | 0.185 | 0.391 | 6 | 1.00 | down_high (2.2%) | `E5/brk4h_futures.md` |
| CARRY family | perp | **+1.647** | 1.744 | 0.098 | 3 | 1.00 | up_mid (0.3%) | `E6/carry_k1_k3_paper.md` |

Caveats: TREND cells are coin x regime (per-symbol contributions, close-to-close approximation
net of costs), while BRK4H and CARRY have no per-coin decomposition and use the portfolio series
as one column, so only 3-6 regime cells; the scores are not strictly comparable across engines.
CARRY's positive A_k rests on 3 cells, a 1.1 % vol series, PBO = 1.0 and unverified funding.
PLAN §3.3.5: "the most adaptable is the highest A_k **among those that pass the gate**" — no
engine passes level A or B, so **no engine is declared adaptable** and E8 SELECTOR stays closed.

## Overall status after E3-E8

- Engines evaluated: TREND (E2), BRK4H (E5), CARRY (E6). All are **level C** in every market.
  No candidate for real capital or for paper under §5.6 (CARRY paper is an explicit panel
  exception, conditional on funding verification).
- Families closed by the panel without trials: REGIME, FVETO, SHORT, PULLBACK, SHOCK, SELECTOR
  (their quotas are kept; N stays 21).
- Holdout E9 not opened: there is no finalist that justifies spending it.
- Consequence for the user's plan (capital < 10k USD, 100 USD spot to validate execution, DD
  limits 20 % total / 5 % daily): the research does not support any strategy with real money.
  A 100 USD spot account can still be used **only** to validate execution plumbing (orders,
  fills, fees, kill-switch) with minimum-notional orders (~5 USD) on BTC/ETH, without any
  expectation of edge; futures remain testnet-only (BTC minNotional ~100 USD).
