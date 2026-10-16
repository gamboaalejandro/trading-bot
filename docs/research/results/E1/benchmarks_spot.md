# E1 — Benchmarks spot

Generated 2026-10-15 20:50 UTC. Market: **spot**. Trials: none (not a trial). Holdout: closed.

## Warnings

- **Survivorship bias.** Every symbol of the universe is still listed in 2026; delisted coins (LUNA, FTT, SRM and others) are missing. Conclusions focus on BTC/ETH and every basket result carries this warning (PLAN §5.1).
- Published figures (papers, debate) are not targets; only these OOS numbers count.

## Data provenance

- Harness git sha: `6dac91d09d8fdf224327bfc08bb3a594b05fb153`
- Data commits (upstream sources): futures `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, funding `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, spot `4d33a56f2b3930376fc778522770c6e84855be7e`
- Manifest digest: `6a8d22c62ab7b9a6fb786f025f1368072feec33f88658ac97b4d2400cb6b75fe`

<details><summary>CSV SHA-256 (9 files)</summary>

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
| OOS | 1529 | 48.07% | 9.82% | 52.09% | 0.440 | [-0.538, 1.486] | 0.643 | 66.93% | 0.147 | 6.26% | 1.070 |

## By year

| year | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | 365 | -64.21% | -64.21% | 63.74% | -1.288 | [-2.824, 0.229] | -1.695 | 66.93% | -0.959 | 8.68% | 0.819 |
| 2023 | 365 | 155.61% | 155.61% | 44.06% | 2.349 | [0.409, 4.289] | 4.122 | 20.00% | 7.779 | 4.45% | 1.451 |
| 2024 | 366 | 121.31% | 120.83% | 53.08% | 1.756 | [-0.157, 3.690] | 2.833 | 26.15% | 4.620 | 5.54% | 1.291 |
| 2025 | 365 | -6.33% | -6.33% | 41.69% | 0.051 | [-1.673, 1.843] | 0.073 | 32.02% | -0.198 | 4.89% | 1.007 |
| 2026 | 68 | -21.92% | -73.51% | 63.78% | -1.762 | [-4.827, 2.049] | -2.367 | 35.11% | -2.094 | 7.58% | 0.755 |

## By symbol

_Single series: no per-symbol breakdown available._

## By regime (ex-ante cell: trend_BTC x vol tercile)

| regime | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| down_high | 100 | 41.39% | 254.00% | 69.36% | 2.163 | [-0.922, 5.182] | 3.745 | 21.82% | 11.638 | 6.30% | 1.368 |
| down_low | 298 | -33.51% | -39.34% | 49.46% | -0.759 | [-2.636, 1.713] | -0.972 | 51.48% | -0.764 | 7.30% | 0.885 |
| down_mid | 277 | -47.91% | -57.66% | 62.42% | -1.061 | [-2.490, 0.475] | -1.422 | 53.37% | -1.080 | 8.06% | 0.852 |
| up_high | 20 | 9.37% | 412.97% | 69.90% | 2.672 | [n/a, n/a] | 4.636 | 11.35% | 36.377 | 5.15% | 1.461 |
| up_low | 662 | 201.86% | 83.89% | 43.91% | 1.605 | [0.243, 2.953] | 2.639 | 22.29% | 3.764 | 4.70% | 1.278 |
| up_mid | 172 | -8.42% | -17.03% | 53.01% | -0.089 | [-2.141, 2.102] | -0.127 | 32.80% | -0.519 | 6.15% | 0.987 |

## Benchmarks

| benchmark | n_days | total_return | cagr | vol | sharpe | sharpe_ci | sortino | max_dd | mar | cvar95 | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B&H BTC | 1529 | 48.07% | 9.82% | 52.09% | 0.440 | [-0.538, 1.486] | 0.643 | 66.93% | 0.147 | 6.26% | 1.070 |
| B&H basket (EW) | 1529 | -43.62% | -12.79% | 72.17% | 0.173 | [-0.792, 1.255] | 0.244 | 77.24% | -0.166 | 8.83% | 1.025 |

## Notes

- Benchmarks are not trials (PLAN §2.1). Vol matching is done per candidate in each family report.
