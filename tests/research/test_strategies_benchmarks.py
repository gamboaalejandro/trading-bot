"""Tests for apps.research.strategies.benchmarks (PLAN §2.11, §6.2 R13).

Small deterministic fixtures check the mechanics (no backtest result is drawn
from them); the integration test reads the real local data and is skipped
without it.
"""
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apps.research.engine.costs import CostModel
from apps.research.engine.event_bt import run_event_bt
from apps.research.strategies.base import OrderIntent
from apps.research.strategies.benchmarks import (
    BenchmarkError,
    RandomEntryEventStrategy,
    RandomEntryResult,
    bh_returns,
    entry_schedule,
    exposure_episodes,
    permute_episodes,
    random_entry_event_test,
    random_entry_event_wf_test,
    random_entry_weights_test,
    random_weight_paths,
    selection_segments,
    vol_matched_benchmarks,
    vol_matched_bh,
    weights_returns,
    wf_event_oos,
)

IDX = pd.date_range("2024-01-01", periods=200, freq="1D", tz="UTC")


def zigzag_closes(n=200, symbols=("BTCUSDT", "ETHUSDT", "SOLUSDT")):
    """Deterministic price paths (no randomness): distinct periodic patterns."""
    t = np.arange(n)
    out = {}
    for k, s in enumerate(symbols):
        out[s] = 100.0 * (1.0 + 0.05 * np.sin(t / (3.0 + k)) + 0.001 * t * (k + 1))
    return pd.DataFrame(out, index=IDX[:n])


