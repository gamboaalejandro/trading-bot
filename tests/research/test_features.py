"""Features and ex-ante regime cells (PLAN R04, §3.1-§3.2).

Unit tests use small deterministic hand-built fixtures (allowed for formula
checks, PLAN §6.1); the integration test reads the real data under
/home/user/harness/data and is skipped when it is not present.
"""
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apps.research.features import candles, funding as fnd, regime, trend, volatility as vol
from apps.research.features.volatility import FeatureError
from apps.research.portfolio.sizing import ewma_corr as sizing_ewma_corr

DAY = pd.Timedelta(days=1)


# ------------------------------------------------------------------ fixtures
def _ohlcv(n=700, seed=7, start="2020-01-01", freq="1D", hole=None):
    """Deterministic random-walk OHLCV fixture (formula tests only, never a backtest)."""
    rng = np.random.RandomState(seed)
    ret = rng.normal(0.0005, 0.03, n)
    close = 100.0 * np.exp(np.cumsum(ret))
    open_ = np.r_[100.0, close[:-1]] * np.exp(rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.01, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.01, n)))
    volume = rng.uniform(50, 150, n)
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC", name="open_time")
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx)
    if hole is not None:
        df.iloc[hole] = np.nan
    return df


@pytest.fixture(scope="module")
def daily():
    return _ohlcv(hole=450)


def _funding(index_start="2019-12-25", n=2400, seed=3):
    rng = np.random.RandomState(seed)
    idx = pd.date_range(index_start, periods=n, freq="8h", tz="UTC", name="settlement_time")
    return pd.Series(0.0001 + rng.normal(0, 0.0001, n), index=idx, name="funding_rate")


def _same(a, b):
    """Equality for floats (NaN == NaN) and labels (None == None)."""
    if isinstance(a, float) or isinstance(b, float) or a is None or b is None:
        if a is None or b is None:
            return (a is None or (isinstance(a, float) and math.isnan(a))) and \
                   (b is None or (isinstance(b, float) and math.isnan(b)))
        if math.isnan(a) or math.isnan(b):
            return math.isnan(a) and math.isnan(b)
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    return a == b


def _assert_row_equal(full, trunc, t):
    if isinstance(full, pd.Series):
        assert _same(full.loc[t], trunc.loc[t]), (full.name, t, full.loc[t], trunc.loc[t])
        return
    for col in full.columns:
        assert _same(full.loc[t, col], trunc.loc[t, col]), (col, t, full.loc[t, col], trunc.loc[t, col])


TRUNC_POS = [5, 30, 199, 250, 366, 449, 450, 451, 520, 699]

DAILY_FEATURES = {
    "body_atr": candles.body_atr,
    "upper_wick_atr": candles.upper_wick_atr,
    "lower_wick_atr": candles.lower_wick_atr,
    "range_atr": candles.range_atr,
    "close_loc": candles.close_loc,
    "rvol": candles.rvol,
    "gap": candles.gap,
    "candle_features": candles.candle_features,
    "atr": vol.atr,
    "atr_pct": vol.atr_pct,
    "atr_pct_pctl": vol.atr_pct_pctl,
    "sigma_30": lambda d: vol.sigma_30(d["close"]),
    "sigma_90": lambda d: vol.sigma_90(d["close"]),
    "volatility_features": vol.volatility_features,
    "sma_ratio_50": lambda d: trend.sma_ratio(d["close"], 50),
    "sma_ratio_100": lambda d: trend.sma_ratio(d["close"], 100),
    "sma_ratio_200": lambda d: trend.sma_ratio(d["close"], 200),
    "ema_20": lambda d: trend.ema(d["close"], 20),
    "sma50_gt_sma200": lambda d: trend.sma50_gt_sma200(d["close"]),
    "slope_sma50": lambda d: trend.slope_sma50(d["close"]),
    "adx14": lambda d: trend.adx(d, 14, return_di=True),
    "er30": lambda d: trend.er(d["close"], 30),
    "donchian_20": lambda d: trend.donchian(d["close"], 20),
    "donchian_pos_20": lambda d: trend.donchian_pos(d["close"], 20),
    "dist_52w_high": trend.dist_52w_high,
    "dd_365": lambda d: trend.dd_365(d["close"]),
    "trend_features": trend.trend_features,
    "regime_cells": regime.regime_cells,
    "ex_ante_cells": regime.ex_ante_cells,
}


