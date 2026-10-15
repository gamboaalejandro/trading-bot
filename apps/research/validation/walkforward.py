"""
Anchored walk-forward with per-fold selection (PLAN.md §5.3, §4.2, task R14).

- Folds: quarterly test windows from 2022-01-01 to 2026-03-09 (17 folds; the
  last one is the short quarter 2026-01-01..2026-03-09). Training is ANCHORED:
  every fold trains from the same first date (the start of the data) up to the
  day before its test window. Test windows never overlap and never reach the
  holdout (2026-03-10 onwards).
- Selection: in each fold, ``select`` receives ONLY the training returns
  (T_train x configs, dates < test start) and returns the name of the chosen
  configuration; by default the best net Sharpe (:func:`select_best_sharpe`).
  The OOS result of the family is the concatenation of the test windows of
  the chosen configurations. Every configuration is also reported alone.

Candidates
    A candidate is any object with ``name`` and
    ``returns(panel, start, end)`` returning the daily NET returns over
    ``[start, end]`` (a ``pd.Series`` or a :class:`BTResult`). Candidates with
    fixed, preregistered rules (TREND, overlays, BRK4H...) are causal, so one
    continuous run from the first training date to the last test date is
    sliced into train / test windows (the position state carries over, as it
    would in live trading). A candidate that FITS something on the training
    window (e.g. SELECTOR M2) implements ``fold_returns(panel, fold)`` and gets
    ``(train_returns, test_returns)`` computed per fold.

    :class:`BacktestCandidate` wraps an engine call (``run(start, end, **kw)
    -> BTResult``) and keeps the full results for the reports and the stress
    runs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from apps.research.validation.stats import sharpe_ratio

__all__ = [
    "WalkForwardError",
    "Fold",
    "WFResult",
    "BacktestCandidate",
    "make_folds",
    "validate_folds",
    "select_best_sharpe",
    "walk_forward",
    "apply_selection",
    "oos_weights",
]

ONE_DAY = pd.Timedelta(days=1)
WF_START = "2022-01-01"
WF_END = "2026-03-09"
FOLD_MONTHS = 3
N_FOLDS = 17
#: Anchor of every training window: start of the debug split (PLAN §5.3). The spot
#: 2017-08..2020-08 frozen OOS must never feed a selection, so training starts after it.
TRAIN_ANCHOR = "2020-09-01"


class WalkForwardError(ValueError):
    """Invalid folds, candidates or selection."""


@dataclass(frozen=True)
class Fold:
    """One walk-forward fold (inclusive daily bounds, UTC)."""

    index: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp

    def as_tuple(self) -> tuple:
        return (self.train_start, self.train_end, self.test_start, self.test_end)


def _ts(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def make_folds(start: str = WF_START, end: str = WF_END, fold_months: int = FOLD_MONTHS,
               train_start: str = TRAIN_ANCHOR, n_folds: Optional[int] = N_FOLDS) -> list[Fold]:
    """
    Anchored folds with test windows of ``fold_months`` calendar months from
    ``start`` to ``end`` (the last window is truncated at ``end``).

    ``train_start`` is the anchor (default 2020-09-01, the start of the debug
    split and of the futures data; the frozen spot OOS 2017-08..2020-08 must
    never be used to select). Indicators may still warm up on earlier bars. With ``n_folds`` set the
    number of folds is checked (17 for the plan's split).
    """
    t0, t1, anchor = _ts(start), _ts(end), _ts(train_start)
    if not anchor < t0 <= t1:
        raise WalkForwardError("need train_start < start <= end")
    if fold_months < 1:
        raise WalkForwardError("fold_months must be >= 1")
    folds = []
    s = t0
    while s <= t1:
        e = min(s + pd.DateOffset(months=fold_months) - ONE_DAY, t1)
        folds.append(Fold(len(folds), anchor, s - ONE_DAY, s, e))
        s = e + ONE_DAY
    if n_folds is not None and len(folds) != n_folds:
        raise WalkForwardError(f"expected {n_folds} folds, built {len(folds)}")
    validate_folds(folds)
    return folds


def _as_fold(i: int, f) -> Fold:
    if isinstance(f, Fold):
        return f
    if len(f) != 4:
        raise WalkForwardError("a fold tuple is (train_start, train_end, test_start, test_end)")
    return Fold(i, *(_ts(x) for x in f))


def validate_folds(folds: Sequence) -> list[Fold]:
    """Check ordering, train < test, no overlap between test windows and anchored training."""
    out = [_as_fold(i, f) for i, f in enumerate(folds)]
    if not out:
        raise WalkForwardError("no folds")
    for f in out:
        if not (f.train_start <= f.train_end < f.test_start <= f.test_end):
            raise WalkForwardError(f"fold {f.index}: need train_start <= train_end < test_start <= test_end")
    for a, b in zip(out, out[1:]):
        if b.test_start <= a.test_end:
            raise WalkForwardError(f"folds {a.index} and {b.index} overlap")
        if b.train_start != a.train_start:
            raise WalkForwardError("training must be anchored (same train_start in every fold)")
    return out


def select_best_sharpe(train: pd.DataFrame) -> str:
    """Configuration with the best net Sharpe on the training returns (ties: first)."""
    best, best_sr = None, -math.inf
    for name in train.columns:
        sr = sharpe_ratio(train[name].dropna().to_numpy())
        if math.isfinite(sr) and sr > best_sr:
            best, best_sr = name, sr
    if best is None:
        return str(train.columns[0])
    return str(best)


@dataclass
class BacktestCandidate:
    """
    Candidate backed by an engine run: ``run(start, end, **overrides) -> BTResult``.

    ``overrides`` let the stress suite reuse the same configuration with
    stressed costs / delays / stop fills (robustness runs are not trials).
    Results are cached per ``(start, end, overrides)``.
    """

    name: str
    run: Callable[..., Any]
    params: dict = field(default_factory=dict)
    n_free_params: int = 0
    trial_id: Optional[str] = None
    results: dict = field(default_factory=dict, repr=False)

    def result(self, start, end, **overrides):
        key = (str(start), str(end), tuple(sorted((k, repr(v)) for k, v in overrides.items())))
        if key not in self.results:
            self.results[key] = self.run(start, end, **overrides)
        return self.results[key]

    def returns(self, panel, start, end, **overrides) -> pd.Series:
        return _returns_of(self.result(start, end, **overrides))


def _returns_of(obj) -> pd.Series:
    r = obj.returns if hasattr(obj, "returns") and not callable(obj.returns) else obj
    if not isinstance(r, pd.Series):
        raise WalkForwardError("a candidate must return a pd.Series or an object with .returns")
    if not isinstance(r.index, pd.DatetimeIndex):
        raise WalkForwardError("candidate returns need a DatetimeIndex")
    return r.astype(float)


def _slice(r: pd.Series, start, end) -> pd.Series:
    return r[(r.index >= start) & (r.index < end + ONE_DAY)]


@dataclass
class WFResult:
    """
    Walk-forward output.

    - ``oos_returns``: concatenated test returns of the configurations chosen
      in each fold (the family result).
    - ``config_oos``: T x configs test returns of every configuration alone
      (input of the PBO / CSCV of the family).
    - ``selections``: one row per fold with the bounds, the chosen
      configuration and the training Sharpe of every configuration.
    - ``train_seen``: last training date passed to ``select`` per fold (audit:
      it is always before the test start).
    """

    folds: list[Fold]
    oos_returns: pd.Series
    config_oos: pd.DataFrame
    selections: pd.DataFrame
    train_seen: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def selected(self) -> list[str]:
        return list(self.selections["selected"])

    @property
    def final_selection(self) -> str:
        """Configuration chosen in the last fold (the one that would go live)."""
        return str(self.selections["selected"].iloc[-1])


def walk_forward(family_configs: list, panel, folds: list[tuple], select: Callable = select_best_sharpe) -> WFResult:
    """
    Run the anchored walk-forward of ``family_configs`` (see the module docstring).

    ``select(train_returns: pd.DataFrame) -> str`` only ever sees training rows
    (dates <= ``train_end``, strictly before the fold's test window).
    """
    if not family_configs:
        raise WalkForwardError("no configurations")
    names = [str(getattr(c, "name", "")) for c in family_configs]
    if any(not n for n in names) or len(set(names)) != len(names):
        raise WalkForwardError(f"configurations need unique non-empty names, got {names}")
    fs = validate_folds(folds)
    first, last = fs[0].train_start, fs[-1].test_end

    full: dict[str, pd.Series] = {}
    for c, n in zip(family_configs, names):
        if not hasattr(c, "fold_returns"):
            r = _returns_of(c.returns(panel, first, last))
            if r.index.max() > last + ONE_DAY:
                raise WalkForwardError(f"{n}: returns beyond the last test date {last.date()}")
            full[n] = r

    rows, oos_parts, cfg_parts, seen = [], [], {n: [] for n in names}, {}
    for f in fs:
        train_cols, test_cols = {}, {}
        for c, n in zip(family_configs, names):
            if n in full:
                tr, te = _slice(full[n], f.train_start, f.train_end), _slice(full[n], f.test_start, f.test_end)
            else:
                tr, te = c.fold_returns(panel, f)
                tr, te = _slice(_returns_of(tr), f.train_start, f.train_end), \
                    _slice(_returns_of(te), f.test_start, f.test_end)
            train_cols[n], test_cols[n] = tr, te
        train = pd.DataFrame(train_cols)
        if len(train) and train.index.max() >= f.test_start:
            raise WalkForwardError("training data overlaps the test window")  # pragma: no cover
        seen[f.index] = train.index.max() if len(train) else None
        choice = str(select(train.copy()))
        if choice not in names:
            raise WalkForwardError(f"select returned unknown configuration {choice!r}")
        test = pd.DataFrame(test_cols)
        oos_parts.append(test[choice] if choice in test else pd.Series(dtype=float))
        for n in names:
            cfg_parts[n].append(test[n])
        row = {"fold": f.index, "train_start": f.train_start, "train_end": f.train_end,
               "test_start": f.test_start, "test_end": f.test_end, "selected": choice,
               "test_days": int(test[choice].notna().sum()) if choice in test else 0}
        for n in names:
            row[f"train_sr[{n}]"] = sharpe_ratio(train[n].dropna().to_numpy(), 365) if n in train else np.nan
        rows.append(row)

    oos = pd.concat(oos_parts).sort_index() if oos_parts else pd.Series(dtype=float)
    config_oos = pd.DataFrame({n: pd.concat(cfg_parts[n]) for n in names}).sort_index()
    return WFResult(fs, oos.rename("oos_returns"), config_oos, pd.DataFrame(rows), seen,
                    raw={"full": full})


def apply_selection(selections: pd.DataFrame, returns_by_config: Mapping[str, pd.Series]) -> pd.Series:
    """
    Re-apply the per-fold choices of a walk-forward to other return series of
    the same configurations (stress runs: costs x2, +1 bar delay...). The
    selection is NOT redone on stressed data.
    """
    parts = []
    for row in selections.itertuples(index=False):
        r = returns_by_config.get(row.selected)
        if r is None:
            raise WalkForwardError(f"no returns for the selected configuration {row.selected!r}")
        parts.append(_slice(_returns_of(r), _ts(row.test_start), _ts(row.test_end)))
    return pd.concat(parts).sort_index().rename("oos_returns") if parts else pd.Series(dtype=float)


def oos_weights(selections: pd.DataFrame, weights_by_config: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """Concatenated weights of the chosen configurations over the test windows."""
    parts = []
    for row in selections.itertuples(index=False):
        w = weights_by_config[row.selected]
        parts.append(w[(w.index >= _ts(row.test_start)) & (w.index < _ts(row.test_end) + ONE_DAY)])
    return pd.concat(parts).sort_index() if parts else pd.DataFrame()

