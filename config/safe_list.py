"""
Safe List Configuration - SPOT TRADING
Define which trading pairs to operate and their mathematical personalities

This configuration uses a policy-based approach where each asset has:
- Strategy type (momentum vs mean reversion)
- Risk parameters (position size limits)
- Mathematical parameters (RSI period, BB std, etc.)

Tier Classification:
- STABLE: Low volatility, range-bound (BTC, ETH)
- VOLATILE: High volatility, trending (SOL, MATIC)
- MEME: Extreme volatility, unpredictable (DOGE, SHIB, PEPE)

Note: This is configured for SPOT trading (no leverage). Swing trading approach with wide TP/SL.
"""

SAFE_LIST = {
    # --- TIER 1: LOS SEGUROS (STABLE) ---
    "BTC/USDT": {
        "enabled": True,
        "tier": "STABLE",
        "strategy": "mean_reversion", # Compra barato, vende caro en rango
        "description": "Bitcoin - El ancla del portafolio",
        
        "max_position_size_usd": 1000, 
        "max_daily_trades": 10,
        
        "params": {
            "rsi_period": 14,
            "bb_period": 20,
            "bb_std": 2.0,    # Desviación estándar normal
            "min_atr": 100,   # Filtro de volatilidad absoluta
            "oversold": 30,   # Compra cuando RSI < 30
            "overbought": 70
        }
    },
    
    "ETH/USDT": {
        "enabled": True,
        "tier": "STABLE",
        "strategy": "mean_reversion",
        "description": "Ethereum - Seguidor de BTC",
        
        "max_position_size_usd": 800,
        "max_daily_trades": 10,
        
        "params": {
            "rsi_period": 14,
            "bb_period": 20,
            "bb_std": 2.2,    # Un poco más ancho que BTC
            "min_atr": 10,
            "oversold": 30,
            "overbought": 70
        }
    },
    
    # --- TIER 2: SWEET SPOT (Volatilidad Sana) ---
    "SOL/USDT": {
        "enabled": True,
        "tier": "SWEET_SPOT",
        "strategy": "momentum", # Sigue la tendencia fuerte
        "description": "Solana - El motor de ganancias rápidas",
        
        "max_position_size_usd": 700, # Menos capital que BTC por riesgo
        "max_daily_trades": 5,
        
        "params": {
            "rsi_period": 14,
            "ma_fast": 9,
            "ma_slow": 21,
            "bb_std": 2.5,    # Bandas anchas para aguantar "mechas"
            "min_atr": 0.5,
            "oversold": 35,   # En tendencias fuertes, 30 es difícil de tocar
            "overbought": 75  # Deja correr la ganancia más tiempo
        }
    },

    "BNB/USDT": {
        "enabled": True,
        "tier": "SWEET_SPOT",
        "strategy": "mean_reversion",
        "description": "Binance Coin - Híbrido Estabilidad/Volatilidad",
        
        "max_position_size_usd": 800,
        "max_daily_trades": 8,
        
        "params": {
            "rsi_period": 14,
            "bb_period": 20,
            "bb_std": 2.3,    # Desviación media
            "min_atr": 1.0,
            "oversold": 30,
            "overbought": 70
        }
    },

    "AVAX/USDT": {
        "enabled": True,
        "tier": "SWEET_SPOT",
        "strategy": "momentum",
        "description": "Avalanche - Movimientos explosivos tipo SOL",
        
        "max_position_size_usd": 400,
        "max_daily_trades": 5,
        
        "params": {
            "rsi_period": 9,  # RSI rápido para capturar el inicio del pump
            "ma_fast": 7,
            "ma_slow": 25,
            "bb_std": 2.5,
            "min_atr": 0.2,
            "oversold": 40,   # Entra antes (en tendencia alcista el RSI rebota en 40)
            "overbought": 80  # Vende muy arriba
        }
    },

    # --- TIER 3: HIGH VOLATILITY (Manejar con cuidado) ---
    "DOGE/USDT": {
        "enabled": True,
        "tier": "CASINO",
        "strategy": "momentum",
        "description": "Dogecoin - Rey de la volatilidad y liquidez",
        
        "max_position_size_usd": 300, # Capital bajo para alto riesgo
        "max_daily_trades": 3,
        
        "params": {
            "rsi_period": 14,
            "bb_period": 20,
            "bb_std": 2.5,    # ¡Muy ancho! Para ignorar el ruido/mechas
            "min_atr": 0.001,
            "oversold": 30,   # Solo compra si está MUY muerto
            "overbought": 85  # Solo vende si está en la luna
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
        print(f" {symbol}")
        print(f"   Tier: {config['tier']}")
        print(f"   Strategy: {config['strategy']}")
        print(f"   Max Position: ${config['max_position_size_usd']}")
        print(f"   Description: {config['description']}")
        print()
    
    print(f"STABLE pairs: {get_symbols_by_tier('STABLE')}")
    print(f"VOLATILE pairs: {get_symbols_by_tier('VOLATILE')}")
    print(f"Momentum strategy: {get_strategy_symbols('momentum')}")
    print(f"Mean Reversion strategy: {get_strategy_symbols('mean_reversion')}")
