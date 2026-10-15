"""
PULLBACK: 1h entry overlay for TREND (PLAN.md §2.8).

The overlay only changes WHEN an exposure increase is bought. When the
discretised daily signal ``E_q,i`` rises at the close of day ``t`` (row ``t``),
TREND would buy at ``open[t+1]``. With the overlay the order waits, on CLOSED
1h bars, for one of these conditions:

- ``P1``: ``RSI2_1h < 10`` (Wilder RSI with n = 2);
- ``P2``: ``C_1h <= C_1d,t - 0.5 * ATR14_1d(t)`` (decision-day close and ATR);
- ``P3``: ``P1 or P2``.

The 24 hourly bars of the window are those opening at ``t+1d+0h .. t+1d+23h``.
If the condition is met at the close of window bar ``j`` the buy fills at the
open of bar ``j+1``; if it never is, the buy fills at market at the open of
bar 25 (``t+2d 00:00``), i.e. at the latest when the next daily rebalance
happens. Decreases of ``E`` are never deferred: they fill at ``open[t+1]``.

Evaluation (§2.8): incremental net return per unit of turnover versus T3. Both
paths buy the SAME units ``U = size / p_base`` (size = the increase of ``E_q``
or of the target weight), so the paths are identical after the overlay's fill
and the whole difference is ``U * (p_base - p_fill) * (1 + fee)`` (commission
is proportional to the notional). :func:`pullback_report` aggregates it.

Data: futures 1h exist from 2020, spot 1h only from 2022 (PLAN §5.2.6). A
window without 1h bars is reported as ``no_intraday`` and falls back to the
baseline fill (zero improvement); nothing is imputed.

The trigger functions (:func:`rsi`, :func:`trigger_series`) are the code the
live executor uses to watch a pending increase bar by bar.
"""
from __future__ import annotations

import math
from typing import Mapping, Optional

import numpy as np
import pandas as pd

from apps.research.features.volatility import ATR_N, atr, check_window, wilder_smooth
from apps.research.strategies._intraday import StrategyError

__all__ = [
    "PULLBACK_CONFIGS",
    "EVENT_COLUMNS",
    "rsi",
    "trigger_series",
    "increase_events",
    "pullback_schedule",
    "pullback_report",
    "Pullback",
    "make_pullback",
]

ONE_DAY = pd.Timedelta(days=1)
TF = pd.Timedelta(hours=1)

_BASE = {"rule": "P3", "rsi_n": 2, "rsi_max": 10.0, "atr_n": ATR_N, "atr_mult": 0.5, "max_wait": 24}

PULLBACK_CONFIGS: dict[str, dict] = {
    "P1": {**_BASE, "rule": "P1"},
    "P2": {**_BASE, "rule": "P2"},
    "P3": {**_BASE, "rule": "P3"},
}

EVENT_COLUMNS = ["symbol", "decision", "e_prev", "e_new", "size", "base_time", "base_price",
                 "trigger_time", "fill_time", "fill_price", "trigger", "wait_bars", "status"]


def rsi(close: pd.Series, n: int = 2) -> pd.Series:
    """
    Wilder RSI: ``100 - 100 / (1 + avg_gain / avg_loss)`` with Wilder averages of
    the gains and losses. 100 when there are no losses, 50 when nothing moved.
    """
    n = check_window(n)
    d = close.astype(float).diff()
    gain = wilder_smooth(d.clip(lower=0.0).where(d.notna()), n)
    loss = wilder_smooth((-d).clip(lower=0.0).where(d.notna()), n)
    out = 100.0 - 100.0 / (1.0 + gain / loss.where(loss > 0))
    out = out.mask((loss == 0) & (gain > 0), 100.0).mask((loss == 0) & (gain == 0), 50.0)
    return out.where(gain.notna() & loss.notna()).rename(f"rsi{n}")


