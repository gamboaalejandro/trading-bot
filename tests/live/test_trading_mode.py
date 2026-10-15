"""H0: execution mode safety (dry_run default, confirmed live, 1m profiles)."""
import asyncio
import inspect

import pytest

import apps.executor.multi_symbol_engine as engine_mod
from apps.executor.profiles import PROFILES
from core.config import (
    LIVE_CONFIRM_TOKEN,
    Settings,
    TradingModeError,
    is_one_minute_timeframe,
    resolve_settings_mode,
    resolve_trading_mode,
)

MODE_ENV = ("TRADING_MODE", "LIVE_TRADING_CONFIRM", "ALLOW_1M_LIVE", "DRY_RUN", "DEFAULT_TIMEFRAME")


@pytest.fixture
def clean_env(monkeypatch):
    for name in MODE_ENV:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, BINANCE_API_KEY="k", BINANCE_SECRET="s", **overrides)


def test_start_without_flags_is_dry_run(clean_env):
    cfg = make_settings()
    assert cfg.TRADING_MODE == "dry_run"
    mode = resolve_settings_mode(cfg)
    assert mode.mode == "dry_run"
    assert mode.dry_run is True
    assert mode.use_testnet is True


def test_empty_mode_defaults_to_dry_run():
    assert resolve_trading_mode().mode == "dry_run"
    assert resolve_trading_mode("", timeframe="1d").dry_run is True


def test_invalid_mode_refuses_to_start():
    with pytest.raises(TradingModeError):
        resolve_trading_mode("production", timeframe="1d")


@pytest.mark.parametrize("confirm", [None, "", "yes", "i_understand", "I UNDERSTAND"])
def test_live_requires_exact_confirmation(confirm):
    with pytest.raises(TradingModeError):
        resolve_trading_mode("live", live_confirm=confirm, timeframe="1d")


def test_confirmed_live_on_daily_profile():
    mode = resolve_trading_mode("live", live_confirm=LIVE_CONFIRM_TOKEN, timeframe="1d")
    assert mode.mode == "live"
    assert mode.dry_run is False
    assert mode.use_testnet is False


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_1m_profiles_reject_live(profile):
    # Every existing profile runs on DEFAULT_TIMEFRAME=1m
    cfg = make_settings(
        TRADING_PROFILE=profile, TRADING_MODE="live", LIVE_TRADING_CONFIRM=LIVE_CONFIRM_TOKEN
    )
    assert cfg.DEFAULT_TIMEFRAME == "1m"
    mode = resolve_settings_mode(cfg)
    assert mode.mode == "dry_run"
    assert mode.dry_run is True
    assert mode.use_testnet is True
    assert "ALLOW_1M_LIVE" in mode.reason


@pytest.mark.parametrize("requested", ["spot_demo", "futures_testnet", "live"])
@pytest.mark.parametrize("timeframe", ["1m", "3m", "5m"])
def test_sub_15m_timeframes_forced_to_dry_run(requested, timeframe):
    mode = resolve_trading_mode(requested, live_confirm=LIVE_CONFIRM_TOKEN, timeframe=timeframe)
    assert mode.mode == "dry_run"
    assert mode.requested == requested


def test_allow_1m_live_flag_is_explicit_opt_in():
    mode = resolve_trading_mode(
        "live", live_confirm=LIVE_CONFIRM_TOKEN, timeframe="1m", allow_1m_live=True
    )
    assert mode.mode == "live"
    # The flag never bypasses the live confirmation
    with pytest.raises(TradingModeError):
        resolve_trading_mode("live", timeframe="1m", allow_1m_live=True)


def test_allow_1m_live_from_env(clean_env):
    clean_env.setenv("TRADING_MODE", "spot_demo")
    clean_env.setenv("ALLOW_1M_LIVE", "true")
    mode = resolve_settings_mode(make_settings())
    assert mode.mode == "spot_demo"
    assert mode.dry_run is False
    assert mode.use_testnet is True


def test_legacy_dry_run_true_forces_dry_run():
    mode = resolve_trading_mode("spot_demo", timeframe="1h", legacy_dry_run=True)
    assert mode.mode == "dry_run"
    # DRY_RUN=false never enables trading by itself
    assert resolve_trading_mode(None, timeframe="1h", legacy_dry_run=False).mode == "dry_run"


@pytest.mark.parametrize("tf,expected", [
    ("1m", True), ("5m", True), ("15m", False), ("1h", False), ("4h", False),
    ("1d", False), ("1w", False), ("1M", False), ("garbage", True),
])
def test_one_minute_timeframe_detection(tf, expected):
    assert is_one_minute_timeframe(tf) is expected


def test_engine_defaults_to_dry_run():
    default = inspect.signature(engine_mod.MultiSymbolEngine.__init__).parameters["dry_run"].default
    assert default is True


def test_engine_rejects_futures_testnet():
    cfg = make_settings(TRADING_MODE="futures_testnet", DEFAULT_TIMEFRAME="1d")
    with pytest.raises(TradingModeError):
        engine_mod.resolve_engine_mode(cfg)


class _EngineSpy:
    created = []

    def __init__(self, **kwargs):
        _EngineSpy.created.append(kwargs)

    async def start(self):
        return None


@pytest.fixture
def engine_spy(monkeypatch):
    _EngineSpy.created = []
    monkeypatch.setattr(engine_mod, "MultiSymbolEngine", _EngineSpy)
    return _EngineSpy


def test_main_without_flags_runs_dry(monkeypatch, engine_spy):
    monkeypatch.setattr(engine_mod, "settings", make_settings(DRY_RUN=False, USE_TESTNET=False))
    asyncio.run(engine_mod.main())
    assert engine_spy.created == [{"use_testnet": True, "dry_run": True}]


def test_main_refuses_unconfirmed_live(monkeypatch, engine_spy):
    monkeypatch.setattr(engine_mod, "settings", make_settings(TRADING_MODE="live", DEFAULT_TIMEFRAME="1d"))
    with pytest.raises(TradingModeError):
        asyncio.run(engine_mod.main())
    assert engine_spy.created == []


def test_main_1m_live_forced_dry(monkeypatch, engine_spy):
    monkeypatch.setattr(
        engine_mod, "settings",
        make_settings(TRADING_MODE="live", LIVE_TRADING_CONFIRM=LIVE_CONFIRM_TOKEN),
    )
    asyncio.run(engine_mod.main())
    assert engine_spy.created == [{"use_testnet": True, "dry_run": True}]


def test_main_confirmed_live_daily(monkeypatch, engine_spy):
    monkeypatch.setattr(
        engine_mod, "settings",
        make_settings(TRADING_MODE="live", LIVE_TRADING_CONFIRM=LIVE_CONFIRM_TOKEN, DEFAULT_TIMEFRAME="1d"),
    )
    asyncio.run(engine_mod.main())
    assert engine_spy.created == [{"use_testnet": False, "dry_run": False}]


def test_main_spot_demo_uses_testnet(monkeypatch, engine_spy):
    monkeypatch.setattr(
        engine_mod, "settings", make_settings(TRADING_MODE="spot_demo", DEFAULT_TIMEFRAME="4h", USE_TESTNET=False)
    )
    asyncio.run(engine_mod.main())
    assert engine_spy.created == [{"use_testnet": True, "dry_run": False}]