def candidate_weights():
    w = pd.DataFrame(0.0, index=IDX, columns=["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    w.iloc[10:25, 0] = 0.30
    w.iloc[40:42, 0] = [0.10, 0.20]
    w.iloc[100:160, 0] = np.linspace(0.05, 0.35, 60)
    w.iloc[5:9, 1] = 0.2
    w.iloc[9:12, 1] = -0.1                      # sign flip: a separate episode
    w.iloc[150:190, 1] = 0.25
    return w


def episode_signature(series):
    return sorted((e.length, e.weights) for e in exposure_episodes(series))


# --------------------------------------------------------------------------- episodes
def test_exposure_episodes_split_on_zero_and_sign_flip():
    w = candidate_weights()
    eps = exposure_episodes(w["ETHUSDT"])
    assert [(e.start, e.length, e.sign) for e in eps] == [(5, 4, 1), (9, 3, -1), (150, 40, 1)]
    assert exposure_episodes(w["SOLUSDT"]) == []
    assert exposure_episodes(pd.Series([np.nan, 0.1, np.nan]))[0].length == 1


def test_permutation_keeps_durations_and_weights_without_overlap():
    w = candidate_weights()
    for seed in range(20):
        rng = np.random.default_rng(seed)
        for s in ["BTCUSDT", "ETHUSDT"]:
            p = permute_episodes(w[s], None, rng)
            assert episode_signature(p) == episode_signature(w[s])
            # Total exposure (sum of weights) and active days are preserved.
            assert p.sum() == pytest.approx(w[s].sum())
            assert (p != 0).sum() == (w[s] != 0).sum()


def test_permutation_stays_inside_the_symbol_life():
    w = candidate_weights()
    closes = zigzag_closes()
    closes.iloc[:60, 0] = np.nan                # BTC listed on day 60
    closes.iloc[180:, 0] = np.nan               # and delisted on day 180
    for seed in range(20):
        p = random_weight_paths(w, closes, seed)
        active = p["BTCUSDT"] != 0
        assert not active.iloc[:60].any() and not active.iloc[180:].any()
        assert episode_signature(p["BTCUSDT"]) == episode_signature(w["BTCUSDT"])
        assert (p["SOLUSDT"] == 0).all()


def test_permutation_that_cannot_fit_raises():
    w = pd.Series([0.5] * 10 + [0.0] * 10, index=IDX[:20])
    life = pd.Series([False] * 15 + [True] * 5, index=IDX[:20])
    with pytest.raises(BenchmarkError):
        permute_episodes(w, life, np.random.default_rng(0))


def test_seeds_are_reproducible_and_distinct():
    w, closes = candidate_weights(), zigzag_closes()
    a = random_weight_paths(w, closes, seed=7)
    b = random_weight_paths(w, closes, seed=7)
    c = random_weight_paths(w, closes, seed=8)
    pd.testing.assert_frame_equal(a, b)
    assert not a.equals(c)
    r1 = random_entry_weights_test(w, closes, n_seeds=10, seed0=3, cost_rate=0.0012)
    r2 = random_entry_weights_test(w, closes, n_seeds=10, seed0=3, cost_rate=0.0012)
    np.testing.assert_array_equal(r1.sharpes, r2.sharpes)
    assert r1.seeds == list(range(3, 13))


def test_default_is_100_seeds_and_percentile_rule():
    w, closes = candidate_weights(), zigzag_closes()
    res = random_entry_weights_test(w, closes)
    assert len(res.sharpes) == 100 and res.seeds == list(range(100))
    thr = np.percentile(res.sharpes[np.isfinite(res.sharpes)], 95)
    assert res.threshold == pytest.approx(thr)
    assert res.passed == (res.candidate_sharpe > thr)
    fake = RandomEntryResult(np.arange(100, dtype=float), 99.5, list(range(100)))
    assert fake.passed and fake.percentile == 100.0
    assert not RandomEntryResult(np.arange(100, dtype=float), 90.0, list(range(100))).passed


# --------------------------------------------------------------------------- evaluator
def test_weights_returns_accounting():
    closes = pd.DataFrame({"A": [100.0, 110.0, 99.0, 99.0]}, index=IDX[:4])
    w = pd.DataFrame({"A": [0.5, 0.5, 0.0, 0.0]}, index=IDX[:4])
    r = weights_returns(w, closes, cost_rate=0.001)
    # day0: entry cost 0.5*0.001; day1: 0.5*10%; day2: 0.5*(-10%) - exit cost 0.5*0.001.
    assert r.tolist() == pytest.approx([-0.0005, 0.05, -0.05 - 0.0005, 0.0])
    fund = pd.DataFrame({"A": [0.0, 0.0003, 0.0003, 0.0003]}, index=IDX[:4])
    r2 = weights_returns(w, closes, 0.0, funding_daily=fund)
    assert r2.iloc[1] == pytest.approx(0.05 - 0.5 * 0.0003)   # long pays positive funding


# --------------------------------------------------------------------------- vol matching
def test_vol_matched_bh_matches_the_candidate_vol():
    closes = zigzag_closes()
    cand = weights_returns(candidate_weights(), closes, 0.001).iloc[30:]
    scaled, k = vol_matched_bh(cand, bh_returns(closes["BTCUSDT"]))
    assert scaled.std(ddof=1) == pytest.approx(cand.std(ddof=1), rel=1e-12)
    assert scaled.index.equals(cand.index)
    raw = bh_returns(closes["BTCUSDT"]).loc[cand.index]
    np.testing.assert_allclose(scaled.to_numpy(), k * raw.to_numpy())
    out = vol_matched_benchmarks(cand, {s: closes[[s]].rename(columns={s: "close"}) for s in closes})
    for key in ("BTC", "basket"):
        assert out[key].std(ddof=1) == pytest.approx(cand.std(ddof=1), rel=1e-12)
    assert set(out["mult"]) == {"BTC", "basket"}


def test_basket_is_equal_weight_over_available_symbols():
    closes = pd.DataFrame({"A": [100.0, 110.0, 121.0], "B": [np.nan, 50.0, 45.0]}, index=IDX[:3])
    r = bh_returns(closes)
    assert np.isnan(r.iloc[0])
    assert r.iloc[1] == pytest.approx(0.10)                    # B has no return yet
    assert r.iloc[2] == pytest.approx((0.10 - 0.10) / 2)


# --------------------------------------------------------------------------- event strategies
def bars_4h(n=6 * 40):
    idx = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    t = np.arange(n)
    p = 100.0 * (1.0 + 0.03 * np.sin(t / 5.0))
    return pd.DataFrame({"open": p, "high": p * 1.002, "low": p * 0.998, "close": p, "volume": 1e6}, index=idx)


def to_daily(df):
    d = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    d["quote_volume"] = d["volume"] * d["close"]
    return d


class TimeExitCandidate:
    """Long every 30 bars, exits after ``hold`` bars (exit logic reads ctx.positions only)."""

    name = "toy"
    n_free_params = 0

    def __init__(self, hold=6, every=30):
        self.params = {"hold": hold, "stop_atr_mult": 2.0}
        self.every = every
        self.calls = 0

    def on_bar(self, t, bars, ctx):
        self.calls += 1
        out = []
        for s, b in bars.items():
            pos = ctx.positions.get(s)
            if pos is not None:
                if pos.bars_held >= self.params["hold"]:
                    out.append(OrderIntent(s, "SELL", reduce_only=True, tag="time_exit"))
            elif self.calls % self.every == 0:
                out.append(OrderIntent(s, "BUY", stop_price=float(b["close"]) * 0.9, tag="entry"))
        return out


def event_run(strategy, df):
    return run_event_bt(strategy, {"SOLUSDT": df}, "spot", CostModel(), None,
                        daily={"SOLUSDT": to_daily(df)}, fixed_slip_bps=2.0)


def test_entry_schedule_keeps_frequency_and_sides():
    df = bars_4h()
    cand = event_run(TimeExitCandidate(), df)
    rt = cand.meta["round_trips"]
    n = rt.drop_duplicates(["symbol", "entry_time"]).shape[0]
    assert n > 3
    s1 = entry_schedule(rt, {"SOLUSDT": df}, np.random.default_rng(1))
    s1b = entry_schedule(rt, {"SOLUSDT": df}, np.random.default_rng(1))
    s2 = entry_schedule(rt, {"SOLUSDT": df}, np.random.default_rng(2))
    assert len(s1["SOLUSDT"]) == n and s1 == s1b and s1 != s2
    assert all(t < df.index[-1] for t in s1["SOLUSDT"])
    assert sorted(s1["SOLUSDT"].values()) == sorted(rt.drop_duplicates(["symbol", "entry_time"])["side"])


def test_random_event_strategy_uses_candidate_exits():
    df = bars_4h()
    cand = event_run(TimeExitCandidate(), df)
    sched = entry_schedule(cand.meta["round_trips"], {"SOLUSDT": df}, np.random.default_rng(0))
    strat = RandomEntryEventStrategy(TimeExitCandidate(), sched)
    res = event_run(strat, df)
    rt = res.meta["round_trips"]
    assert len(rt) > 0
    assert "time_exit" in set(rt["exit_reason"])          # the candidate's exit rule
    assert set(rt["tag"]) == {"random_entry"}               # the entries are the random ones
    # Entries happen only at the scheduled bars (filled at the next open).
    sched_fill = {df.index[df.index.get_loc(t) + 1] for t in sched["SOLUSDT"]}
    assert set(rt["entry_time"]) <= sched_fill
    assert strat.entries_requested <= len(sched["SOLUSDT"])


def test_random_entry_event_test_is_reproducible():
    df = bars_4h()
    cand = event_run(TimeExitCandidate(), df)
    run = partial(event_run, df=df)
    a = random_entry_event_test(TimeExitCandidate, cand, run, {"SOLUSDT": df}, n_seeds=4, seed0=11)
    b = random_entry_event_test(TimeExitCandidate, cand, run, {"SOLUSDT": df}, n_seeds=4, seed0=11)
    np.testing.assert_array_equal(a.sharpes, b.sharpes)
    assert a.seeds == [11, 12, 13, 14]
    assert a.extra["candidate_entries"] == cand.meta["round_trips"].drop_duplicates(
        ["symbol", "entry_time"]).shape[0]
    assert all(r <= a.extra["candidate_entries"] for r in a.extra["entries_realized"])


# --------------------------------------------------------------------------- walk-forward event OOS
# 60 days of 4h bars; fold 0 tests days 20-39 (config "A"), fold 1 days 40-59 (config "B").
WF_DAYS = pd.date_range("2024-01-01", periods=60, freq="1D", tz="UTC")
WF_SEL = pd.DataFrame({
    "fold": [0, 1], "selected": ["A", "B"],
    "test_start": [WF_DAYS[20], WF_DAYS[40]], "test_end": [WF_DAYS[39], WF_DAYS[59]],
})


class WindowedCandidate(TimeExitCandidate):
    """``TimeExitCandidate(every_in)`` inside ``window``, a different entry rhythm outside it."""

    def __init__(self, window, every_in, every_out, hold=6):
        super().__init__(hold=hold, every=every_in)
        self.window, self.every_in, self.every_out = window, every_in, every_out

    def on_bar(self, t, bars, ctx):
        inside = self.window[0] <= t <= self.window[1]
        self.every = self.every_in if inside else self.every_out
        return super().on_bar(t, bars, ctx)


def _window(i):
    return WF_DAYS[[20, 40][i]], WF_DAYS[[39, 59][i]] + pd.Timedelta(hours=23)


def _makers(every_out_a, every_out_b):
    def make(cfg):
        if cfg == "A":
            return WindowedCandidate(_window(0), 30, every_out_a)
        return WindowedCandidate(_window(1), 25, every_out_b, hold=4)
    return make


def _window_run(df):
    def run(strat, s0, s1):
        return run_event_bt(strat, {"SOLUSDT": df}, "spot", CostModel(), None, s0, s1,
                            daily={"SOLUSDT": to_daily(df)}, fixed_slip_bps=2.0)
    return run


def test_selection_segments_merges_contiguous_same_config():
    sel = pd.DataFrame({"selected": ["A", "A", "B"],
                        "test_start": WF_DAYS[[0, 10, 20]], "test_end": WF_DAYS[[9, 19, 29]]})
    segs = selection_segments(sel)
    assert [s[0] for s in segs] == ["A", "B"]
    assert segs[0][1] == WF_DAYS[0] and segs[0][2] == WF_DAYS[19] + pd.Timedelta(days=1) - pd.Timedelta(1, "ns")
    with pytest.raises(BenchmarkError):
        selection_segments(sel.iloc[0:0])


def test_wf_event_oos_only_uses_chosen_test_windows():
    df = bars_4h(6 * 60)
    out = wf_event_oos(WF_SEL, _makers(30, 25), _window_run(df))
    assert out.returns.index.min() >= WF_DAYS[20] and out.returns.index.max() <= WF_DAYS[59]
    rt = out.round_trips
    assert len(rt) > 0 and set(rt["config"]) == {"A", "B"}
    for cfg, (t0, t1) in (("A", _window(0)), ("B", _window(1))):
        et = pd.to_datetime(rt.loc[rt["config"] == cfg, "entry_time"], utc=True)
        assert ((et >= t0) & (et <= t1)).all()
    assert len(out.trade_returns) == len(rt)


def test_candidate_sharpe_and_trades_ignore_performance_outside_chosen_windows():
    """Look-ahead guard: A outside fold 0 and B outside fold 1 must not matter (checks 3 and 10)."""
    df = bars_4h(6 * 60)
    run = _window_run(df)
    base, changed = _makers(30, 25), _makers(7, 3)
    # Sanity: over the whole window (the old, in-sample computation) the variants differ.
    full_a = run(base("A"), WF_DAYS[0], WF_DAYS[59])
    full_a2 = run(changed("A"), WF_DAYS[0], WF_DAYS[59])
    assert len(full_a.meta["round_trips"]) != len(full_a2.meta["round_trips"])

    r1 = random_entry_event_wf_test(base, run, {"SOLUSDT": df}, WF_SEL, n_seeds=3, seed0=5)
    r2 = random_entry_event_wf_test(changed, run, {"SOLUSDT": df}, WF_SEL, n_seeds=3, seed0=5)
    assert np.isfinite(r1.candidate_sharpe)
    assert r1.candidate_sharpe == r2.candidate_sharpe
    np.testing.assert_array_equal(r1.sharpes, r2.sharpes)
    assert r1.extra["candidate_entries"] == r2.extra["candidate_entries"] > 0
    assert [s[0] for s in r1.extra["segments"]] == ["A", "B"]
    o1, o2 = wf_event_oos(WF_SEL, base, run), wf_event_oos(WF_SEL, changed, run)
    pd.testing.assert_series_equal(o1.trade_returns, o2.trade_returns)
    pd.testing.assert_series_equal(o1.returns, o2.returns)
    assert r1.candidate_sharpe == o1.sharpe


def test_random_entry_wf_schedule_stays_in_segments():
    df = bars_4h(6 * 60)
    run = _window_run(df)
    seen = []

    def spy(strat, s0, s1):
        if isinstance(strat, RandomEntryEventStrategy):
            seen.append((s0, s1, {t for v in strat.schedule.values() for t in v}))
        return run(strat, s0, s1)

    cand = wf_event_oos(WF_SEL, _makers(30, 25), run)
    res = random_entry_event_wf_test(_makers(30, 25), spy, {"SOLUSDT": df}, WF_SEL, n_seeds=2, candidate=cand)
    assert len(seen) == 2 * 2
    for s0, s1, ts in seen:
        assert all(s0 <= t <= s1 for t in ts)
    per_seed = [len(ts) for _, _, ts in seen]
    assert per_seed[0] + per_seed[1] == res.extra["candidate_entries"]


# --------------------------------------------------------------------------- real data
DATA = Path("/home/user/harness/data")


@pytest.mark.skipif(not (DATA / "spot" / "BTCUSDT_1d.csv").exists(), reason="local data not available")
def test_integration_vol_matched_on_real_closes():
    from apps.research.data.loader import load_panel

    panel = load_panel(["BTCUSDT", "ETHUSDT"], "spot", "1d", "2019-01-01", "2020-08-31", root=DATA)
    closes = pd.DataFrame({s: df["close"] for s, df in panel.items()})
    w = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    w.iloc[50:120, 0] = 0.3
    w.iloc[300:400, 1] = 0.2
    cand = weights_returns(w, closes, 0.0012)
    out = vol_matched_benchmarks(cand, panel)
    common = cand.loc[out["BTC"].index]
    assert out["BTC"].std(ddof=1) == pytest.approx(common.std(ddof=1), rel=1e-9)
    res = random_entry_weights_test(w, closes, n_seeds=5)
    assert np.isfinite(res.sharpes).all()


def test_random_entry_wf_parallel_matches_serial():
    """Forked workers give exactly the serial result (each seed owns its RNG)."""
    df = bars_4h(6 * 60)
    run = _window_run(df)
    cand = wf_event_oos(WF_SEL, _makers(30, 25), run)
    r1 = random_entry_event_wf_test(_makers(30, 25), run, {"SOLUSDT": df}, WF_SEL, n_seeds=4, seed0=3,
                                    candidate=cand, n_jobs=1)
    r2 = random_entry_event_wf_test(_makers(30, 25), run, {"SOLUSDT": df}, WF_SEL, n_seeds=4, seed0=3,
                                    candidate=cand, n_jobs=2)
    np.testing.assert_array_equal(r1.sharpes, r2.sharpes)
    assert r1.extra["entries_requested"] == r2.extra["entries_requested"]
    assert r1.extra["entries_realized"] == r2.extra["entries_realized"]
