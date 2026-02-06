"""
Safe List Configuration
Define which trading pairs to operate and their mathematical personalities

This configuration uses a policy-based approach where each asset has:
- Strategy type (momentum vs mean reversion)
- Risk parameters (leverage, position size)
- Mathematical parameters (RSI period, BB std, etc.)

Tier Classification:
- STABLE: Low volatility, range-bound (BTC, ETH)
- VOLATILE: High volatility, trending (SOL, MATIC)
- MEME: Extreme volatility, unpredictable (DOGE, SHIB, PEPE)
"""

SAFE_LIST = {
    "BTC/USDT": {
        "enabled": True,
        "tier": "STABLE",
        "strategy": "mean_reversion",
        "description": "Bitcoin - Most liquid, oscillates in ranges",
        
        # Risk Management
        "leverage": 5,
        "max_position_size_usd": 5000,
        "max_daily_trades": 10,
        
        # Strategy Parameters
        "params": {
            "rsi_period": 14,
            "bb_period": 20,
            "bb_std": 2.0,  # Standard deviation for Bollinger Bands
            "min_atr": 100,  # Minimum ATR to trade (filters low volatility)
            "oversold": 30,
            "overbought": 70
        }
    },
    
    "ETH/USDT": {
        "enabled": True,
        "tier": "STABLE",
        "strategy": "mean_reversion",
        "description": "Ethereum - Follows BTC, slightly more volatile",
        
        # Risk Management
        "leverage": 5,
        "max_position_size_usd": 3000,
        "max_daily_trades": 10,
        
        # Strategy Parameters
        "params": {
            "rsi_period": 14,
            "bb_period": 20,
            "bb_std": 2.2,  # Slightly wider bands than BTC
            "min_atr": 50,
            "oversold": 30,
            "overbought": 70
        }
    },
    
    "SOL/USDT": {
        "enabled": True,
        "tier": "VOLATILE",
        "strategy": "momentum",
        "description": "Solana - High volatility, strong trends",
        
        # Risk Management (more conservative due to volatility)
        "leverage": 2,
        "max_position_size_usd": 1000,
        "max_daily_trades": 5,
        
        # Strategy Parameters
        "params": {
            "rsi_period": 9,    # Faster RSI for quick reactions
            "ma_fast": 8,
            "ma_slow": 21,
            "min_atr": 1.0,  # SOL always has volatility
            "oversold": 35,   # Adjusted thresholds
            "overbought": 65
        }
    },
    
    # Example: Disabled pair (for future use)
    "MATIC/USDT": {
        "enabled": False,  # Not trading yet
        "tier": "VOLATILE",
        "strategy": "momentum",
        "description": "Polygon - Altcoin with trending behavior",
        
        "leverage": 2,
        "max_position_size_usd": 800,
        "max_daily_trades": 5,
        
        "params": {
            "rsi_period": 9,
            "ma_fast": 8,
            "ma_slow": 21,
            "min_atr": 0.01,
            "oversold": 35,
            "overbought": 65
        }
    }
}


def get_active_symbols():
    """
    Get list of enabled trading pairs.
    
    Returns:
        List[str]: Symbols with enabled=True
    """
    return [symbol for symbol, config in SAFE_LIST.items() if config.get("enabled", False)]


def get_symbol_config(symbol: str):
    """
    Get configuration for specific symbol.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USDT')
        
    Returns:
        dict: Configuration or None if not found
    """
    return SAFE_LIST.get(symbol, None)


def get_symbols_by_tier(tier: str):
    """
    Get symbols filtered by tier classification.
    
    Args:
        tier: 'STABLE', 'VOLATILE', or 'MEME'
        
    Returns:
        List[str]: Symbols matching the tier
    """
    return [
        symbol for symbol, config in SAFE_LIST.items()
        if config.get("tier") == tier and config.get("enabled", False)
    ]


def get_strategy_symbols(strategy: str):
    """
    Get symbols using specific strategy.
    
    Args:
        strategy: 'momentum' or 'mean_reversion'
        
    Returns:
        List[str]: Symbols using that strategy
    """
    return [
        symbol for symbol, config in SAFE_LIST.items()
        if config.get("strategy") == strategy and config.get("enabled", False)
    ]


# Validation
if __name__ == "__main__":
    print("=== SAFE LIST CONFIGURATION ===\n")
    
    active = get_active_symbols()
    print(f"Active Symbols ({len(active)}): {active}\n")
    
    for symbol in active:
        config = get_symbol_config(symbol)
        print(f"📊 {symbol}")
        print(f"   Tier: {config['tier']}")
        print(f"   Strategy: {config['strategy']}")
        print(f"   Max Position: ${config['max_position_size_usd']}")
        print(f"   Leverage: {config['leverage']}x")
        print(f"   Description: {config['description']}")
        print()
    
    print(f"STABLE pairs: {get_symbols_by_tier('STABLE')}")
    print(f"VOLATILE pairs: {get_symbols_by_tier('VOLATILE')}")
    print(f"Momentum strategy: {get_strategy_symbols('momentum')}")
    print(f"Mean Reversion strategy: {get_strategy_symbols('mean_reversion')}")
