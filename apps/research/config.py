"""Research harness configuration (config/research.yml).

The YAML file holds costs, splits, the trial budget, gate thresholds and data
paths. Everything is fixed a priori (docs/research/PLAN.md); this module only
loads and validates it. The historical data root can be overridden with the
``RESEARCH_DATA_ROOT`` environment variable.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "research.yml"
DATA_ROOT_ENV = "RESEARCH_DATA_ROOT"
DEFAULT_DATA_ROOT = Path("/home/user/harness/data")

# User risk decisions (not tunable): isolated margin, at most 3x, 20% total drawdown.
USER_MAX_LEVERAGE = 3.0
USER_MAX_DRAWDOWN = 0.20


class ConfigError(ValueError):
    """Raised when config/research.yml is missing or inconsistent."""


@dataclass(frozen=True)
class BudgetConfig:
    total: int
    quotas: Mapping[str, int]
    exploratory_family: str
    exploratory_tag: str


@dataclass(frozen=True)
class ResearchConfig:
    data_root: Path
    trials_log: Path
    holdout_lock: Path
    reports_dir: Path
    data_sources: Mapping[str, Mapping[str, str]]
    universe: Mapping[str, Any]
    costs: Mapping[str, Any]
    splits: Mapping[str, Any]
    budget: BudgetConfig
    sizing: Mapping[str, Any]
    leverage: Mapping[str, Any]
    gate: Mapping[str, Any]
    bootstrap: Mapping[str, Any]
    raw: Mapping[str, Any] = field(repr=False, default_factory=dict)

    def source_commit(self, market: str) -> str:
        """Commit of the upstream repository that produced ``market`` data."""
        try:
            return str(self.data_sources[market]["commit"])
        except KeyError as exc:
            raise ConfigError(f"No data source configured for market {market!r}") from exc

    @property
    def funding_excluded(self) -> tuple[str, ...]:
        return tuple(self.universe.get("funding_excluded", ()))


def _resolve(path: str | os.PathLike) -> Path:
    p = Path(path).expanduser()
    return p if p.is_absolute() else REPO_ROOT / p


def data_root(cfg_value: str | os.PathLike | None = None) -> Path:
    """Data root: ``RESEARCH_DATA_ROOT`` env > config value > default."""
    env = os.environ.get(DATA_ROOT_ENV)
    if env:
        return Path(env).expanduser()
    if cfg_value:
        return Path(cfg_value).expanduser()
    return DEFAULT_DATA_ROOT


def _validate(cfg: ResearchConfig) -> None:
    budget = cfg.budget
    if any(int(q) < 0 for q in budget.quotas.values()):
        raise ConfigError("Budget quotas must be non-negative")
    if sum(budget.quotas.values()) != budget.total:
        raise ConfigError(
            f"Family quotas sum to {sum(budget.quotas.values())}, expected total {budget.total}"
        )
    if budget.exploratory_family not in budget.quotas:
        raise ConfigError("The exploratory family must have a quota")

    lev = cfg.leverage
    if str(lev.get("margin_type", "")).upper() != "ISOLATED":
        raise ConfigError("Futures margin must be ISOLATED")
    for key in ("max_alt", "max_major", "user_hard_cap"):
        if float(lev[key]) > USER_MAX_LEVERAGE:
            raise ConfigError(f"leverage.{key}={lev[key]} exceeds the user cap of {USER_MAX_LEVERAGE}x")
    if float(lev["max_alt"]) > float(lev["max_major"]):
        raise ConfigError("Altcoin leverage cannot exceed BTC/ETH leverage")

    for key in ("max_dd_oos_spot", "max_dd_oos_futures"):
        if float(cfg.gate[key]) > USER_MAX_DRAWDOWN:
            raise ConfigError(f"gate.{key} exceeds the user drawdown tolerance of {USER_MAX_DRAWDOWN:.0%}")

    if float(cfg.sizing["gross_long_max"]) > 1.0:
        raise ConfigError("Gross long exposure must be <= 1x (PLAN §1.4)")


def load_config(path: str | os.PathLike | None = None) -> ResearchConfig:
    """Load and validate the research configuration."""
    cfg_path = Path(path) if path is not None else CONFIG_PATH
    if not cfg_path.is_file():
        raise ConfigError(f"Research config not found: {cfg_path}")
    with open(cfg_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    try:
        paths = raw["paths"]
        b = raw["budget"]
        budget = BudgetConfig(
            total=int(b["total"]),
            quotas={str(k): int(v) for k, v in b["quotas"].items()},
            exploratory_family=str(b["exploratory_family"]),
            exploratory_tag=str(b["exploratory_tag"]),
        )
        cfg = ResearchConfig(
            data_root=data_root(paths.get("data_root")),
            trials_log=_resolve(paths["trials_log"]),
            holdout_lock=_resolve(paths["holdout_lock"]),
            reports_dir=_resolve(paths["reports_dir"]),
            data_sources=raw["data_sources"],
            universe=raw["universe"],
            costs=raw["costs"],
            splits=raw["splits"],
            budget=budget,
            sizing=raw["sizing"],
            leverage=raw["leverage"],
            gate=raw["gate"],
            bootstrap=raw.get("bootstrap", {}),
            raw=raw,
        )
    except (KeyError, TypeError) as exc:
        raise ConfigError(f"Invalid research config {cfg_path}: missing {exc}") from exc

    _validate(cfg)
    return cfg


@lru_cache(maxsize=1)
def _default_config() -> ResearchConfig:
    return load_config()


def get_config() -> ResearchConfig:
    """Cached default configuration (the data root still honours the env var)."""
    cfg = _default_config()
    root = data_root(cfg.raw.get("paths", {}).get("data_root"))
    if root != cfg.data_root:
        cfg = replace(cfg, data_root=root)
    return cfg


def git_sha(repo: Path = REPO_ROOT) -> str:
    """Current commit of the trading-bot repository, or ``"unknown"``."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"