# ------------------------------------------------------------------ causality
@pytest.mark.parametrize("name", sorted(DAILY_FEATURES))
def test_truncating_at_t_does_not_change_value_at_t(daily, name):
    fn = DAILY_FEATURES[name]
    full = fn(daily)
    assert len(full) == len(daily)
    for k in TRUNC_POS:
        t = daily.index[k]
        trunc = fn(daily.iloc[: k + 1])
        _assert_row_equal(full, trunc, t)
    # the features are not trivially NaN at the end of the sample
    last = full.iloc[-1]
    assert pd.notna(last).any() if isinstance(last, pd.Series) else pd.notna(last)


def test_causality_ewma_corr_to(daily):
    other = _ohlcv(seed=11)
    rets = pd.DataFrame({"BTC": vol.log_returns(daily["close"]), "ALT": vol.log_returns(other["close"])})
    full = vol.ewma_corr_to(rets, "BTC")
    for k in TRUNC_POS:
        t = rets.index[k]
        _assert_row_equal(full, vol.ewma_corr_to(rets.iloc[: k + 1], "BTC"), t)


def test_causality_funding_features(daily):
    f = _funding()
    full = fnd.funding_features(f, daily.index)
    assert full["fund_pct"].notna().sum() > 100
    for k in TRUNC_POS:
        t = daily.index[k]
        close_t = t + DAY
        trunc = fnd.funding_features(f[f.index <= close_t], daily.index[: k + 1])
        _assert_row_equal(full, trunc, t)


def test_causality_daily_asof_intraday(daily):
    cells = regime.regime_cells(daily)
    h4 = pd.date_range(daily.index[0], daily.index[-1] + pd.Timedelta(hours=20), freq="4h", tz="UTC")
    full = regime.daily_asof(cells, h4, "4h")
    for k in [10, 1500, 2399, 3000, len(h4) - 1]:
        t = h4[k]
        close_t = t + pd.Timedelta(hours=4)
        trunc = regime.daily_asof(cells[cells.index + DAY <= close_t], h4[: k + 1], "4h")
        _assert_row_equal(full, trunc, t)


# ------------------------------------------------------------------ ATR (Wilder) by hand
HAND = pd.DataFrame(
    {
        "open": [9.0, 9.5, 12.5, 13.0, 11.0],
        "high": [10.0, 11.0, 14.0, 13.5, 12.0],
        "low": [8.0, 9.0, 12.0, 10.0, 11.0],
        "close": [9.0, 10.5, 13.0, 11.0, 11.5],
        "volume": [1.0, 2.0, 3.0, 4.0, 5.0],
    },
    index=pd.date_range("2021-01-01", periods=5, freq="1D", tz="UTC"),
)


def test_true_range_by_hand():
    # TR0 = H-L = 2; TR1 = max(2, |11-9|, |9-9|) = 2; TR2 = max(2, 14-10.5, |12-10.5|) = 3.5
    # TR3 = max(3.5, |13.5-13|, |10-13|) = 3.5; TR4 = max(1, |12-11|, |11-11|) = 1
    assert vol.true_range(HAND).tolist() == [2.0, 2.0, 3.5, 3.5, 1.0]


def test_atr_wilder_by_hand():
    a = vol.atr(HAND, 3)
    # seed = mean(2, 2, 3.5) = 2.5; then ATR = (2 * prev + TR) / 3
    assert a.iloc[:2].isna().all()
    assert a.iloc[2] == pytest.approx(2.5)
    assert a.iloc[3] == pytest.approx(8.5 / 3)      # (2*2.5 + 3.5) / 3
    assert a.iloc[4] == pytest.approx(20.0 / 9)     # (2*8.5/3 + 1) / 3
    assert vol.atr_pct(HAND, 3).iloc[4] == pytest.approx((20.0 / 9) / 11.5)


