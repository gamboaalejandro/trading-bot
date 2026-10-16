# E2 — TREND spot vs perp

Generated 2026-10-15 22:10 UTC. Market: **spot vs futures**. Trials: none (not a trial). Holdout: closed.

## Warnings

- **Survivorship bias.** Every symbol of the universe is still listed in 2026; delisted coins (LUNA, FTT, SRM and others) are missing. Conclusions focus on BTC/ETH and every basket result carries this warning (PLAN §5.1).
- **Funding not verified.** The local funding is sampled at 00/08/16 UTC and may be the predicted rate, not the settled one; symbols moved to 4h/1h intervals are under-counted. P&L that depends on funding is UNVERIFIED until checked against `/fapi/v1/fundingRate` and `/fapi/v1/fundingInfo` (PLAN §2.7, §5.2.3, §8). BNBUSDT funding is excluded.
- Published figures (papers, debate) are not targets; only these OOS numbers count.

## Data provenance

- Harness git sha: `c60c2a25b92fe5e7933af812547ea94bfd07883e`
- Data commits (upstream sources): futures `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, funding `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, spot `4d33a56f2b3930376fc778522770c6e84855be7e`
- Manifest: not recorded for this report

## Summary (OOS)

| series | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| OOS | 1529 | -2.43% | -0.59% | 5.24% | -0.086 | [-0.927, 0.783] | -0.120 | 9.97% | -0.059 | 0.72% | 0.983 |

## By year

| year | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | 365 | -0.69% | -0.69% | 3.77% | -0.166 | [-1.860, 1.622] | -0.222 | 3.62% | -0.192 | 0.55% | 0.969 |
| 2023 | 365 | 0.92% | 0.92% | 3.89% | 0.254 | [-1.602, 2.264] | 0.349 | 3.44% | 0.266 | 0.51% | 1.045 |
| 2024 | 366 | -5.09% | -5.07% | 7.35% | -0.672 | [-2.367, 1.047] | -0.930 | 7.92% | -0.641 | 1.01% | 0.877 |
| 2025 | 365 | 2.15% | 2.15% | 5.34% | 0.425 | [-1.128, 2.064] | 0.630 | 3.98% | 0.540 | 0.70% | 1.088 |
| 2026 | 68 | 0.41% | 2.24% | 4.06% | 0.567 | [-2.819, 4.356] | 0.736 | 1.20% | 1.867 | 0.56% | 1.140 |

## By symbol

_Single series: no per-symbol breakdown available._

## By regime (ex-ante cell: trend_BTC x vol tercile)

_Regime labels not available._

## Benchmarks

| benchmark | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| spot | 1529 | 16.21% | 3.65% | 9.21% | 0.436 | [-0.826, 1.698] | 0.645 | 16.21% | 0.225 | 1.17% | 1.089 |
| perp | 1529 | 17.78% | 3.98% | 10.53% | 0.424 | [-0.872, 1.658] | 0.630 | 19.08% | 0.209 | 1.23% | 1.086 |

## Notes

- One-sided bootstrap p (perp > spot) = 0.4215. Preregistered rule: the long leg goes to spot unless perp wins with p < 0.05 -> **spot**.
