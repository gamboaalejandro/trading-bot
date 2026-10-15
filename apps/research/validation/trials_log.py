"""Append-only log of every configuration tested (docs/research/PLAN.md §2.1, §4.2).

Each line of ``data/trials/trials.jsonl`` is a JSON record chained to the
previous one by SHA-256 (``prev_hash`` -> ``hash``), so any edit, deletion or
reordering of past lines is detected by :meth:`TrialsLog.verify`.

Record kinds:

- ``trial``: one tested configuration (counts towards N and the family quota).
- ``metrics``: metrics computed for an existing trial. Metrics are appended as
  a separate record instead of rewriting the trial line.

The project budget is N <= 40 trials split in family quotas; the 8 exploratory
trials of the debate are preloaded under the ``DEBATE`` family with the tag
``debate-exploratorio``. Registering beyond a quota raises
:class:`BudgetExceeded`. A trial must be registered BEFORE computing anything
on 2022+ data.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

from apps.research.config import get_config, git_sha
from apps.research.data.manifest import data_commit

try:  # POSIX advisory lock so concurrent agents cannot interleave appends
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX platforms
    fcntl = None

GENESIS_HASH = "0" * 64
TRIAL = "trial"
METRICS = "metrics"

# The 8 trials already consumed during the debate (PLAN §2.1). They count
# towards N (DSR) even though their exact numbers live in the debate notes.
DEBATE_TRIALS: tuple[dict[str, Any], ...] = (
    {"round": 1, "author": "optimist", "family": "TREND",
     "description": "Donchian ensemble, vol target, Lmax=1"},
    {"round": 1, "author": "optimist", "family": "TREND",
     "description": "Donchian ensemble, vol target, Lmax=2"},
    {"round": 2, "author": "debate", "family": "TREND",
     "description": "Trend variant 1 (round 2)"},
    {"round": 2, "author": "debate", "family": "TREND",
     "description": "Trend variant 2 (round 2)"},
    {"round": 2, "author": "debate", "family": "TREND",
     "description": "Trend variant 3 (round 2, alternative exit rule)"},
    {"round": 2, "author": "debate", "family": "TREND",
     "description": "Trend variant 4 (round 2)"},
    {"round": 2, "author": "debate", "family": "SHORT",
     "description": "Short leg with portfolio vol target"},
    {"round": 2, "author": "debate", "family": "CARRY",
     "description": "Funding carry, delta-neutral"},
)


class TrialsLogError(Exception):
    """Base error of the trials log."""


class TrialsLogCorrupted(TrialsLogError):
    """The hash chain is broken: a past line was edited, removed or reordered."""


class BudgetExceeded(TrialsLogError):
    """Registering the trial would exceed a family quota or the total budget."""


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _record_hash(record: Mapping[str, Any]) -> str:
    body = {k: v for k, v in record.items() if k != "hash"}
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def _jsonable(params: Mapping[str, Any]) -> dict:
    """Round-trip through canonical JSON: rejects NaN/inf and non-serialisable values."""
    try:
        return json.loads(_canonical(dict(params)))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"params must be JSON-serialisable and finite: {exc}") from exc


class TrialsLog:
    """Append-only, hash-chained JSONL log with per-family quotas."""

    def __init__(
        self,
        path: str | os.PathLike | None = None,
        quotas: Mapping[str, int] | None = None,
        total: int | None = None,
        seed_debate: bool = True,
    ) -> None:
        cfg = get_config()
        self.path = Path(path) if path is not None else cfg.trials_log
        self.quotas: dict[str, int] = dict(quotas if quotas is not None else cfg.budget.quotas)
        self.total_budget = int(total if total is not None else cfg.budget.total)
        self.exploratory_family = cfg.budget.exploratory_family
        self.exploratory_tag = cfg.budget.exploratory_tag
        if any(q < 0 for q in self.quotas.values()) or self.total_budget < 0:
            raise ValueError("Quotas and total budget must be non-negative")
        if seed_debate:
            self._seed_debate()

    # ------------------------------------------------------------------ io
    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name("." + self.path.name + ".flock")
        with open(lock_path, "a+") as lock:
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def records(self) -> list[dict]:
        """All records, after verifying the whole hash chain."""
        if not self.path.exists():
            return []
        out: list[dict] = []
        prev = GENESIS_HASH
        with open(self.path, "r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                if not line.strip():
                    raise TrialsLogCorrupted(f"{self.path}:{lineno}: blank line")
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise TrialsLogCorrupted(f"{self.path}:{lineno}: invalid JSON") from exc
                if rec.get("prev_hash") != prev:
                    raise TrialsLogCorrupted(f"{self.path}:{lineno}: prev_hash does not match previous line")
                if rec.get("hash") != _record_hash(rec):
                    raise TrialsLogCorrupted(f"{self.path}:{lineno}: content hash mismatch (edited line)")
                prev = rec["hash"]
                out.append(rec)
        return out

    def verify(self) -> bool:
        """Raise :class:`TrialsLogCorrupted` if the chain is broken; return True otherwise."""
        self.records()
        return True

    def _append(self, records: list[dict], body: dict) -> dict:
        prev = records[-1]["hash"] if records else GENESIS_HASH
        rec = {**body, "prev_hash": prev}
        rec["hash"] = _record_hash(rec)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(_canonical(rec) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        records.append(rec)
        return rec

    # -------------------------------------------------------------- queries
    def trials(self, family: str | None = None) -> list[dict]:
        """Trial records (optionally of one family), with their latest metrics merged in."""
        records = self.records()
        latest: dict[str, Any] = {}
        for rec in records:
            if rec["kind"] == METRICS:
                latest[rec["trial_id"]] = rec["metrics"]
        out = []
        for rec in records:
            if rec["kind"] == TRIAL and (family is None or rec["family"] == family):
                out.append({**rec, "metrics": latest.get(rec["id"], rec.get("metrics"))})
        return out

    def n_total(self) -> int:
        """Number of trials registered in the whole project (N for the DSR)."""
        return sum(1 for r in self.records() if r["kind"] == TRIAL)

    def n_family(self, family: str) -> int:
        return sum(1 for r in self.records() if r["kind"] == TRIAL and r["family"] == family)

    def remaining(self, family: str) -> int:
        """Trials left in ``family``'s quota. Raises :class:`BudgetExceeded` if overspent."""
        if family not in self.quotas:
            raise KeyError(f"Unknown trial family {family!r}; known: {sorted(self.quotas)}")
        used = self.n_family(family)
        left = self.quotas[family] - used
        if left < 0:
            raise BudgetExceeded(f"Family {family} used {used} trials, quota is {self.quotas[family]}")
        return left

    def get(self, trial_id: str) -> dict:
        for rec in self.trials():
            if rec["id"] == trial_id:
                return rec
        raise KeyError(f"Unknown trial id {trial_id!r}")

    # -------------------------------------------------------------- writes
    def register(self, family: str, params: dict, agent: str, tag: str = "") -> str:
        """Register a configuration BEFORE computing its metrics; return its id.

        Re-registering an identical ``(family, params)`` returns the existing id
        without consuming budget (robustness runs of the same configuration are
        not new trials). Raises :class:`BudgetExceeded` when the family quota or
        the total budget is exhausted.
        """
        if family not in self.quotas:
            raise KeyError(f"Unknown trial family {family!r}; known: {sorted(self.quotas)}")
        if not agent:
            raise ValueError("agent is required")
        clean = _jsonable(params)
        with self._locked():
            records = self.records()
            key = _canonical(clean)
            for rec in records:
                if rec["kind"] == TRIAL and rec["family"] == family and _canonical(rec["params"]) == key:
                    return rec["id"]
            trials = [r for r in records if r["kind"] == TRIAL]
            used = sum(1 for r in trials if r["family"] == family)
            if used >= self.quotas[family]:
                raise BudgetExceeded(
                    f"Family {family} exhausted its quota of {self.quotas[family]} trials"
                )
            if len(trials) >= self.total_budget:
                raise BudgetExceeded(f"Total trial budget of {self.total_budget} exhausted")
            trial_id = f"{family}-{used + 1:02d}"
            self._append(records, self._trial_body(trial_id, family, clean, agent, tag))
        return trial_id

    def record_metrics(self, trial_id: str, metrics: Mapping[str, Any]) -> None:
        """Append metrics for an already registered trial."""
        clean = _jsonable(metrics)
        with self._locked():
            records = self.records()
            if not any(r["kind"] == TRIAL and r["id"] == trial_id for r in records):
                raise KeyError(f"Unknown trial id {trial_id!r}; register it first")
            body = {
                "kind": METRICS,
                "trial_id": trial_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "metrics": clean,
            }
            self._append(records, body)

    def sharpe_values(self) -> list[float]:
        """Latest ``sharpe`` metric of every trial that has one (for the DSR variance)."""
        out = []
        for rec in self.trials():
            m = rec.get("metrics") or {}
            sr = m.get("sharpe")
            if isinstance(sr, (int, float)) and math.isfinite(sr):
                out.append(float(sr))
        return out

    # ------------------------------------------------------------ internals
    @staticmethod
    def _trial_body(trial_id: str, family: str, params: dict, agent: str, tag: str) -> dict:
        return {
            "kind": TRIAL,
            "id": trial_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "family": family,
            "params": params,
            "tag": tag,
            "data_commit": data_commit(),
            "git_sha": git_sha(),
            "metrics": None,
        }

    def _seed_debate(self) -> None:
        """Preload the 8 exploratory debate trials once (no-op if already present)."""
        family = self.exploratory_family
        if family not in self.quotas:
            return
        with self._locked():
            records = self.records()
            if any(r["kind"] == TRIAL and r["family"] == family for r in records):
                return
            n = min(len(DEBATE_TRIALS), self.quotas[family])
            for i, params in enumerate(DEBATE_TRIALS[:n], start=1):
                body = self._trial_body(
                    f"{family}-{i:02d}", family, _jsonable(params), "debate", self.exploratory_tag
                )
                self._append(records, body)
