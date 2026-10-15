"""Data provenance: upstream source commits and SHA-256 of the local CSVs.

Every research result stores the ``data_commit`` of the sources plus the hash
of each CSV it read (docs/research/PLAN.md §5.2.7), so a number can always be
traced back to the exact bytes that produced it.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

# Upstream repositories of the local data (harness data README).
SOURCES: dict[str, dict[str, str]] = {
    "futures": {
        "repo": "https://github.com/kbsingh1399/Backtesting_Data",
        "commit": "735eb87ffafb5c431162d7fec0d9bb3bf88d6d47",
    },
    "funding": {
        "repo": "https://github.com/kbsingh1399/Backtesting_Data",
        "commit": "735eb87ffafb5c431162d7fec0d9bb3bf88d6d47",
    },
    "spot": {
        "repo": "https://github.com/finom/static-klines",
        "commit": "4d33a56f2b3930376fc778522770c6e84855be7e",
    },
}

_HASH_CACHE: dict[tuple[str, int, int], str] = {}


def source_commit(market: str) -> str:
    """Upstream commit for ``market`` ("spot", "futures" or "funding")."""
    try:
        return SOURCES[market]["commit"]
    except KeyError as exc:
        raise KeyError(f"Unknown data market {market!r}") from exc


def data_commit() -> dict[str, str]:
    """Commits of every data source, as stored in each trial/result."""
    return {market: info["commit"] for market, info in SOURCES.items()}


def sha256_file(path: str | os.PathLike) -> str:
    """SHA-256 of a file, cached by (path, mtime, size)."""
    p = Path(path)
    st = p.stat()
    key = (str(p.resolve()), st.st_mtime_ns, st.st_size)
    cached = _HASH_CACHE.get(key)
    if cached is not None:
        return cached
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    digest = h.hexdigest()
    _HASH_CACHE[key] = digest
    return digest


def build_manifest(files: Iterable[str | os.PathLike], root: str | os.PathLike | None = None) -> dict:
    """Manifest of the given files: source commits, per-file SHA-256 and a combined digest.

    Paths are stored relative to ``root`` when possible so the manifest does not
    depend on where the data directory is mounted.
    """
    root_p = Path(root).resolve() if root is not None else None
    entries: dict[str, str] = {}
    for f in files:
        p = Path(f)
        name = str(p)
        if root_p is not None:
            try:
                name = str(p.resolve().relative_to(root_p))
            except ValueError:
                pass
        entries[name] = sha256_file(p)
    entries = dict(sorted(entries.items()))
    combined = hashlib.sha256(
        json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {"sources": data_commit(), "files": entries, "digest": combined}


def manifest_from_frames(frames: Iterable) -> dict:
    """Manifest built from the ``attrs`` that the loader attaches to each frame/series."""
    entries: dict[str, str] = {}
    for obj in frames:
        attrs = getattr(obj, "attrs", {}) or {}
        if "path" in attrs and "sha256" in attrs:
            entries[str(attrs.get("relpath", attrs["path"]))] = attrs["sha256"]
    entries = dict(sorted(entries.items()))
    combined = hashlib.sha256(
        json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {"sources": data_commit(), "files": entries, "digest": combined}