def test_atr14_matches_reference_loop(daily):
    d = daily.iloc[:300]
    h, l, c = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(d))]
    ref = [math.nan] * 13 + [sum(tr[:14]) / 14]
    for i in range(14, len(d)):
        ref.append((ref[-1] * 13 + tr[i]) / 14)
    np.testing.assert_allclose(vol.atr(d).to_numpy(), np.array(ref), rtol=1e-12, equal_nan=True)


def test_wilder_skips_missing_bars_without_filling():
    x = pd.Series([1.0, 2.0, 3.0, np.nan, 6.0])
    out = vol.wilder_smooth(x, 3)
    assert out.iloc[2] == pytest.approx(2.0)
    assert math.isnan(out.iloc[3])
    assert out.iloc[4] == pytest.approx(2.0 + (6.0 - 2.0) / 3)
    # TR after a hole only uses H-L (previous close is not forward-filled)
    d = HAND.copy()
    d.iloc[2] = np.nan
    tr = vol.true_range(d)
    assert math.isnan(tr.iloc[2]) and tr.iloc[3] == pytest.approx(3.5)


# ------------------------------------------------------------------ Donchian on closes
def test_donchian_uses_closes_of_previous_n_bars():
    close = pd.Series([1.0, 3.0, 2.0, 5.0, 4.0, 6.0])
    ch = trend.donchian(close, 3)
    assert ch.iloc[:3].isna().all().all()
    assert ch["up"].tolist()[3:] == [3.0, 5.0, 5.0]
    assert ch["dn"].tolist()[3:] == [1.0, 2.0, 2.0]
    assert ch["mid"].tolist()[3:] == [2.0, 3.5, 3.5]
    pos = trend.donchian_pos(close, 3)
    assert pos.iloc[5] == pytest.approx((6 - 2) / (5 - 2))   # breakout above the channel > 1


def test_donchian_ignores_highs_and_lows(daily):
    d = daily.iloc[:120].copy()
    base = trend.donchian(d["close"], 20)
    d["high"] = d["high"] * 5
    d["low"] = d["low"] / 5
    pd.testing.assert_frame_equal(base, trend.donchian(d["close"], 20))
    ref_up = d["close"].shift(1).rolling(20).max()
    pd.testing.assert_series_equal(base["up"], ref_up, check_names=False)


# ------------------------------------------------------------------ other formulas
def test_candle_formulas_by_hand():
    a = pd.Series(2.0, index=HAND.index)
    assert candles.body_atr(HAND, atr_series=a).iloc[2] == pytest.approx((13.0 - 12.5) / 2)
    assert candles.upper_wick_atr(HAND, atr_series=a).iloc[2] == pytest.approx((14.0 - 13.0) / 2)
    assert candles.lower_wick_atr(HAND, atr_series=a).iloc[2] == pytest.approx((12.5 - 12.0) / 2)
    assert candles.range_atr(HAND, atr_series=a).iloc[3] == pytest.approx(3.5 / 2)
    assert candles.close_loc(HAND).iloc[1] == pytest.approx((10.5 - 9) / 2)
    assert candles.gap(HAND).iloc[2] == pytest.approx(12.5 / 10.5 - 1)
    assert math.isnan(candles.gap(HAND).iloc[0])
    flat = HAND.copy()
    flat.loc[flat.index[0], ["high", "low"]] = 9.0
    assert math.isnan(candles.close_loc(flat).iloc[0])


def test_rvol_by_hand():
    df = pd.DataFrame({"volume": [1.0, 2.0, 3.0, 4.0, 10.0]})
    r = candles.rvol(df, 3)
    assert r.iloc[:2].isna().all()
    assert r.iloc[2] == pytest.approx(3 / 2)
    assert r.iloc[4] == pytest.approx(10 / 4)


def test_sigma_n_matches_numpy(daily):
    c = daily["close"].iloc[:200]
    s = vol.sigma_n(c, 30)
    lr = np.log(c / c.shift(1)).to_numpy()
    expected = np.std(lr[170:200], ddof=1) * math.sqrt(365)
    assert s.iloc[199] == pytest.approx(expected, rel=1e-12)
    assert vol.sigma_90(c).iloc[58] != vol.sigma_90(c).iloc[58]   # < 60 returns -> NaN
    assert vol.sigma_90(c).iloc[60] > 0


