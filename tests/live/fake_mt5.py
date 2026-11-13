"""Minimal fake of the ``MetaTrader5`` module for Linux CI (no terminal needed).

Field names follow the official result types; constants are checked against the real
wheel in the tests. Behaviour is deliberately simple and scriptable.
"""
from __future__ import annotations

from collections import deque, namedtuple
from types import SimpleNamespace

# ---- constants (subset; values identical to MetaTrader5 5.0.6231) ----
TIMEFRAME_M1, TIMEFRAME_M5, TIMEFRAME_M15 = 1, 5, 15
TIMEFRAME_H1, TIMEFRAME_D1 = 1 | 0x4000, 24 | 0x4000
COPY_TICKS_ALL, COPY_TICKS_INFO, COPY_TICKS_TRADE = -1, 1, 2
POSITION_TYPE_BUY, POSITION_TYPE_SELL = 0, 1
ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1
ORDER_TYPE_BUY_LIMIT, ORDER_TYPE_SELL_LIMIT = 2, 3
ORDER_TYPE_BUY_STOP, ORDER_TYPE_SELL_STOP = 4, 5
ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN, ORDER_FILLING_BOC = 0, 1, 2, 3
ORDER_TIME_GTC, ORDER_TIME_DAY, ORDER_TIME_SPECIFIED, ORDER_TIME_SPECIFIED_DAY = 0, 1, 2, 3
TRADE_ACTION_DEAL, TRADE_ACTION_PENDING, TRADE_ACTION_SLTP = 1, 5, 6
TRADE_ACTION_MODIFY, TRADE_ACTION_REMOVE, TRADE_ACTION_CLOSE_BY = 7, 8, 10
SYMBOL_TRADE_MODE_DISABLED, SYMBOL_TRADE_MODE_CLOSEONLY, SYMBOL_TRADE_MODE_FULL = 0, 3, 4
SYMBOL_TRADE_EXECUTION_REQUEST, SYMBOL_TRADE_EXECUTION_INSTANT = 0, 1
SYMBOL_TRADE_EXECUTION_MARKET, SYMBOL_TRADE_EXECUTION_EXCHANGE = 2, 3
SYMBOL_CALC_MODE_CFD, SYMBOL_CALC_MODE_CFDINDEX, SYMBOL_CALC_MODE_CFDLEVERAGE = 2, 3, 4
ACCOUNT_TRADE_MODE_DEMO, ACCOUNT_TRADE_MODE_CONTEST, ACCOUNT_TRADE_MODE_REAL = 0, 1, 2
ACCOUNT_MARGIN_MODE_RETAIL_NETTING, ACCOUNT_MARGIN_MODE_RETAIL_HEDGING = 0, 2
TRADE_RETCODE_REQUOTE, TRADE_RETCODE_PLACED, TRADE_RETCODE_DONE = 10004, 10008, 10009
TRADE_RETCODE_DONE_PARTIAL, TRADE_RETCODE_TIMEOUT = 10010, 10012
TRADE_RETCODE_INVALID_STOPS, TRADE_RETCODE_MARKET_CLOSED = 10016, 10018
TRADE_RETCODE_PRICE_CHANGED, TRADE_RETCODE_CLIENT_DISABLES_AT = 10020, 10027
TRADE_RETCODE_INVALID_FILL = 10030
RES_S_OK, RES_E_INTERNAL_FAIL_TIMEOUT = 1, -10005
__version__ = "5.0.6231-fake"

