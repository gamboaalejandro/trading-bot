"""Tests for apps.research.strategies.breakout4h (PLAN §2.6, §6.2 R10).

Small hand-built deterministic fixtures; the integration test reads the real
local data in the debug window (2020-09 .. 2021-12) and is skipped without it.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apps.research.engine.costs import CostModel
from apps.research.engine.event_bt import run_event_bt
from apps.research.features.volatility import atr
from apps.research.strategies._intraday import StrategyError
from apps.research.strategies.base import Context, EventStrategy, Position
from apps.research.strategies.breakout4h import (
    BRK4H_CONFIGS,
    Breakout4H,
    breakout_features,
    entry_side,
    long_regime,
    make_breakout4h,
    short_regime,
)

ZERO = CostModel(spot_fee=0.0, fut_taker=0.0, fut_maker=0.0)
B1 = BRK4H_CONFIGS["B1"]


def row(**kw):
    base = dict(close=110.0, high=111.0, low=104.0, hh=105.0, ll=90.0, mid=100.0, atr=2.0, rvol=2.0,
                close_loc=0.85, d_close=110.0, d_sma=100.0, d_adx=25.0, btc_d_close=50.0, btc_d_sma=60.0,
                apr_3d=0.10, fund_pct=50.0)
    base.update(kw)
    return pd.Series(base)


def short_row(**kw):
    base = dict(close=85.0, high=91.0, low=84.0, hh=105.0, ll=90.0, mid=100.0, d_close=90.0, d_sma=100.0,
                close_loc=0.1)
    base.update(kw)
    return row(**base)


def daily_from(df):
    d = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    d["quote_volume"] = d["volume"] * d["close"]
    return d


def trend_4h(n_days=140, seed=3, start="2024-01-01"):
    """Deterministic 4h path: up-trend, then a sharp reversal in the last 20 days."""
    rng = np.random.default_rng(seed)
    n = 6 * n_days
    steps = np.where(np.arange(n) < n - 120, 0.004, -0.012) + rng.normal(0, 0.006, n)
    close = 100.0 * np.exp(np.cumsum(steps))
    open_ = np.r_[100.0, close[:-1]]
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.003, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.003, n)))
    vol = 1e6 * (1 + np.abs(rng.normal(0, 0.5, n)))
    idx = pd.date_range(start, periods=n, freq="4h", tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol}, index=idx)


# --------------------------------------------------------------------------- configurations
def test_configs_b1_to_b5_follow_the_plan():
    assert set(BRK4H_CONFIGS) == {"B1", "B2", "B3", "B4", "B5"}
    b1 = BRK4H_CONFIGS["B1"]
    assert b1["n"] == 20 and b1["use_adx"] and b1["use_funding"] and not b1["use_volume"]
    assert b1["sma_n"] == 100 and b1["adx_min"] == 20 and b1["stop_atr"] == 2.5 and b1["trail_atr"] == 3.0
    assert b1["apr_long_max"] == 0.5 and b1["fund_pct_max"] == 95 and b1["apr_short_min"] == -0.30
    diff = {k: {p: v for p, v in c.items() if b1[p] != v} for k, c in BRK4H_CONFIGS.items()}
    assert diff == {"B1": {}, "B2": {"n": 55}, "B3": {"use_adx": False}, "B4": {"use_funding": False},
                    "B5": {"use_volume": True}}
    b5 = BRK4H_CONFIGS["B5"]
    assert b5["rvol_min"] == 1.5 and b5["close_loc_min"] == 0.7 and b5["rvol_n"] == 20
    s = make_breakout4h("B3")
    assert isinstance(s, EventStrategy) and s.name == "BRK4H-B3" and s.params["config"] == "B3"
    assert s.n_free_params < Breakout4H("B1").n_free_params < Breakout4H("B5").n_free_params
    with pytest.raises(StrategyError):
        Breakout4H("B9")
    with pytest.raises(StrategyError):
        Breakout4H("B1", foo=1)


# --------------------------------------------------------------------------- entry rules
def test_long_entry_needs_a_breakout_above_the_previous_highs_and_the_daily_regime():
    assert entry_side(row(), B1, "spot") == 1
    assert entry_side(row(close=105.0), B1, "spot") == 0           # strict: C > max(H)
    assert entry_side(row(d_close=99.0), B1, "spot") == 0          # C_1d < SMA100
    assert entry_side(row(d_sma=np.nan), B1, "spot") == 0          # regime unknown
    assert entry_side(row(atr=np.nan), B1, "spot") == 0


def test_adx_filter_and_its_ablation_b3():
    r = row(d_adx=15.0)
    assert not long_regime(r, B1) and entry_side(r, B1, "spot") == 0
    assert long_regime(r, BRK4H_CONFIGS["B3"]) and entry_side(r, BRK4H_CONFIGS["B3"], "spot") == 1
    assert entry_side(row(d_adx=20.0), B1, "spot") == 1            # ADX >= 20 inclusive


@pytest.mark.parametrize("kw", [{"apr_3d": 0.51}, {"fund_pct": 96.0}])
def test_funding_filter_blocks_crowded_longs_and_b4_ignores_it(kw):
    assert entry_side(row(**kw), B1, "futures") == 0
    assert entry_side(row(**kw), BRK4H_CONFIGS["B4"], "futures") == 1


def test_unknown_funding_does_not_block_and_limits_are_inclusive():
    assert entry_side(row(apr_3d=np.nan, fund_pct=np.nan), B1, "futures") == 1
    assert entry_side(row(apr_3d=0.5, fund_pct=95.0), B1, "futures") == 1


def test_b5_volume_and_close_location_filter():
    b5 = BRK4H_CONFIGS["B5"]
    assert entry_side(row(rvol=1.5, close_loc=0.7), b5, "spot") == 1
    assert entry_side(row(rvol=1.4, close_loc=0.9), b5, "spot") == 0
    assert entry_side(row(rvol=2.0, close_loc=0.6), b5, "spot") == 0
    assert entry_side(row(rvol=np.nan), b5, "spot") == 0
    assert entry_side(row(rvol=1.0, close_loc=0.1), B1, "spot") == 1   # B1 has no volume filter


def test_short_only_in_perps_with_btc_below_sma200_and_funding_veto():
    r = short_row()
    assert short_regime(r, B1, "futures") and entry_side(r, B1, "futures") == -1
    assert entry_side(r, B1, "spot") == 0                                  # no shorts in spot
    assert entry_side(short_row(btc_d_close=70.0), B1, "futures") == 0    # BTC above SMA200
    assert entry_side(short_row(btc_d_close=np.nan), B1, "futures") == 0
    assert entry_side(short_row(d_adx=10.0), B1, "futures") == 0
    assert entry_side(short_row(apr_3d=-0.31), B1, "futures") == 0         # shorts would pay > 30 %
    assert entry_side(short_row(apr_3d=-0.31), BRK4H_CONFIGS["B4"], "futures") == -1
    assert entry_side(short_row(close_loc=0.5), BRK4H_CONFIGS["B5"], "futures") == 0
    assert entry_side(short_row(close_loc=0.3), BRK4H_CONFIGS["B5"], "futures") == -1


# --------------------------------------------------------------------------- features
def test_channel_excludes_the_current_bar_and_mid_uses_closes():
    df = trend_4h(30)
    f = breakout_features(df, daily_from(df), {**B1, "n": 5})
    i = 50
    assert f["hh"].iloc[i] == pytest.approx(df["high"].iloc[i - 5:i].max())
    assert f["ll"].iloc[i] == pytest.approx(df["low"].iloc[i - 5:i].min())
    mid = (df["close"].iloc[i - 5:i].max() + df["close"].iloc[i - 5:i].min()) / 2
    assert f["mid"].iloc[i] == pytest.approx(mid)
    assert f["atr"].iloc[i] == pytest.approx(atr(df).iloc[i])
    assert f["hh"].iloc[:5].isna().all()


def test_regime_uses_only_the_closed_daily_bar():
    df = trend_4h(130)
    daily = daily_from(df)
    f = breakout_features(df, daily, B1)
    day = daily.index[120]
    bars = df.loc[day:day + pd.Timedelta(hours=20)].index
    # 00:00..16:00 bars close before the day closes: they see the previous day.
    assert (f.loc[bars[:5], "d_close"] == daily["close"].iloc[119]).all()
    # The 20:00 bar closes at 24:00 together with the day.
    assert f.loc[bars[5], "d_close"] == daily["close"].iloc[120]
    # Changing the day's bar cannot change decisions taken before it closed.
    d2 = daily.copy()
    d2.iloc[120, :4] = [1.0, 1.0, 1.0, 1.0]
    f2 = breakout_features(df, d2, B1)
    pd.testing.assert_frame_equal(f.loc[:bars[4]], f2.loc[:bars[4]])
    assert f2.loc[bars[5], "d_close"] == 1.0


def test_features_are_invariant_to_truncation():
    df = trend_4h(130)
    daily = daily_from(df)
    btc = daily.copy()
    full = breakout_features(df, daily, B1, btc_daily=btc)
    for k in (700, 701, 705):
        t = df.index[k - 1]
        d_tr = daily[daily.index + pd.Timedelta(days=1) <= t + pd.Timedelta(hours=4)]
        part = breakout_features(df.iloc[:k], d_tr, B1, btc_daily=d_tr)
        pd.testing.assert_series_equal(part.iloc[-1], full.iloc[k - 1], check_names=False)


def test_funding_features_are_known_at_the_bar_close():
    df = trend_4h(10)
    taus = pd.date_range(df.index[0] - pd.Timedelta(days=5), df.index[-1], freq="8h", tz="UTC")
    fund = pd.Series(1e-4, index=taus, name="funding_rate")
    fund.iloc[-10:] = 5e-4
    f = breakout_features(df, daily_from(df), B1, funding=fund)
    jump = fund.index[-10]
    # The 4h bar opening at ``jump - 4h`` closes at ``jump``: it already sees that settlement.
    t = jump - pd.Timedelta(hours=4)
    expected = (1e-4 * 8 + 5e-4) / 9 * 3 * 365
    assert f.loc[t, "apr_3d"] == pytest.approx(expected)
    assert f.loc[t - pd.Timedelta(hours=4), "apr_3d"] == pytest.approx(1e-4 * 3 * 365)


# --------------------------------------------------------------------------- on_bar
def _ctx_with(df, market="spot", position=None):
    ctx = Context(market=market, t=df.index[-1], nav=10_000.0)
    ctx.frames = {"SOLUSDT": df}
    ctx.tf = pd.Timedelta(hours=4)
    ctx.positions = {} if position is None else {"SOLUSDT": position}
    return ctx


def _strategy_with_row(df, r, config="B1"):
    s = Breakout4H(config)
    feats = pd.DataFrame([r.to_dict()], index=[df.index[-1]])
    s._cache.frames = {"SOLUSDT": feats}
    return s


def test_entry_intent_has_the_initial_stop_on_the_exchange():
    df = trend_4h(5)
    s = _strategy_with_row(df, row())
    out = s.on_bar(df.index[-1], {"SOLUSDT": df.iloc[-1]}, _ctx_with(df))
    assert len(out) == 1
    it = out[0]
    assert it.side == "BUY" and not it.reduce_only and it.qty is None and it.target_weight is None
    assert it.stop_price == pytest.approx(110.0 - 2.5 * 2.0)


def test_chandelier_trailing_only_tightens():
    df = trend_4h(5)
    entry_t = df.index[-6]
    hh = df["high"].loc[entry_t:].max()
    r = row(close=hh - 1.0, mid=0.0, atr=1.0)
    expected = hh - 3.0
    pos = Position("SOLUSDT", 1, 1.0, 100.0, entry_t, stop=expected - 5.0)
    s = _strategy_with_row(df, r)
    out = s.on_bar(df.index[-1], {"SOLUSDT": df.iloc[-1]}, _ctx_with(df, position=pos))
    assert len(out) == 1 and out[0].reduce_only and out[0].side == "SELL"
    assert out[0].stop_price == pytest.approx(expected)
    # A chandelier below the current stop is never sent.
    pos2 = Position("SOLUSDT", 1, 1.0, 100.0, entry_t, stop=expected + 0.5)
    assert s.on_bar(df.index[-1], {"SOLUSDT": df.iloc[-1]}, _ctx_with(df, position=pos2)) == []
    # Shorts: min(L since entry) + 3 ATR, only downwards.
    ll = df["low"].loc[entry_t:].min()
    spos = Position("SOLUSDT", -1, 1.0, 100.0, entry_t, stop=ll + 10.0)
    s2 = _strategy_with_row(df, row(close=ll + 1.0, mid=1e9, atr=1.0, d_close=90.0, d_sma=100.0))
    out = s2.on_bar(df.index[-1], {"SOLUSDT": df.iloc[-1]}, _ctx_with(df, "futures", spos))
    assert out[0].side == "BUY" and out[0].stop_price == pytest.approx(ll + 3.0)


@pytest.mark.parametrize("kw,tag", [({"close": 99.0}, "mid"), ({"d_close": 95.0}, "regime")])
def test_exit_below_mid_or_when_the_daily_regime_inverts(kw, tag):
    df = trend_4h(5)
    pos = Position("SOLUSDT", 1, 1.0, 100.0, df.index[-3], stop=50.0)
    s = _strategy_with_row(df, row(**kw))
    out = s.on_bar(df.index[-1], {"SOLUSDT": df.iloc[-1]}, _ctx_with(df, position=pos))
    assert len(out) == 1 and out[0].is_exit and out[0].side == "SELL"
    assert out[0].tag.endswith(tag)


# --------------------------------------------------------------------------- engine
def _run(strat, df, market="spot", **kw):
    daily = daily_from(df)
    return run_event_bt(strat, {"SOLUSDT": df}, market, ZERO, None, daily={"SOLUSDT": daily},
                        fixed_slip_bps=0.0, **kw)


def test_backtest_prepared_equals_lazy_and_respects_the_rules():
    df = trend_4h(140)
    daily = daily_from(df)
    start = df.index[6 * 110]
    prepared = Breakout4H("B3").prepare({"SOLUSDT": df}, {"SOLUSDT": daily})
    res_p = _run(prepared, df, start=start)
    res_l = _run(Breakout4H("B3"), df, start=start)
    rt_p, rt_l = res_p.meta["round_trips"], res_l.meta["round_trips"]
    assert len(rt_p) >= 1
    pd.testing.assert_frame_equal(rt_p, rt_l)
    pd.testing.assert_series_equal(res_p.equity, res_l.equity)
    f = prepared.features("SOLUSDT")
    for tr in rt_p.itertuples():
        t_dec = df.index[df.index.get_loc(tr.entry_time) - 1]
        r = f.loc[t_dec]
        assert r["close"] > r["hh"] and long_regime(r, prepared.params)
        assert tr.side == 1
    assert res_p.meta["counters"]["stop_loosen_ignored"] == 0


@pytest.mark.skipif(not (Path("/home/user/harness/data") / "futures" / "BTCUSDT_4h.csv").exists(),
                    reason="local data not available")
def test_real_futures_debug_window_runs_with_funding():
    from apps.research.data.loader import load_funding, load_ohlcv

    syms = ["BTCUSDT", "ETHUSDT"]
    h4 = {s: load_ohlcv(s, "futures", "4h", "2020-09-01", "2021-12-31") for s in syms}
    d1 = {s: load_ohlcv(s, "futures", "1d", "2020-09-01", "2021-12-31") for s in syms}
    fund = {s: load_funding(s) for s in syms}
    strat = Breakout4H("B1").prepare(h4, d1, fund)
    res = run_event_bt(strat, h4, "futures", CostModel(), None, start="2021-01-01", end="2021-12-31",
                       daily=d1, funding=fund)
    rt = res.meta["round_trips"]
    assert len(rt) > 0 and np.isfinite(res.equity).all()
    for tr in rt.itertuples():
        t_dec = h4[tr.symbol].index[h4[tr.symbol].index.get_loc(tr.entry_time) - 1]
        r = strat.features(tr.symbol).loc[t_dec]
        assert entry_side(r, strat.params, "futures") == tr.side