def test_sma_ema_slope_and_er():
    c = pd.Series(np.arange(1.0, 301.0))
    assert trend.sma(c, 50).iloc[49] == pytest.approx(25.5)
    assert trend.sma_ratio(c, 50).iloc[49] == pytest.approx(50 / 25.5 - 1)
    assert trend.sma50_gt_sma200(c).iloc[250] == 1.0
    assert math.isnan(trend.sma50_gt_sma200(c).iloc[198])
    s50 = c.rolling(50).mean()
    assert trend.slope_sma50(c).iloc[100] == pytest.approx(s50.iloc[100] / s50.iloc[80] - 1)
    ema = trend.ema(c, 10)
    ref = c.ewm(span=10, adjust=False).mean()
    assert math.isnan(ema.iloc[8]) and ema.iloc[50] == pytest.approx(ref.iloc[50])
    assert trend.er(c, 30).iloc[100] == pytest.approx(1.0)
    zig = pd.Series([1.0, 2.0] * 40)
    assert trend.er(zig, 30).iloc[-1] == pytest.approx(0.0)      # even lag: no net move
    assert trend.er(zig, 29).iloc[-1] == pytest.approx(1 / 29)


def test_adx_pure_uptrend_is_100_and_bounded(daily):
    n = 60
    up = pd.DataFrame({"high": np.arange(n) + 10.0, "low": np.arange(n) + 8.0, "close": np.arange(n) + 9.5})
    a = trend.adx(up, 14, return_di=True)
    assert a["adx"].iloc[:27].isna().all()
    assert a["adx"].iloc[27] == pytest.approx(100.0)
    assert (a["minus_di"].dropna() == 0).all()
    adx = trend.adx(daily, 14).dropna()
    assert ((adx >= 0) & (adx <= 100)).all() and len(adx) > 600


def test_dist_52w_high_and_dd(daily):
    d = daily.iloc[:400]
    dist = trend.dist_52w_high(d)
    t = 380
    assert dist.iloc[t] == pytest.approx(d["close"].iloc[t] / d["high"].iloc[t - 364 : t + 1].max() - 1)
    dd = trend.dd_365(d["close"])
    assert dd.iloc[t] == pytest.approx(d["close"].iloc[t] / d["close"].iloc[t - 364 : t + 1].max() - 1)
    assert (dd.dropna() <= 0).all() and dd.iloc[:364].isna().all()


def test_expanding_pctl_requires_history_and_is_0_100():
    x = pd.Series([3.0, 1.0, 2.0, 5.0, 4.0])
    p = vol.expanding_pctl(x, min_periods=3)
    assert p.iloc[:2].isna().all()
    assert p.iloc[2] == pytest.approx(200 / 3)   # 2 is >= 2 of {3, 1, 2}
    assert p.iloc[3] == pytest.approx(100.0)
    assert p.iloc[4] == pytest.approx(80.0)


def test_ewma_corr_to_matches_sizing_matrix(daily):
    a, b = daily["close"], _ohlcv(seed=5)["close"]
    rets = pd.DataFrame({"BTC": vol.log_returns(a), "ALT": vol.log_returns(b) + 0.5 * vol.log_returns(a)})
    series = vol.ewma_corr_to(rets, "BTC", lam=0.97)
    for k in [50, 300, 451, 699]:
        t = rets.index[k]
        m = sizing_ewma_corr(rets, t, lam=0.97)
        assert series.loc[t, "ALT"] == pytest.approx(m[1, 0], rel=1e-9)
        np.testing.assert_allclose(vol.ewma_corr(rets, t), m)
    assert series["BTC"].dropna().eq(1.0).all()


# ------------------------------------------------------------------ funding
def test_f_bar_3d_is_mean_of_last_9_settlements():
    f = _funding(n=30)
    fb = fnd.f_bar_3d(f)
    assert fb.iloc[:8].isna().all()
    assert fb.iloc[8] == pytest.approx(f.iloc[:9].mean())
    assert fb.iloc[29] == pytest.approx(f.iloc[21:30].mean())
    assert fnd.apr(0.0001) == pytest.approx(0.1095)


