"""Tests for apps/live/kill_switch.py (PLAN.md §6.2 L03, §7.6)."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from apps.live.kill_switch import (
    DEFAULT_RISK_LIMITS_PATH,
    KillSwitch,
    KillSwitchLevel,
    PositionView,
    RiskLimitsError,
    assert_can_start,
    check_leverage,
    check_target_weights,
    load_risk_limits,
    resolve_trading_mode,
)

T0 = datetime(2026, 10, 15, 0, 5, tzinfo=timezone.utc)


@pytest.fixture
def limits():
    return load_risk_limits(DEFAULT_RISK_LIMITS_PATH)


@pytest.fixture
def raw_cfg():
    return yaml.safe_load(DEFAULT_RISK_LIMITS_PATH.read_text(encoding="utf-8"))


def write_cfg(tmp_path: Path, raw) -> Path:
    p = tmp_path / "risk_limits.yml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return p


@dataclass
class Intent:
    symbol: str
    reduce_only: bool


# --- config ------------------------------------------------------------------

def test_repo_config_has_user_thresholds(limits):
    ks = limits.kill_switch
    assert ks.daily_loss_block_entries == pytest.approx(-0.02)
    assert ks.daily_loss_flatten == pytest.approx(-0.05)
    assert ks.drawdown_half_risk == pytest.approx(0.10)
    assert ks.drawdown_halt == pytest.approx(0.20)
    assert ks.reduced_risk_multiplier == pytest.approx(0.5)
    assert limits.user_confirmed is True
    assert limits.exposure.max_gross_long <= 1.0
    assert limits.exposure.max_gross_short <= 0.5
    assert limits.leverage.margin_type == "ISOLATED"
    assert limits.max_leverage("BTC/USDT") == pytest.approx(1.5)
    assert limits.max_leverage("SOLUSDT") == pytest.approx(1.0)
    assert limits.leverage.account_max_leverage <= 3.0


@pytest.mark.parametrize("section,key", [
    ("kill_switch", "daily_loss_flatten"),
    ("kill_switch", "drawdown_halt"),
    ("exposure", "max_gross_long"),
    ("leverage", "max_leverage_alt"),
    ("capital", "max_capital_usdt"),
])
def test_missing_key_has_no_default(tmp_path, raw_cfg, section, key):
    del raw_cfg[section][key]
    with pytest.raises(RiskLimitsError, match=key):
        load_risk_limits(write_cfg(tmp_path, raw_cfg))


@pytest.mark.parametrize("section,key,value", [
    ("kill_switch", "daily_loss_flatten", -0.01),      # milder than block-entries
    ("kill_switch", "daily_loss_block_entries", 0.02),  # positive
    ("kill_switch", "drawdown_half_risk", 0.30),        # above halt
    ("exposure", "max_gross_long", 1.5),                # above PLAN ceiling
    ("exposure", "max_weight_alt", 0.5),
    ("leverage", "max_leverage_alt", 2.0),
    ("leverage", "max_leverage_major", 3.0),
    ("leverage", "account_max_leverage", 5.0),          # above user's 3x
    ("leverage", "margin_type", "CROSSED"),
    ("kill_switch", "drawdown_halt", "20%"),
])
def test_invalid_values_rejected(tmp_path, raw_cfg, section, key, value):
    raw_cfg[section][key] = value
    with pytest.raises(RiskLimitsError):
        load_risk_limits(write_cfg(tmp_path, raw_cfg))


# --- startup guard -----------------------------------------------------------

def test_live_without_config_does_not_start(tmp_path):
    with pytest.raises(RiskLimitsError, match="not found"):
        assert_can_start("live", tmp_path / "missing.yml")


def test_live_with_invalid_config_does_not_start(tmp_path):
    p = tmp_path / "risk_limits.yml"
    p.write_text("kill_switch: [not, a, mapping\n", encoding="utf-8")
    with pytest.raises(RiskLimitsError):
        assert_can_start("live", p)


def test_live_requires_user_confirmation(tmp_path, raw_cfg):
    raw_cfg["user_confirmed"] = False
    p = write_cfg(tmp_path, raw_cfg)
    with pytest.raises(RiskLimitsError, match="user_confirmed"):
        assert_can_start("live", p)
    # non-live modes still load it
    assert assert_can_start("dry_run", p) is not None


def test_live_with_valid_config_starts(limits):
    assert assert_can_start("live", DEFAULT_RISK_LIMITS_PATH) == limits


def test_dry_run_without_config_starts(tmp_path):
    assert assert_can_start("dry_run", tmp_path / "missing.yml") is None


def test_trading_mode_from_env(monkeypatch, tmp_path):
    monkeypatch.delenv("TRADING_MODE", raising=False)
    assert resolve_trading_mode() == "dry_run"
    monkeypatch.setenv("TRADING_MODE", "live")
    with pytest.raises(RiskLimitsError):
        assert_can_start(path=tmp_path / "missing.yml")
    monkeypatch.setenv("TRADING_MODE", "yolo")
    with pytest.raises(RiskLimitsError, match="unknown"):
        resolve_trading_mode()


# --- daily loss ----------------------------------------------------------------

def test_normal_allows_everything(limits):
    ks = KillSwitch(limits)
    d = ks.update(10_000, T0)
    assert d.level == KillSwitchLevel.NORMAL
    assert d.allow_entries and d.allow_any_new_orders
    assert d.risk_multiplier == 1.0
    assert ks.allows_order(reduce_only=False)


def test_daily_minus_2pct_blocks_entries(limits):
    ks = KillSwitch(limits)
    ks.update(10_000, T0)
    d = ks.update(9_850, T0 + timedelta(hours=1))   # -1.5 %
    assert d.level == KillSwitchLevel.NORMAL
    d = ks.update(9_800, T0 + timedelta(hours=2))   # -2 % exactly
    assert d.level == KillSwitchLevel.BLOCK_ENTRIES
    assert not d.allow_entries
    assert d.allow_any_new_orders
    assert not d.close_leveraged_and_shorts
    assert not ks.allows_order(reduce_only=False)
    assert ks.allows_order(reduce_only=True)
    allowed, blocked = ks.filter_orders([Intent("BTCUSDT", False), Intent("ETHUSDT", True)])
    assert [i.symbol for i in allowed] == ["ETHUSDT"]
    assert [i.symbol for i in blocked] == ["BTCUSDT"]
    positions = [PositionView("BTCUSDT", 1.0, leverage=1.5, market="futures")]
    assert ks.positions_to_close(positions) == []


def test_daily_lock_is_sticky_until_next_utc_day(limits):
    ks = KillSwitch(limits)
    ks.update(10_000, T0)
    ks.update(9_790, T0 + timedelta(hours=2))
    d = ks.update(10_050, T0 + timedelta(hours=5))    # intraday recovery
    assert d.level == KillSwitchLevel.BLOCK_ENTRIES
    d = ks.update(10_050, datetime(2026, 10, 16, 0, 5, tzinfo=timezone.utc))
    assert d.level == KillSwitchLevel.NORMAL
    assert d.daily_return == 0.0


def test_daily_minus_5pct_closes_leveraged_and_shorts_and_blocks_all(limits):
    alerts = []
    ks = KillSwitch(limits, alert=alerts.append)
    ks.update(10_000, T0)
    d = ks.update(9_500, T0 + timedelta(hours=3))    # -5 %
    assert d.level == KillSwitchLevel.FLATTEN
    assert d.close_leveraged_and_shorts
    assert not d.allow_entries and not d.allow_any_new_orders
    assert d.risk_multiplier == 0.0
    assert not ks.allows_order(reduce_only=False)
    assert ks.allows_order(reduce_only=True)          # closing orders still go through
    positions = [
        PositionView("BTCUSDT", 0.1, leverage=1.5, market="futures"),   # L > 1 -> close
        PositionView("ETHUSDT", -2.0, leverage=1.0, market="futures"),  # short -> close
        PositionView("SOLUSDT", 10.0, leverage=1.0, market="spot"),     # spot 1x -> keep
        PositionView("ADAUSDT", 0.0, leverage=2.0, market="futures"),   # flat -> ignore
    ]
    to_close = {p.symbol for p in ks.positions_to_close(positions)}
    assert to_close == {"BTCUSDT", "ETHUSDT"}
    assert alerts and "FLATTEN" in alerts[-1]


def test_gap_straight_to_flatten(limits):
    ks = KillSwitch(limits)
    ks.update(10_000, T0)
    assert ks.update(9_300, T0 + timedelta(minutes=5)).level == KillSwitchLevel.FLATTEN


# --- drawdown -------------------------------------------------------------------

def test_drawdown_10pct_halves_risk(limits):
    ks = KillSwitch(limits)
    day = T0
    equity = 10_000.0
    ks.update(equity, day)
    # lose 1.5 % per day: never trips the daily lock, accumulates drawdown
    for _ in range(6):
        day += timedelta(days=1)
        equity *= 0.985
        d = ks.update(equity, day)
        assert d.level == KillSwitchLevel.NORMAL
    day += timedelta(days=1)
    equity = 8_990.0                         # DD 10.1 %, daily -1.x %
    d = ks.update(equity, day)
    assert d.drawdown == pytest.approx(0.101)
    assert d.level == KillSwitchLevel.NORMAL
    assert d.allow_entries
    assert d.risk_multiplier == pytest.approx(0.5)
    assert ks.scale_weights({"BTCUSDT": 0.30, "SOLUSDT": -0.1}) == pytest.approx(
        {"BTCUSDT": 0.15, "SOLUSDT": -0.05})
    # recovery below the threshold restores full risk
    d = ks.update(9_200, day + timedelta(days=1))
    assert d.risk_multiplier == 1.0


def test_drawdown_20pct_halts_until_manual_reset(limits):
    alerts = []
    ks = KillSwitch(limits, alert=alerts.append)
    day = T0
    equity = 10_000.0
    ks.update(equity, day)
    while equity * 0.985 > 8_050:
        day += timedelta(days=1)
        equity *= 0.985
        ks.update(equity, day)
    day += timedelta(days=1)
    d = ks.update(8_000, day)                # DD 20 %
    assert d.level == KillSwitchLevel.HALT
    assert not d.allow_any_new_orders and d.close_leveraged_and_shorts
    assert d.risk_multiplier == 0.0
    assert any("HALT" in r for r in d.reasons)
    assert any("HALT" in a for a in alerts)
    # new day and recovery do not clear it
    d = ks.update(8_500, day + timedelta(days=1))
    assert d.level == KillSwitchLevel.HALT
    with pytest.raises(ValueError):
        ks.reset_halt("", "")
    ks.reset_halt("operator", "reviewed after drawdown")
    d = ks.update(8_500, day + timedelta(days=1, hours=1))
    assert d.level == KillSwitchLevel.NORMAL
    assert d.drawdown == 0.0


def test_state_survives_restart(tmp_path, limits):
    state = tmp_path / "ks_state.json"
    ks = KillSwitch(limits, state_path=state)
    ks.update(10_000, T0)
    ks.update(9_400, T0 + timedelta(hours=1))
    assert ks.level == KillSwitchLevel.FLATTEN
    restarted = KillSwitch(limits, state_path=state)
    assert restarted.level == KillSwitchLevel.FLATTEN
    # same UTC day: reference equity is still the morning one
    d = restarted.update(9_600, T0 + timedelta(hours=2))
    assert d.level == KillSwitchLevel.FLATTEN
    assert d.daily_return == pytest.approx(-0.04)


def test_corrupt_state_refuses(tmp_path, limits):
    state = tmp_path / "ks_state.json"
    state.write_text("{not json", encoding="utf-8")
    with pytest.raises(RiskLimitsError):
        KillSwitch(limits, state_path=state)


def test_rejects_naive_timestamp_and_bad_equity(limits):
    ks = KillSwitch(limits)
    with pytest.raises(ValueError):
        ks.update(10_000, datetime(2026, 10, 15))
    with pytest.raises(ValueError):
        ks.update(float("nan"), T0)


# --- exposure / leverage ----------------------------------------------------------

def test_leverage_caps(limits):
    check_leverage(limits, "BTCUSDT", 1.5)
    check_leverage(limits, "ETH/USDT", 1.0)
    check_leverage(limits, "SOLUSDT", 1.0)
    with pytest.raises(RiskLimitsError):
        check_leverage(limits, "BTCUSDT", 2.0)
    with pytest.raises(RiskLimitsError):
        check_leverage(limits, "SOLUSDT", 1.5)
    with pytest.raises(RiskLimitsError):
        check_leverage(limits, "DOGEUSDT", 3.0)


def test_exposure_checks(limits):
    ok = {"BTCUSDT": 0.35, "ETHUSDT": 0.30, "SOLUSDT": 0.20, "XRPUSDT": 0.15}
    assert check_target_weights(limits, ok) == []
    bad = {"BTCUSDT": 0.35, "ETHUSDT": 0.35, "SOLUSDT": 0.25, "XRPUSDT": 0.2, "ADAUSDT": 0.2}
    v = check_target_weights(limits, bad)
    assert any("SOLUSDT" in s for s in v)
    assert any("gross long" in s for s in v)
    assert any("altcoins total" in s for s in v)
    shorts = {"BTCUSDT": -0.35, "ETHUSDT": -0.35}
    assert any("gross short" in s for s in check_target_weights(limits, shorts))
    assert any("beta" in s for s in check_target_weights(
        limits, {"BTCUSDT": 0.35, "SOLUSDT": 0.2}, betas={"SOLUSDT": 4.0}))
