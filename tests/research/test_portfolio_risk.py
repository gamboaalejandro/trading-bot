"""Tests for apps.research.portfolio.risk (PLAN §6.2 R05, simulated kill-switch)."""
from pathlib import Path

import pandas as pd
import pytest
import yaml

from apps.research.portfolio.risk import (
    RISK_LIMITS_PATH,
    KillSwitch,
    KillSwitchState,
    RiskConfig,
    RiskConfigError,
    apply_kill_switch,
    check_liquidation,
    load_risk_config,
    simulate_kill_switch,
)


# --------------------------------------------------------------------------- config
def test_repo_risk_limits_match_user_decisions():
    cfg = load_risk_config(RISK_LIMITS_PATH)
    assert cfg.daily_block_entries == -0.02
    assert cfg.daily_flatten_leveraged == -0.05
    assert cfg.dd_half_risk == 0.10
    assert cfg.dd_halt == 0.20
    assert cfg.max_lev_alt == 1.0
    assert cfg.max_lev_major == 1.5
    assert cfg.hard_max_leverage == 3.0
    assert cfg == RiskConfig()
    raw = yaml.safe_load(RISK_LIMITS_PATH.read_text())
    assert raw["gate"]["max_dd_oos_spot"] == 0.20
    assert raw["gate"]["max_dd_oos_futures"] == 0.20
    assert raw["leverage"]["margin_type"] == "ISOLATED"


def test_missing_or_incomplete_config_fails(tmp_path: Path):
    with pytest.raises(RiskConfigError):
        load_risk_config(tmp_path / "nope.yml")
    bad = tmp_path / "bad.yml"
    bad.write_text("daily_loss:\n  block_entries: -0.02\n")
    with pytest.raises(RiskConfigError):
        load_risk_config(bad)


def test_config_rejects_inconsistent_or_excessive_values():
    with pytest.raises(RiskConfigError):
        RiskConfig(daily_block_entries=-0.06, daily_flatten_leveraged=-0.05)
    with pytest.raises(RiskConfigError):
        RiskConfig(dd_half_risk=0.25, dd_halt=0.20)
    with pytest.raises(RiskConfigError):
        RiskConfig(max_lev_major=4.0)


def test_cross_margin_is_rejected(tmp_path: Path):
    raw = yaml.safe_load(RISK_LIMITS_PATH.read_text())
    raw["leverage"]["margin_type"] = "CROSSED"
    p = tmp_path / "cross.yml"
    p.write_text(yaml.safe_dump(raw))
    with pytest.raises(RiskConfigError):
        load_risk_config(p)


# --------------------------------------------------------------------------- kill-switch levels
def test_daily_loss_levels():
    ks = KillSwitch()
    assert ks.update(100.0).level == "normal"
    assert ks.update(98.5).level == "normal"               # -1.5 %
    assert ks.update(98.5 * 0.98).level == "block_entries"  # -2 %
    st = ks.update(98.5 * 0.98 * 0.95)                      # -5 %
    assert st.level == "flatten_leveraged"
    assert st.flatten_leveraged and st.entries_blocked
    # Next day without losses the daily blocks clear (drawdown ~ 8.3 % < 10 %).
    st2 = ks.update(98.5 * 0.98 * 0.95 * 1.001)
    assert st2.level == "normal" and st2.risk_mult == 1.0


def test_drawdown_half_risk_and_halt_latch():
    equity = pd.Series([100, 110, 99, 98.9, 95, 88.5, 87.9, 120.0],
                       index=pd.date_range("2024-01-01", periods=8, freq="1D", tz="UTC"))
    states = simulate_kill_switch(equity)
    assert states["risk_mult"].iloc[1] == 1.0
    assert states["drawdown"].iloc[2] == pytest.approx(0.10)
    assert states["risk_mult"].iloc[2] == 0.5                 # DD 10 %
    assert states["level"].iloc[2] == "flatten_leveraged"     # also a -10 % day
    assert not states["halted"].iloc[5]                        # DD 19.5 %
    assert states["halted"].iloc[6]                            # DD 20.1 %
    assert states["halted"].iloc[7]                            # latched even after recovery
    assert states["risk_mult"].iloc[7] == 0.0


# --------------------------------------------------------------------------- applying the state
def _w(**kw):
    return pd.Series(kw, dtype=float)


def test_apply_normal_and_half_risk():
    target = _w(BTCUSDT=0.3, SOLUSDT=0.2)
    held = _w(BTCUSDT=0.1)
    out = apply_kill_switch(target, held, KillSwitchState())
    assert out.to_dict() == {"BTCUSDT": 0.3, "SOLUSDT": 0.2}
    half = apply_kill_switch(target, held, KillSwitchState(risk_mult=0.5))
    assert half.to_dict() == pytest.approx({"BTCUSDT": 0.15, "SOLUSDT": 0.1})


def test_apply_block_entries_only_reduces():
    target = _w(BTCUSDT=0.5, ETHUSDT=0.1, SOLUSDT=0.2, XRPUSDT=-0.1)
    held = _w(BTCUSDT=0.3, ETHUSDT=0.2, XRPUSDT=0.1)
    out = apply_kill_switch(target, held, KillSwitchState(level="block_entries"))
    assert out["BTCUSDT"] == pytest.approx(0.3)   # no increase
    assert out["ETHUSDT"] == pytest.approx(0.1)   # reduction allowed
    assert out["SOLUSDT"] == 0.0                  # no new entry
    assert out["XRPUSDT"] == 0.0                  # flip blocked: only the close happens


def test_apply_flatten_leveraged_closes_shorts_and_leverage():
    target = _w(BTCUSDT=0.3, ETHUSDT=0.3, SOLUSDT=0.2, DOGEUSDT=-0.1)
    held = _w(BTCUSDT=0.3, ETHUSDT=0.3, SOLUSDT=0.2, DOGEUSDT=-0.1)
    lev = _w(BTCUSDT=1.5, ETHUSDT=1.0, SOLUSDT=1.0, DOGEUSDT=1.0)
    out = apply_kill_switch(target, held, KillSwitchState(level="flatten_leveraged"), leverage=lev)
    assert out.to_dict() == {"BTCUSDT": 0.0, "DOGEUSDT": 0.0, "ETHUSDT": 0.3, "SOLUSDT": 0.2}


def test_apply_halt_flattens_everything():
    out = apply_kill_switch(_w(BTCUSDT=0.3), _w(ETHUSDT=0.2), KillSwitchState("halted", 0.0))
    assert (out == 0).all() and set(out.index) == {"BTCUSDT", "ETHUSDT"}


# --------------------------------------------------------------------------- liquidation check
def test_check_liquidation_enforces_leverage_caps():
    cfg = RiskConfig()
    assert check_liquidation("BTCUSDT", 100.0, 95.0, 1.5, +1, 0.2, cfg)
    assert not check_liquidation("BTCUSDT", 100.0, 95.0, 2.0, +1, 0.2, cfg)
    assert not check_liquidation("SOLUSDT", 100.0, 95.0, 1.5, +1, 0.2, cfg)
    assert check_liquidation("SOLUSDT", 100.0, 95.0, 1.0, +1, 0.8, cfg)
    # Worst wick larger than the 1.5x liquidation distance (~66.3 %) blocks BTC at 1.5x.
    assert not check_liquidation("BTCUSDT", 100.0, 95.0, 1.5, +1, 0.7, cfg)
    assert check_liquidation("BTCUSDT", 100.0, 95.0, 1.0, +1, 0.7, cfg)
