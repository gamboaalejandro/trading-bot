"""
Trading Profiles Configuration
Defines risk/reward parameters per user profile
"""
from dataclasses import dataclass
from typing import Dict


@dataclass
class TradingProfile:
    """Trading profile configuration."""
    name: str
    combination_method: str
    min_confidence: float
    max_risk_per_trade: float
    max_positions: int
    description: str


# Profile definitions
PROFILES: Dict[str, TradingProfile] = {
    "conservative": TradingProfile(
        name="Conservative",
        combination_method="consensus",
        min_confidence=0.65,
        max_risk_per_trade=0.01,  # 1%
        max_positions=1,
        description="Suitable for capital < $10k. Requires all strategies to agree."
    ),
    "moderate": TradingProfile(
        name="Moderate",
        combination_method="majority",
        min_confidence=0.60,
        max_risk_per_trade=0.02,  # 2%
        max_positions=3,
        description="Suitable for capital $10k-$50k. Requires majority (>50%) of strategies."
    ),
    "advanced": TradingProfile(
        name="Advanced",
        combination_method="weighted",
        min_confidence=0.55,
        max_risk_per_trade=0.03,  # 3%
        max_positions=5,
        description="Suitable for capital > $50k. Weighted by confidence scores."
    ),
    "spot_production": TradingProfile(
        name="Spot Production",
        combination_method="consensus",
        min_confidence=0.70,  # High selectivity for Spot
        max_risk_per_trade=0.02,  # 2% per trade (no leverage)
        max_positions=2,  # Conservative max positions (swing trading)
        description="SPOT Production: Swing trading with wide TP/SL, high confidence signals only. No leverage."
    )
}


def get_profile(name: str) -> TradingProfile:
    """
    Get trading profile by name.
    
    Args:
        name: Profile name (conservative, moderate, advanced)
        
    Returns:
        TradingProfile instance (defaults to conservative if invalid)
    """
    profile = PROFILES.get(name.lower(), PROFILES["conservative"])
    return profile


def list_profiles() -> Dict[str, str]:
    """Get list of available profiles with descriptions."""
    return {
        name: profile.description
        for name, profile in PROFILES.items()
    }
