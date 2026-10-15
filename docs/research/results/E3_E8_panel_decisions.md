# E3-E8: panel decisions and pre-registered criteria (written BEFORE running E5/E6)

Date 2026-10-15. Branch `feature/experiments`. N before this phase: 13 (DEBATE 8 + TREND 5).
Holdout (E9): closed, not opened in this phase.

## Panel vote after E0-E2 (5 perspectives; majority = 3 of 5 "continue")

| family | pessimist | optimist | realist | analytic | mathematician | continue votes | decision |
|---|---|---|---|---|---|---|---|
| E3 REGIME | stop | continue | stop | continue | stop | 2/5 | **closed by the panel** (0 trials used, quota 3 kept) |
| E3 FVETO | stop | continue | stop | stop | stop | 1/5 | **closed by the panel** (0 trials; deferred until funding is verified) |
| E4 SHORT | stop | continue | stop | continue | stop | 2/5 | **closed by the panel** (0 trials, quota 2 kept) |
| E5 BRK4H | continue | continue | continue | continue | continue | 5/5 | **run** (quota 5: B1-B5) |
| E6 CARRY | continue | continue | continue | stop | continue | 4/5 | **run** (quota 3: K1-K3), paper only, "P&L not verified" |
| E7 PULLBACK | stop | stop | stop | stop | stop | 0/5 | **closed by the panel** (0 trials) |
| E7 SHOCK | stop | stop (reserve) | stop | continue | continue | 2/5 | **closed by the panel** (0 trials) |
| E8 SELECTOR | stop | conditional (needs >= 2 A/B engines) | stop | stop | stop | 0-1/5 | **closed by the panel**; in any case it needs >= 2 engines at level A/B |
| Reserve | — | — | — | — | — | — | not used |

Families closed by the panel register **no** trial and keep their quota (PLAN §2.1).

## Pre-registered interpretation rules for E5 (fixed before seeing any E5 number)

1. **Family result** = per-fold selection on training only (PLAN §5.3) over B1-B5; gate §5.6
   (levels A/B/C) with N from the trials log after registration, MaxDD OOS <= 20 % in spot and futures.
2. **"Beats T3 in DSR"** (PLAN §2.6): DSR of the BRK4H family OOS > DSR of T3 OOS in the same market,
   both computed with the same global N (the trials log after E5/E6) and the same variance of trial SRs.
3. **Ablation "the filter adds value"** (B3 = B1 without ADX, B4 = B1 without funding filter,
   B5 = B1 + volume filter): a filter adds value only if the one-sided stationary bootstrap
   (mean block 20 days) p-value of the daily OOS return difference `B1 - B3` (ADX) or `B1 - B4`
   (funding) is < 0.05, **or** the Sharpe difference exceeds 1 SE of the B1 Sharpe. For B5 the
   volume filter adds value if `B5 - B1` satisfies the same rule. Holm correction across the three
   ablation tests is reported alongside. Diagnostics computed from the per-configuration OOS return
   CSV written by `run.py` (no new trial).
4. Perp folds 0-7 (2022-01..2023-12) have short training windows (data from 2020-09): reported separately.
5. Survivorship bias and "funding not verified" are declared in every report.

## Pre-registered interpretation rules for E6 (CARRY)

- Gate §5.6 is reported, but the destination is PAPER ONLY whatever the level; every number is
  "P&L not verified" until the user checks `/fapi/v1/fundingRate` and `/fapi/v1/fundingInfo` (§8).
- The +1 bar delay stress is not supported by the carry simulator, so that check fails by construction.
