import os
import yaml
from typing import Any, Dict
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Binance Keys
    BINANCE_API_KEY: str = Field(..., description="Binance API Key")
    BINANCE_SECRET: str = Field(..., description="Binance Secret Key")
    
    # Environment
    ENV: str = Field("development", description="Environment: development, production")
    
    # Redis
    REDIS_URL: str = Field("redis://localhost:6379", description="Redis Connection URL")

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
