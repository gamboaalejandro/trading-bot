# E1 — Benchmarks futures

Generated 2026-10-15 20:50 UTC. Market: **futures**. Trials: none (not a trial). Holdout: closed.

## Warnings

- **Survivorship bias.** Every symbol of the universe is still listed in 2026; delisted coins (LUNA, FTT, SRM and others) are missing. Conclusions focus on BTC/ETH and every basket result carries this warning (PLAN §5.1).
- Published figures (papers, debate) are not targets; only these OOS numbers count.

## Data provenance

- Harness git sha: `6dac91d09d8fdf224327bfc08bb3a594b05fb153`
- Data commits (upstream sources): futures `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, funding `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, spot `4d33a56f2b3930376fc778522770c6e84855be7e`
- Manifest digest: `6acf58fc9eb926f264e689addc797d403ad8ee3b774206fdd24d233ec85f11a6`

<details><summary>CSV SHA-256 (9 files)</summary>

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
| OOS | 1529 | 48.01% | 9.81% | 52.17% | 0.440 | [-0.537, 1.484] | 0.643 | 66.94% | 0.147 | 6.27% | 1.070 |

## By year

| year | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | 365 | -64.21% | -64.21% | 63.86% | -1.284 | [-2.820, 0.232] | -1.691 | 66.94% | -0.959 | 8.70% | 0.820 |
| 2023 | 365 | 155.87% | 155.87% | 44.17% | 2.347 | [0.409, 4.279] | 4.121 | 20.01% | 7.790 | 4.46% | 1.450 |
| 2024 | 366 | 121.08% | 120.60% | 53.16% | 1.752 | [-0.162, 3.686] | 2.828 | 26.26% | 4.594 | 5.55% | 1.290 |
| 2025 | 365 | -6.35% | -6.35% | 41.73% | 0.051 | [-1.672, 1.842] | 0.073 | 32.05% | -0.198 | 4.90% | 1.007 |
| 2026 | 68 | -21.93% | -73.52% | 63.83% | -1.761 | [-4.824, 2.049] | -2.366 | 35.13% | -2.093 | 7.58% | 0.755 |

## By symbol

_Single series: no per-symbol breakdown available._

## By regime (ex-ante cell: trend_BTC x vol tercile)

| regime | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| down_high | 112 | 30.06% | 135.49% | 71.62% | 1.551 | [-0.816, 3.990] | 2.421 | 22.00% | 6.159 | 7.93% | 1.256 |
| down_low | 317 | -39.93% | -44.39% | 50.29% | -0.910 | [-2.947, 1.342] | -1.150 | 56.30% | -0.788 | 7.53% | 0.864 |
| down_mid | 246 | -37.38% | -50.07% | 61.27% | -0.826 | [-2.720, 0.913] | -1.156 | 51.35% | -0.975 | 7.17% | 0.884 |
| up_high | 32 | 2.43% | 31.53% | 67.98% | 0.732 | [-3.062, 5.648] | 1.082 | 15.07% | 2.092 | 7.39% | 1.109 |
| up_low | 614 | 146.63% | 71.03% | 43.03% | 1.460 | [0.096, 2.757] | 2.395 | 28.58% | 2.485 | 4.61% | 1.251 |
| up_mid | 208 | 19.75% | 37.20% | 52.92% | 0.860 | [-1.134, 2.908] | 1.309 | 29.57% | 1.258 | 5.77% | 1.131 |

## Benchmarks

| benchmark | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B&H BTC | 1529 | 48.01% | 9.81% | 52.17% | 0.440 | [-0.537, 1.484] | 0.643 | 66.94% | 0.147 | 6.27% | 1.070 |
| B&H basket (EW) | 1529 | -43.06% | -12.58% | 72.58% | 0.180 | [-0.787, 1.255] | 0.253 | 77.03% | -0.163 | 8.86% | 1.026 |

## Notes

- Benchmarks are not trials (PLAN §2.1). Vol matching is done per candidate in each family report.