def trigger_series(h1: pd.DataFrame, d_close: float, d_atr: float, params: Mapping,
                   rsi_values: Optional[pd.Series] = None) -> pd.Series:
    """
    Boolean pullback condition at the close of each 1h bar of ``h1`` for an
    increase decided on a day with close ``d_close`` and ``ATR14_1d = d_atr``.
    ``rsi_values`` (RSI of the full 1h history, aligned on ``h1``) avoids
    recomputing the RSI; by default it is computed on ``h1`` itself.
    """
    rule = params["rule"]
    if rule not in ("P1", "P2", "P3"):
        raise StrategyError(f"unknown pullback rule {rule!r}")
    r = rsi(h1["close"], params["rsi_n"]) if rsi_values is None else rsi_values.reindex(h1.index)
    p1 = (r < params["rsi_max"]).fillna(False)
    level = d_close - params["atr_mult"] * d_atr
    p2 = h1["close"] <= level if (pd.notna(d_close) and pd.notna(d_atr)) else pd.Series(False, index=h1.index)
    p2 = p2.fillna(False)
    if rule == "P1":
        out = p1
    elif rule == "P2":
        out = p2
    else:
        out = p1 | p2
    return out.astype(bool)


def increase_events(E_q: pd.DataFrame) -> pd.DataFrame:
    """
    Rows ``(symbol, decision, e_prev, e_new)`` where ``E_q`` rises at the close of
    ``decision`` (NaN is flat). Decreases are not events: they are never deferred.
    """
    rows = []
    for s in E_q.columns:
        e = E_q[s].astype(float).fillna(0.0)
        prev = e.shift(1).fillna(0.0)
        up = e > prev + 1e-12
        for t in e.index[up.to_numpy()]:
            rows.append((s, t, float(prev.loc[t]), float(e.loc[t])))
    return pd.DataFrame(rows, columns=["symbol", "decision", "e_prev", "e_new"])


def _first_open_at_or_after(h1: pd.DataFrame, when: pd.Timestamp, limit: pd.Timestamp):
    pos = int(h1.index.searchsorted(when, side="left"))
    opens = h1["open"].to_numpy(dtype=float)
    while pos < len(h1) and h1.index[pos] <= limit:
        if math.isfinite(opens[pos]):
            return h1.index[pos], float(opens[pos])
        pos += 1
    return None, math.nan