# ---- result types: attribute names taken from the official docs and from the strings of
# _core.pyd 5.0.6231; field ORDER is not guaranteed, so code must use attribute access ----
SYMBOL_FIELDS = (
    "custom chart_mode select visible session_deals session_buy_orders session_sell_orders "
    "volume volumehigh volumelow time digits spread spread_float ticks_bookdepth "
    "trade_calc_mode trade_mode start_time expiration_time trade_stops_level "
    "trade_freeze_level trade_exemode swap_mode swap_rollover3days margin_hedged_use_leg "
    "expiration_mode filling_mode order_mode order_gtc_mode option_mode option_right bid "
    "bidhigh bidlow ask askhigh asklow last lasthigh lastlow volume_real volumehigh_real "
    "volumelow_real option_strike point trade_tick_value trade_tick_value_profit "
    "trade_tick_value_loss trade_tick_size trade_contract_size trade_accrued_interest "
    "trade_face_value trade_liquidity_rate volume_min volume_max volume_step volume_limit "
    "swap_long swap_short margin_initial margin_maintenance session_volume session_turnover "
    "session_interest session_buy_orders_volume session_sell_orders_volume session_open "
    "session_close session_aw session_price_settlement session_price_limit_min "
    "session_price_limit_max margin_hedged price_change price_volatility price_theoretical "
    "price_greeks_delta price_greeks_theta price_greeks_gamma price_greeks_vega "
    "price_greeks_rho price_greeks_omega price_sensitivity basis category currency_base "
    "currency_profit currency_margin bank description exchange formula isin name page path"
).split()
SymbolInfo = namedtuple("SymbolInfo", SYMBOL_FIELDS, defaults=[0] * len(SYMBOL_FIELDS))
Tick = namedtuple("Tick", "time bid ask last volume time_msc flags volume_real")
AccountInfo = namedtuple(
    "AccountInfo",
    "login trade_mode leverage limit_orders margin_so_mode trade_allowed trade_expert "
    "margin_mode currency_digits fifo_close balance credit profit equity margin margin_free "
    "margin_level margin_so_call margin_so_so margin_initial margin_maintenance assets "
    "liabilities commission_blocked name server currency company")
TerminalInfo = namedtuple(
    "TerminalInfo",
    "community_account community_connection connected dlls_allowed trade_allowed "
    "tradeapi_disabled email_enabled ftp_enabled notifications_enabled mqid build maxbars "
    "codepage ping_last community_balance retransmission company name language path "
    "data_path commondata_path")
OrderCheckResult = namedtuple(
    "OrderCheckResult",
    "retcode balance equity profit margin margin_free margin_level comment request")
OrderSendResult = namedtuple(
    "OrderSendResult",
    "retcode deal order volume price bid ask comment request_id retcode_external request")
TradePosition = namedtuple(
    "TradePosition",
    "ticket time time_msc time_update time_update_msc type magic identifier reason volume "
    "price_open sl tp price_current swap profit symbol comment external_id")

# ---- scriptable state ----
state = SimpleNamespace()


def reset(*, trade_mode=ACCOUNT_TRADE_MODE_DEMO, login=1000001, server="Broker-Demo",
          algo_on=True, equity=10_000.0):
    state.initialized = False
    state.last_error = (RES_S_OK, "Success")
    state.account = AccountInfo(
        login=login, trade_mode=trade_mode, leverage=20, limit_orders=200, margin_so_mode=0,
        trade_allowed=True, trade_expert=True, margin_mode=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
        currency_digits=2, fifo_close=False, balance=equity, credit=0.0, profit=0.0,
        equity=equity, margin=0.0, margin_free=equity, margin_level=0.0, margin_so_call=100.0,
        margin_so_so=50.0, margin_initial=0.0, margin_maintenance=0.0, assets=0.0,
        liabilities=0.0, commission_blocked=0.0, name="demo", server=server, currency="USD",
        company="Fake Broker")
    state.terminal = TerminalInfo(
        community_account=False, community_connection=False, connected=True,
        dlls_allowed=False, trade_allowed=algo_on, tradeapi_disabled=False,
        email_enabled=False, ftp_enabled=False, notifications_enabled=False, mqid=False,
        build=6231, maxbars=100000, codepage=0, ping_last=50_000, community_balance=0.0,
        retransmission=0.0, company="Fake Broker", name="MetaTrader 5", language="English",
        path="C:\\MT5", data_path="C:\\MT5", commondata_path="C:\\Common")
    state.symbols = {}
    state.ticks = {}
    state.send_script = deque()     # retcodes to return from successive order_send calls
    state.sent = []                 # requests that reached order_send
    state.checked = []              # requests that reached order_check
    state.positions = []


