"""Read-only MetaTrader 5 smoke check: it sends NO orders.

Run it on the Windows PC with the MT5 terminal open and logged in to a DEMO account
(guide: docs/MT5_QUICKSTART.md):

    set MT5_TERMINAL_PATH=C:\\MT5-bot\\terminal64.exe   (optional)
    set MT5_SYMBOLS=US100,NAS100,USTEC,NVDA,NVDA.US,#NVDA
    python scripts/mt5_smoke_check.py

It prints the package/terminal versions, whether the account is demo, the Algo
Trading button state, the contract specification of each symbol the broker offers
and the estimated server clock offset (valid only while the market is open).
"""
from __future__ import annotations

import os
import time


def main() -> int:
    import MetaTrader5 as mt5  # imported here so tests can inject a fake module

    path = os.environ.get("MT5_TERMINAL_PATH")
    ok = mt5.initialize(path) if path else mt5.initialize()
    if not ok:
        print("initialize() failed:", mt5.last_error())
        return 1
    try:
        print("package", mt5.__version__, "terminal", mt5.version())
        acc, term = mt5.account_info(), mt5.terminal_info()
        if acc is None or term is None:
            print("no account/terminal info:", mt5.last_error())
            return 1
        print("server", acc.server, "| demo", acc.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO,
              "| hedging", acc.margin_mode == mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
              "| currency", acc.currency, "| account trade_allowed", acc.trade_allowed,
              "| trade_expert", acc.trade_expert)
        print("connected", term.connected, "| algo trading button", term.trade_allowed,
              "| tradeapi_disabled", term.tradeapi_disabled, "| maxbars", term.maxbars,
              "| build", term.build)
        for name in os.environ.get("MT5_SYMBOLS", "US100,NAS100,USTEC").split(","):
            s = mt5.symbol_info(name)
            if s is None:
                print(f"{name}: not offered by this broker")
                continue
            mt5.symbol_select(name, True)
            spec = dict(desc=s.description, calc=s.trade_calc_mode, exe=s.trade_exemode,
                        filling=s.filling_mode, order_mode=s.order_mode,
                        expiration=s.expiration_mode, contract=s.trade_contract_size,
                        tick_size=s.trade_tick_size, tick_value=s.trade_tick_value,
                        vmin=s.volume_min, vstep=s.volume_step, vmax=s.volume_max,
                        stops_level=s.trade_stops_level, freeze_level=s.trade_freeze_level,
                        digits=s.digits, ccy=s.currency_profit, trade_mode=s.trade_mode)
            print(name, spec)
            t = mt5.symbol_info_tick(name)
            if t is not None:
                raw = t.time_msc / 1000.0 - time.time()
                print(f"  spread={t.ask - t.bid:.5f} server_offset~{round(raw / 900) * 900}s "
                      f"(valid only if the market is open: raw={raw:.0f}s)")
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
