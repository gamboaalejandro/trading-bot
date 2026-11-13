"""The MT5 smoke check runs against a fake MetaTrader5 module and never sends orders."""
import sys
from datetime import datetime, timezone

from scripts import mt5_smoke_check
from tests.live import fake_mt5 as mt5


def _market_setup():
    mt5.reset()
    mt5.add_symbol("US100", volume_min=0.01, volume_step=0.01)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000) + 7_200_000  # server = UTC+2
    mt5.set_tick("US100", 28_000.0, 28_001.0, now_ms)


def test_smoke_check_is_read_only(monkeypatch, capsys):
    _market_setup()
    monkeypatch.setitem(sys.modules, "MetaTrader5", mt5)
    monkeypatch.setenv("MT5_SYMBOLS", "US100,NOPE")
    assert mt5_smoke_check.main() == 0
    out = capsys.readouterr().out
    assert "demo True" in out
    assert "NOPE: not offered by this broker" in out
    assert "server_offset~7200s" in out
    assert mt5.state.sent == [] and mt5.state.checked == []  # no order ever reached the terminal


def test_smoke_check_reports_initialize_failure(monkeypatch, capsys):
    _market_setup()
    monkeypatch.setitem(sys.modules, "MetaTrader5", mt5)
    monkeypatch.setattr(mt5, "initialize", lambda *a, **k: False)
    assert mt5_smoke_check.main() == 1
    assert "initialize() failed" in capsys.readouterr().out
