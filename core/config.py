import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Binance Keys
    BINANCE_API_KEY: str = Field(..., description="Binance API Key")
    BINANCE_SECRET: str = Field(..., description="Binance Secret Key")
    
    # Binance Testnet (optional, defaults to main keys if not provided)
    BINANCE_TESTNET_API_KEY: str = Field(default="", description="Binance Testnet API Key")
    BINANCE_TESTNET_SECRET: str = Field(default="", description="Binance Testnet Secret Key")
    USE_TESTNET: bool = Field(default=True, description="Use testnet instead of production")
    
    # Environment
    ENV: str = Field("development", description="Environment: development, production")
    # Legacy switch. TRADING_MODE is authoritative; DRY_RUN=true can only
    # force dry_run, it can never enable order execution.
    DRY_RUN: Optional[bool] = Field(default=None, description="Legacy dry run flag (true forces dry_run)")

    # Execution mode (see resolve_trading_mode)
    TRADING_MODE: str = Field(
        default="dry_run",
        description="Execution mode: dry_run (default), spot_demo, futures_testnet, live"
    )
    LIVE_TRADING_CONFIRM: str = Field(
        default="",
        description="Must equal I_UNDERSTAND for TRADING_MODE=live"
    )
    ALLOW_1M_LIVE: bool = Field(
        default=False,
        description="Explicit opt-in to send orders from 1m (high frequency) profiles"
    )
    
    # Trading Profile Configuration
    TRADING_PROFILE: str = Field(
        default="conservative",
        description="Trading profile: conservative, moderate, advanced"
    )
    MIN_CONFIDENCE_THRESHOLD: float = Field(
        default=0.60,
        description="Minimum confidence threshold for signal execution (0.0-1.0)"
    )
    STRATEGY_COMBINATION_METHOD: str = Field(
        default="consensus",
        description="Method to combine strategies: consensus, majority, weighted, any"
    )
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # ZeroMQ
    ZMQ_FEED_HANDLER_URL: str = "tcp://127.0.0.1:5555"
    
    # Trading Configuration
    MAX_DAILY_DRAWDOWN: float = Field(0.05, description="Maximum daily drawdown (5% = 0.05)")
    MAX_RISK_PER_TRADE: float = Field(0.02, description="Maximum risk per trade (2% = 0.02)")
    KELLY_FRACTION: float = Field(0.25, description="Kelly criterion fraction (0.25 = quarter Kelly)")
    DEFAULT_LEVERAGE: int = Field(1, description="Default leverage for futures")
    
    # Trading Symbol
    DEFAULT_SYMBOL: str = Field("BTC/USDT", description="Default trading symbol")
    DEFAULT_TIMEFRAME: str = Field("1m", description="Default candle timeframe")

    # AI Config (Loaded from YAML)
    AI_CONFIG: Dict[str, Any] = Field(default_factory=dict)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def load_ai_config(self, path: str = "config/ai_config.yml"):
        """Loads AI configuration from a YAML file."""
        if os.path.exists(path):
            with open(path, "r") as f:
                self.AI_CONFIG = yaml.safe_load(f)

logger = logging.getLogger(__name__)

# =========================
# Execution mode safety
# =========================

TRADING_MODES = ("dry_run", "spot_demo", "futures_testnet", "live")
LIVE_CONFIRM_TOKEN = "I_UNDERSTAND"
# Profiles running on candles shorter than this are "1m profiles": their
# round-trip cost exceeds the typical candle range, so they never send orders
# unless ALLOW_1M_LIVE=true.
MIN_ORDER_TIMEFRAME_SECONDS = 15 * 60
_TIMEFRAME_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "M": 2592000}


class TradingModeError(RuntimeError):
    """Raised when the requested execution mode must not start."""


