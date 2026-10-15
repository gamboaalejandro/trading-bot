"""
Holdout lock (PLAN.md §5.3, §4.2, task R14).

The sanity holdout (futures 2026-03-10..2026-09-10, spot 2026-03-10..2026-10-15)
may be opened ONCE, at the end of the project and only for the finalists. The
opening is recorded in ``<trials_dir>/holdout.lock`` (default
``${REPO}/data/trials/holdout.lock``): who, when, for which finalists, the git
sha and the data commits, sealed with a SHA-256 of its content.

- :meth:`HoldoutLock.open` creates the lock file atomically (``O_EXCL``). A
  second call, from this or any other process, raises
  :class:`HoldoutAlreadyOpened` with the details of the first opening.
- A lock file that cannot be parsed or whose seal does not match counts as
  OPENED (fail closed) and raises :class:`HoldoutLockCorrupted`.
- :func:`check_outside_holdout` is the guard every walk-forward / debug run
  calls before loading data: a range that reaches the holdout raises
  :class:`HoldoutViolation`.

The trials directory is configurable (``trials_dir=`` or the
``RESEARCH_TRIALS_DIR`` environment variable); the default comes from
``config/research.yml`` (``paths.holdout_lock``).
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

import pandas as pd

from apps.research.config import get_config, git_sha
from apps.research.data.manifest import data_commit

__all__ = [
    "TRIALS_DIR_ENV",
    "LOCK_NAME",
    "HoldoutError",
    "HoldoutAlreadyOpened",
    "HoldoutLockCorrupted",
    "HoldoutViolation",
    "HoldoutGrant",
    "HoldoutLock",
    "holdout_window",
    "check_outside_holdout",
    "default_trials_dir",
]

TRIALS_DIR_ENV = "RESEARCH_TRIALS_DIR"
LOCK_NAME = "holdout.lock"


class HoldoutError(RuntimeError):
    """Base error of the holdout lock."""


class HoldoutAlreadyOpened(HoldoutError):
    """The holdout was already opened once; it cannot be opened again."""


class HoldoutLockCorrupted(HoldoutAlreadyOpened):
    """The lock file exists but is unreadable or was edited (treated as opened)."""


class HoldoutViolation(HoldoutError):
    """A run tried to use holdout dates without the lock."""


def default_trials_dir() -> Path:
    """``RESEARCH_TRIALS_DIR`` if set, else the directory of ``paths.holdout_lock``."""
    env = os.environ.get(TRIALS_DIR_ENV)
    if env:
        return Path(env).expanduser()
    return get_config().holdout_lock.parent


def _seal(body: dict) -> str:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def holdout_window(market: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Inclusive UTC bounds of the holdout of ``market`` (from config/research.yml)."""
    hold = get_config().splits["holdout"]
    if market not in hold:
        raise HoldoutError(f"no holdout configured for market {market!r}")
    w = hold[market]
    return pd.Timestamp(w["start"], tz="UTC"), pd.Timestamp(w["end"], tz="UTC")


def check_outside_holdout(end, market: str) -> None:
    """Raise :class:`HoldoutViolation` if a run ending at ``end`` reaches the holdout."""
    start_h, _ = holdout_window(market)
    t = pd.Timestamp(end)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    if t >= start_h:
        raise HoldoutViolation(
            f"{market}: the range ends at {t.date()} but the holdout starts at {start_h.date()}; "
            "only HoldoutLock.open() (experiment E9) may use it")


@dataclass(frozen=True)
class HoldoutGrant:
    """Proof that this process opened the holdout (returned once by :meth:`HoldoutLock.open`)."""

    path: Path
    record: dict

    def window(self, market: str) -> tuple[pd.Timestamp, pd.Timestamp]:
        return holdout_window(market)


class HoldoutLock:
    """One-shot lock of the holdout (see the module docstring)."""

    def __init__(self, trials_dir: str | os.PathLike | None = None, path: str | os.PathLike | None = None):
        if path is not None:
            self.path = Path(path)
        else:
            self.path = Path(trials_dir) / LOCK_NAME if trials_dir is not None else default_trials_dir() / LOCK_NAME

    # ---------------------------------------------------------------- state
    def is_open(self) -> bool:
        """True once the holdout has been opened (or the lock file exists at all)."""
        return self.path.exists()

    def info(self) -> Optional[dict]:
        """The recorded opening, or None if never opened. Raises if the file was tampered with."""
        if not self.path.exists():
            return None
        try:
            rec = json.loads(self.path.read_text(encoding="utf-8"))
            body = {k: v for k, v in rec.items() if k != "seal"}
            ok = rec.get("seal") == _seal(body)
        except (OSError, ValueError, AttributeError) as exc:
            raise HoldoutLockCorrupted(f"{self.path}: unreadable holdout lock ({exc}); treated as opened") from exc
        if not ok:
            raise HoldoutLockCorrupted(f"{self.path}: holdout lock seal mismatch (edited); treated as opened")
        return rec

    # ---------------------------------------------------------------- open
    def open(self, agent: str, finalists: Sequence[str], reason: str = "") -> HoldoutGrant:
        """
        Open the holdout ONCE. Records who, when, the finalists, git sha and
        data commits. Raises :class:`HoldoutAlreadyOpened` on any later call.
        """
        if not agent:
            raise ValueError("agent is required")
        finalists = [str(f) for f in finalists]
        if not finalists:
            raise ValueError("the holdout is opened only for named finalists")
        if self.path.exists():
            prev = self.info()
            raise HoldoutAlreadyOpened(
                f"holdout already opened at {prev.get('opened_at')} by {prev.get('agent')} "
                f"for {prev.get('finalists')}")
        body = {
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "finalists": finalists,
            "reason": reason,
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "git_sha": git_sha(),
            "data_commit": data_commit(),
            "windows": {m: [str(a.date()), str(b.date())] for m in ("futures", "spot")
                        for a, b in [holdout_window(m)]},
        }
        rec = {**body, "seal": _seal(body)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
        except FileExistsError as exc:
            prev = self.info() or {}
            raise HoldoutAlreadyOpened(
                f"holdout already opened at {prev.get('opened_at')} by {prev.get('agent')}") from exc
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True, indent=2) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return HoldoutGrant(self.path, rec)