def test_f_bar_3d_missing_settlement_gives_nan_and_offgrid_ignored():
    f = _funding(n=30)
    holed = f.drop(f.index[12])
    fb = fnd.f_bar_3d(holed)
    assert fb.loc[f.index[12]:f.index[20]].isna().all()
    assert fb.loc[f.index[21]] == pytest.approx(f.iloc[13:22].mean())
    extra = pd.concat([f, pd.Series([0.5 / 100], index=[f.index[10] + pd.Timedelta(hours=4)])]).sort_index()
    pd.testing.assert_series_equal(fnd.f_bar_3d(extra), fnd.f_bar_3d(f), check_names=False)


def test_daily_alignment_uses_settlement_at_close_only():
    idx = pd.date_range("2022-01-01", periods=6, freq="8h", tz="UTC")
    f = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], index=idx) * 1e-4
    days = pd.date_range("2021-12-31", periods=3, freq="1D", tz="UTC")
    d = fnd.to_daily(f, days)
    # bar 2021-12-31 closes 2022-01-01 00:00 -> includes that settlement (1e-4)
    assert d.iloc[0] == pytest.approx(1e-4)
    # bar 2022-01-01 closes 2022-01-02 00:00 -> settlement at that instant (4e-4), not 08:00 (5e-4)
    assert d.iloc[1] == pytest.approx(4e-4)
    # bar 2022-01-02 closes 2022-01-03 00:00: the last print (16:00 on 01-02) is 8h old -> accepted
    assert d.iloc[2] == pytest.approx(6e-4)
    later = pd.date_range("2022-01-05", periods=1, freq="1D", tz="UTC")
    assert math.isnan(fnd.to_daily(f, later).iloc[0])     # stale values are not carried forward


def test_fund_pct_window_and_minimum(daily):
    f = _funding()
    ff = fnd.funding_features(f, daily.index)
    first_valid = ff["f_bar_3d"].first_valid_index()
    k0 = daily.index.get_loc(first_valid)
    assert ff["fund_pct"].iloc[: k0 + 179].isna().all()
    assert ff["fund_pct"].iloc[k0 + 179] == ff["fund_pct"].iloc[k0 + 179]
    k = 650
    win = ff["f_bar_3d"].iloc[k - 364 : k + 1]
    expected = (win <= win.iloc[-1]).mean() * 100
    assert ff["fund_pct"].iloc[k] == pytest.approx(expected)
    assert ff["apr_3d"].iloc[k] == pytest.approx(ff["f_bar_3d"].iloc[k] * 1095)
    assert ff.attrs["funding_verified"] is False


def test_bnb_funding_is_excluded():
    f = _funding(n=30)
    f.attrs["symbol"] = "BNBUSDT"
    with pytest.raises(FeatureError):
        fnd.f_bar_3d(f)
    with pytest.raises(Exception):
        fnd.load_funding_features("BNBUSDT", pd.DatetimeIndex([], tz="UTC"))


def test_basis():
    idx = pd.date_range("2022-01-01", periods=3, freq="4h", tz="UTC")
    perp = pd.DataFrame({"close": [101.0, 99.0, np.nan]}, index=idx)
    spot = pd.DataFrame({"close": [100.0, 100.0, 100.0]}, index=idx)
    b = fnd.basis(perp, spot)
    assert b.iloc[0] == pytest.approx(0.01) and b.iloc[1] == pytest.approx(-0.01)
    assert math.isnan(b.iloc[2])
    perp.attrs["tf"], spot.attrs["tf"] = "4h", "1h"
    with pytest.raises(FeatureError):
        fnd.basis(perp, spot)


# ------------------------------------------------------------------ regime cells
def test_tercile_cut_points():
    p = pd.Series([0.0, 33.0, 33.01, 67.0, 67.01, 100.0, np.nan])
    lab = regime._tercile(p)
    assert lab.iloc[:6].tolist() == ["low", "low", "mid", "mid", "high", "high"]
    assert pd.isna(lab.iloc[6])


