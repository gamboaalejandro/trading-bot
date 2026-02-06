import os
import yaml
from typing import Any, Dict
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
    DRY_RUN: bool = Field(default=True, description="Dry run mode")
    
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

# Global Settings Instance
settings = Settings()
settings.load_ai_config()