def pullback_schedule(E_q: pd.DataFrame, intraday: Mapping[str, pd.DataFrame],
                      daily: Mapping[str, pd.DataFrame], params: Mapping,
                      size: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Fill schedule of every increase of ``E_q`` (daily, rows = decision day ``t``).

    ``intraday``: 1h OHLCV per symbol; ``daily``: 1d OHLCV per symbol (decision
    close, ATR14 and the baseline price ``open[t+1]``). ``size``: optional
    frame with the weight increase per day (e.g. T3 target weights); by default
    the increase of ``E_q``. Returns one row per event (:data:`EVENT_COLUMNS`).
    ``status`` is ``triggered``, ``timeout`` or ``no_intraday``.
    """
    max_wait = int(params["max_wait"])
    if max_wait < 1:
        raise StrategyError("max_wait must be >= 1")
    ev = increase_events(E_q)
    out = []
    cache: dict[str, tuple] = {}
    for s, t, e_prev, e_new in ev.itertuples(index=False):
        if s not in daily:
            raise StrategyError(f"{s}: no daily bars")
        if s not in cache:
            d = daily[s]
            h1 = intraday.get(s)
            cache[s] = (d, atr(d, params["atr_n"]), h1,
                        None if h1 is None else rsi(h1["close"], params["rsi_n"]))
        d, d_atr, h1, r = cache[s]
        if size is not None:
            w = size[s].astype(float).fillna(0.0)
            amount = float(w.loc[t] - w.shift(1).fillna(0.0).loc[t]) if t in w.index else math.nan
        else:
            amount = e_new - e_prev
        base_time = t + ONE_DAY
        base_price = float(d["open"].loc[base_time]) if base_time in d.index else math.nan
        start, last = base_time, base_time + (max_wait - 1) * TF
        timeout_time = base_time + max_wait * TF
        window = h1.loc[start:last] if h1 is not None else None
        if window is None or len(window) == 0 or window["close"].notna().sum() == 0:
            out.append((s, t, e_prev, e_new, amount, base_time, base_price, pd.NaT, base_time,
                        base_price, "", 0, "no_intraday"))
            continue
        if not math.isfinite(base_price):
            _, base_price = _first_open_at_or_after(h1, base_time, base_time)
        cond = trigger_series(window, float(d["close"].loc[t]) if t in d.index else math.nan,
                              float(d_atr.loc[t]) if t in d_atr.index else math.nan, params,
                              rsi_values=r)
        hit = cond.to_numpy().nonzero()[0]
        if len(hit):
            trig_time = window.index[hit[0]]
            planned = trig_time + TF
            rule = params["rule"]
            if rule == "P3":
                rp1 = r.reindex([trig_time]).iloc[0] < params["rsi_max"]
                rule = "P1" if bool(rp1) else "P2"
            status = "triggered"
        else:
            trig_time, planned, rule, status = pd.NaT, timeout_time, "", "timeout"
        fill_time, fill_price = _first_open_at_or_after(h1, planned, timeout_time + ONE_DAY)
        if fill_time is None:
            raise StrategyError(f"{s}: no 1h open to fill the increase decided on {t} (no imputation)")
        wait = int(round((fill_time - base_time) / TF))
        out.append((s, t, e_prev, e_new, amount, base_time, base_price, trig_time, fill_time,
                    fill_price, rule, wait, status))
    return pd.DataFrame(out, columns=EVENT_COLUMNS)


def pullback_report(events: pd.DataFrame, fee: float = 0.0010) -> dict:
    """
    Summary of a schedule: number of events, share triggered / timed out /
    without 1h data, mean wait in hours and the incremental NET return per unit
    of turnover versus buying at ``open[t+1]``:
    ``sum(size * (1 - p_fill / p_base)) * (1 + fee) / sum(size)``.
    """
    n = len(events)
    if n == 0:
        return {"n_events": 0, "triggered": 0.0, "timeout": 0.0, "no_intraday": 0.0,
                "mean_wait_h": np.nan, "incremental_per_turnover": np.nan, "improvement_bps_mean": np.nan}
    ok = events[np.isfinite(events["base_price"].astype(float)) & np.isfinite(events["fill_price"].astype(float))
                & np.isfinite(events["size"].astype(float))]
    size = ok["size"].astype(float).abs()
    impr = 1.0 - ok["fill_price"].astype(float) / ok["base_price"].astype(float)
    turnover = float(size.sum())
    status = events["status"].value_counts(normalize=True)
    return {
        "n_events": int(n),
        "triggered": float(status.get("triggered", 0.0)),
        "timeout": float(status.get("timeout", 0.0)),
        "no_intraday": float(status.get("no_intraday", 0.0)),
        "mean_wait_h": float(events["wait_bars"].mean()),
        "incremental_per_turnover": float((size * impr).sum() * (1.0 + fee) / turnover) if turnover > 0 else np.nan,
        "improvement_bps_mean": float(impr.mean() * 1e4) if len(impr) else np.nan,
    }


class Pullback:
    """PULLBACK overlay (``P1``..``P3``); see the module docstring."""

    def __init__(self, config: str = "P3", **overrides):
        if config not in PULLBACK_CONFIGS:
            raise StrategyError(f"unknown PULLBACK config {config!r}; expected one of {list(PULLBACK_CONFIGS)}")
        unknown = set(overrides) - set(_BASE)
        if unknown:
            raise StrategyError(f"unknown PULLBACK parameters {sorted(unknown)}")
        self.params = {**PULLBACK_CONFIGS[config], **overrides, "config": config}
        self.name = f"PULLBACK-{config}"
        rule = self.params["rule"]
        # rsi_n + rsi_max (P1), atr_mult (P2), max_wait
        self.n_free_params = {"P1": 2, "P2": 1, "P3": 3}[rule] + 1

    def schedule(self, E_q: pd.DataFrame, intraday: Mapping[str, pd.DataFrame],
                 daily: Mapping[str, pd.DataFrame], size: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        return pullback_schedule(E_q, intraday, daily, self.params, size)

    def report(self, events: pd.DataFrame, fee: float = 0.0010) -> dict:
        return pullback_report(events, fee)


def make_pullback(config: str, **overrides) -> Pullback:
    """Factory used by the experiment runner (``P1``..``P3``)."""
    return Pullback(config, **overrides)