@dataclass(frozen=True)
class ExecutionMode:
    """Resolved execution mode.

    Attributes:
        mode: Effective mode (one of TRADING_MODES).
        requested: Mode requested by the user.
        dry_run: True when no order may reach any exchange.
        use_testnet: True unless the effective mode is ``live``.
        reason: Why the effective mode differs from the requested one ("" if it does not).
    """
    mode: str
    requested: str
    dry_run: bool
    use_testnet: bool
    reason: str = ""


def is_one_minute_timeframe(timeframe: Optional[str]) -> bool:
    """True for intraday profiles below 15m (1m, 3m, 5m...). Unknown -> True (fail safe)."""
    if not timeframe:
        return False
    tf = str(timeframe).strip()
    try:
        seconds = int(tf[:-1]) * _TIMEFRAME_UNITS[tf[-1]]
    except (KeyError, ValueError):
        return True
    return seconds < MIN_ORDER_TIMEFRAME_SECONDS


def resolve_trading_mode(
    mode: Optional[str] = None,
    live_confirm: Optional[str] = None,
    timeframe: Optional[str] = None,
    allow_1m_live: bool = False,
    legacy_dry_run: Optional[bool] = None,
) -> ExecutionMode:
    """Resolve the effective execution mode, failing closed.

    Rules:
        - Missing/empty mode -> ``dry_run``.
        - Unknown mode -> TradingModeError (never guess).
        - ``live`` without ``live_confirm == "I_UNDERSTAND"`` -> TradingModeError.
        - ``legacy_dry_run is True`` (DRY_RUN=true) forces ``dry_run``.
        - 1m profiles (timeframe < 15m) are forced to ``dry_run`` unless
          ``allow_1m_live`` is True.

    Args:
        mode: Requested TRADING_MODE.
        live_confirm: Value of LIVE_TRADING_CONFIRM.
        timeframe: Candle timeframe of the active profile (e.g. '1m', '1d').
        allow_1m_live: Value of ALLOW_1M_LIVE.
        legacy_dry_run: Value of the legacy DRY_RUN flag (None if unset).

    Returns:
        ExecutionMode with the effective mode.
    """
    requested = (mode or "dry_run").strip().lower()
    if requested not in TRADING_MODES:
        raise TradingModeError(
            f"Invalid TRADING_MODE={mode!r}; expected one of {', '.join(TRADING_MODES)}"
        )
    if requested == "live" and (live_confirm or "").strip() != LIVE_CONFIRM_TOKEN:
        raise TradingModeError(
            f"TRADING_MODE=live requires LIVE_TRADING_CONFIRM={LIVE_CONFIRM_TOKEN}"
        )

    reason = ""
    effective = requested
    if requested != "dry_run":
        if legacy_dry_run is True:
            effective, reason = "dry_run", "DRY_RUN=true forces dry_run"
        elif is_one_minute_timeframe(timeframe) and not allow_1m_live:
            effective = "dry_run"
            reason = (
                f"timeframe {timeframe} is a 1m profile: forced to dry_run "
                f"(set ALLOW_1M_LIVE=true to override)"
            )
    if reason:
        logger.critical(f"TRADING_MODE {requested} -> dry_run: {reason}")

    return ExecutionMode(
        mode=effective,
        requested=requested,
        dry_run=effective == "dry_run",
        use_testnet=effective != "live",
        reason=reason,
    )


def resolve_settings_mode(cfg: "Settings", timeframe: Optional[str] = None) -> ExecutionMode:
    """resolve_trading_mode() fed from a Settings instance."""
    return resolve_trading_mode(
        mode=cfg.TRADING_MODE,
        live_confirm=cfg.LIVE_TRADING_CONFIRM,
        timeframe=timeframe if timeframe is not None else cfg.DEFAULT_TIMEFRAME,
        allow_1m_live=cfg.ALLOW_1M_LIVE,
        legacy_dry_run=cfg.DRY_RUN,
    )


# Global Settings Instance
settings = Settings()
settings.load_ai_config()