def add_symbol(name, **kw):
    base = dict(name=name, visible=False, select=False, trade_mode=SYMBOL_TRADE_MODE_FULL,
                trade_exemode=SYMBOL_TRADE_EXECUTION_MARKET, filling_mode=1, order_mode=127,
                expiration_mode=15, digits=2, point=0.01, trade_tick_size=0.01,
                trade_tick_value=0.01, trade_tick_value_profit=0.01,
                trade_tick_value_loss=0.01, trade_contract_size=1.0, volume_min=0.1,
                volume_max=100.0, volume_step=0.1, trade_stops_level=0, currency_profit="USD",
                trade_calc_mode=SYMBOL_CALC_MODE_CFDINDEX)
    base.update(kw)
    state.symbols[name] = SymbolInfo(**base)


def set_tick(name, bid, ask, server_ts_ms):
    state.ticks[name] = Tick(time=server_ts_ms // 1000, bid=bid, ask=ask, last=0.0, volume=0,
                             time_msc=server_ts_ms, flags=6, volume_real=0.0)


# ---- API ----
def initialize(path=None, **kwargs):
    state.initialized = True
    return True


def shutdown():
    state.initialized = False


def version():
    return (500, 6231, "fake")


def last_error():
    return state.last_error


def account_info():
    return state.account if state.initialized else None


def terminal_info():
    return state.terminal if state.initialized else None


def symbol_info(name):
    return state.symbols.get(name)


def symbol_select(name, enable=True):
    if name not in state.symbols:
        return False
    state.symbols[name] = state.symbols[name]._replace(visible=enable, select=enable)
    return True


def symbol_info_tick(name):
    return state.ticks.get(name)


def _filling_allowed(sym, req):
    f = req.get("type_filling", ORDER_FILLING_FOK)
    if req["action"] == TRADE_ACTION_PENDING:
        return f == ORDER_FILLING_RETURN
    if f == ORDER_FILLING_FOK:
        return bool(sym.filling_mode & 1)
    if f == ORDER_FILLING_IOC:
        return bool(sym.filling_mode & 2)
    if f == ORDER_FILLING_RETURN:
        return sym.trade_exemode != SYMBOL_TRADE_EXECUTION_MARKET
    return False


def order_check(request):
    state.checked.append(dict(request))
    sym = state.symbols.get(request.get("symbol"))
    rc = 0
    if sym is not None and request["action"] in (TRADE_ACTION_DEAL, TRADE_ACTION_PENDING):
        if not _filling_allowed(sym, request):
            rc = TRADE_RETCODE_INVALID_FILL
    a = state.account
    return OrderCheckResult(rc, a.balance, a.equity, 0.0, 0.0, a.margin_free, 0.0,
                            "Done" if rc == 0 else "Unsupported filling mode", request)


def order_send(request):
    state.sent.append(dict(request))
    if not state.terminal.trade_allowed:
        rc = TRADE_RETCODE_CLIENT_DISABLES_AT
    elif state.send_script:
        rc = state.send_script.popleft()
        if rc is None:                       # simulate an IPC failure
            state.last_error = (RES_E_INTERNAL_FAIL_TIMEOUT, "IPC timeout")
            return None
        if isinstance(rc, tuple):            # ("err", code, description)
            state.last_error = (rc[1], rc[2])
            return None
    else:
        rc = TRADE_RETCODE_PLACED if request["action"] == TRADE_ACTION_PENDING else TRADE_RETCODE_DONE
    tick = state.ticks.get(request.get("symbol"))
    return OrderSendResult(rc, 1 if rc == TRADE_RETCODE_DONE else 0, 2, request.get("volume", 0.0),
                           request.get("price", 0.0), tick.bid if tick else 0.0,
                           tick.ask if tick else 0.0, "", 1, 0, request)


def order_calc_profit(action, symbol, volume, price_open, price_close):
    sym = state.symbols[symbol]
    per_unit = sym.trade_tick_value / sym.trade_tick_size
    sign = 1 if action == ORDER_TYPE_BUY else -1
    return sign * (price_close - price_open) * per_unit * volume


def positions_get(symbol=None, ticket=None, group=None):
    out = state.positions
    if symbol is not None:
        out = [p for p in out if p.symbol == symbol]
    if ticket is not None:
        out = [p for p in out if p.ticket == ticket]
    return tuple(out)


def orders_get(symbol=None, ticket=None, group=None):
    return tuple()


reset()