def test_regime_cells_match_definition(daily):
    cells = regime.regime_cells(daily)
    c = daily["close"]
    s200 = c.rolling(200, min_periods=134).mean()   # one missing bar tolerated (2/3 rule)
    pctl = vol.expanding_pctl(vol.atr_pct(daily), 365)
    for k in [100, 380, 449, 450, 451, 600, 699]:
        t = daily.index[k]
        row = cells.loc[t]
        if pd.isna(s200.iloc[k]) or pd.isna(pctl.iloc[k]) or pd.isna(c.iloc[k]):
            assert pd.isna(row["cell"])
            continue
        tr = "up" if c.iloc[k] > s200.iloc[k] else "down"
        vt = "low" if pctl.iloc[k] <= 33 else ("mid" if pctl.iloc[k] <= 67 else "high")
        assert row["cell"] == f"{tr}_{vt}"
    labels = set(cells["cell"].dropna())
    assert labels <= set(regime.CELLS) and len(regime.CELLS) == 6
    assert len(labels) >= 3


def test_ex_ante_cells_apply_to_next_day_return(daily):
    cells = regime.regime_cells(daily)["cell"]
    ex = regime.ex_ante_cells(daily)
    assert pd.isna(ex.iloc[0])
    for k in [400, 451, 452, 500, 699]:
        assert _same(ex.iloc[k], cells.iloc[k - 1])
    assert pd.isna(ex.iloc[451]) and ex.iloc[452] == cells.iloc[451]


def test_daily_asof_uses_closed_daily_bar_only(daily):
    lab = regime.trend_btc(daily)
    t_day = daily.index[300]
    h1 = pd.date_range(t_day, periods=48, freq="1h", tz="UTC")
    out = regime.daily_asof(lab, h1, "1h")
    # bars of day t (closing before 00:00 of t+1) see day t-1's label
    assert (out.iloc[:23] == lab.iloc[299]).all()
    # the 23:00 bar closes at 00:00 of t+1, exactly when day t closes
    assert out.iloc[23] == lab.iloc[300]
    assert (out.iloc[24:47] == lab.iloc[300]).all()


def test_fng_features():
    idx = pd.date_range("2020-01-01", periods=10, freq="1D", tz="UTC")
    fng = pd.Series(np.arange(10.0) * 10, index=idx, name="fng")
    out = regime.fng_features(fng, min_days=5)
    assert out["fng_pctl"].iloc[:4].isna().all() and out["fng_pctl"].iloc[9] == pytest.approx(100.0)


def test_invalid_inputs():
    with pytest.raises(FeatureError):
        vol.atr(pd.DataFrame({"close": [1.0]}))
    with pytest.raises(FeatureError):
        trend.sma(pd.Series([1.0]), 0)
    with pytest.raises(FeatureError):
        vol.ewma_corr_to(pd.DataFrame({"A": [0.1]}), "B")


# ------------------------------------------------------------------ integration (real data)
DATA_ROOT = Path(os.environ.get("RESEARCH_DATA_ROOT", "/home/user/harness/data"))


@pytest.mark.skipif(not (DATA_ROOT / "spot" / "BTCUSDT_1d.csv").is_file(), reason="harness data not present")
def test_real_btc_features_are_causal():
    from apps.research.data.loader import load_ohlcv

    btc = load_ohlcv("BTCUSDT", "spot", "1d", root=DATA_ROOT)
    builders = [candles.candle_features, trend.trend_features, vol.volatility_features, regime.regime_cells]
    fulls = [b(btc) for b in builders]
    for t in ["2018-12-15", "2020-03-12", "2021-05-19", "2022-11-09"]:
        ts = pd.Timestamp(t, tz="UTC")
        trunc_df = btc.loc[:ts]
        for b, full in zip(builders, fulls):
            _assert_row_equal(full, b(trunc_df), ts)
    fut = load_ohlcv("BTCUSDT", "futures", "1d", root=DATA_ROOT)
    ff = fnd.load_funding_features("BTCUSDT", fut.index, root=DATA_ROOT)
    # BTC funding is in fraction: median of the 3-day mean around 1e-4
    assert 2e-5 < ff["f_bar_3d"].median() < 3e-4
