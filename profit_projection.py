import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.safe_list import SAFE_LIST

def calculate_projection():
    print("=" * 60)
    print("PROYECCIÓN DE RENTABILIDAD MENSUAL (SEMI-SAFE STRATEGY)")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d')}")
    print("Nota: Estimación teórica basada en parámetros de configuración.")
    print("=" * 60 + "\n")

    total_capital_required = 0
    total_expected_monthly_pnl = 0

    # Assumptions based on tiers
    assumptions = {
        "STABLE": {
            "win_rate": 0.60,
            "trades_per_week": 2,
            "avg_win_pct": 0.04,  # 4% per trade
            "avg_loss_pct": 0.02, # 2% stop loss
        },
        "SWEET_SPOT": {
            "win_rate": 0.55,
            "trades_per_week": 4,
            "avg_win_pct": 0.06,  # Higher volatility
            "avg_loss_pct": 0.025,
        },
        "CASINO": {
            "win_rate": 0.40,     # Lower win rate
            "trades_per_week": 5,
            "avg_win_pct": 0.10,  # Huge pumps
            "avg_loss_pct": 0.03, # Wider stops
        }
    }

    portfolio_data = []

    for symbol, config in SAFE_LIST.items():
        if not config.get("enabled", False):
            continue

        tier = config.get("tier", "STABLE")
        # Map config tier to assumptions key
        if tier == "STABLE":
            metrics = assumptions["STABLE"]
        elif tier == "SWEET_SPOT":
            metrics = assumptions["SWEET_SPOT"]
        else:
            metrics = assumptions["CASINO"]

        pos_size = config.get("max_position_size_usd", 0)
        total_capital_required += pos_size

        # Weekly Calculation
        trades_per_week = metrics["trades_per_week"]
        win_rate = metrics["win_rate"]

        # Expected Value per Trade = (Win% * Win$) - (Loss% * Loss$)
        ev_per_trade_pct = (win_rate * metrics["avg_win_pct"]) - ((1 - win_rate) * metrics["avg_loss_pct"])

        # Monthly Calculation (4 weeks)
        monthly_trades = trades_per_week * 4
        expected_monthly_return_pct = ev_per_trade_pct * monthly_trades
        expected_monthly_pnl = pos_size * expected_monthly_return_pct

        total_expected_monthly_pnl += expected_monthly_pnl

        portfolio_data.append({
            "Symbol": symbol,
            "Tier": tier,
            "Capital ($)": pos_size,
            "Trades/Mo": monthly_trades,
            "Exp. Return": f"{expected_monthly_return_pct:.1%}",
            "Est. PnL ($)": expected_monthly_pnl
        })

    # Display Table
    df = pd.DataFrame(portfolio_data)
    print(df.to_string(index=False, formatters={
        "Capital ($)": "${:,.0f}".format,
        "Est. PnL ($)": "${:,.2f}".format
    }))

    print("\n" + "=" * 60)
    print("RESUMEN DEL PORTAFOLIO")
    print("=" * 60)
    print(f"Capital Total Requerido:   ${total_capital_required:,.2f}")

    roi_monthly = (total_expected_monthly_pnl / total_capital_required) * 100 if total_capital_required > 0 else 0

    print(f"Ganancia Mensual Estimada: ${total_expected_monthly_pnl:,.2f}")
    print(f"ROI Mensual Proyectado:    {roi_monthly:.2f}%")
    print("=" * 60)

    print("\nCONCLUSIÓN:")
    print(f"- Con un capital de ${total_capital_required:,.0f}, podrías generar ~${total_expected_monthly_pnl:,.0f} al mes.")
    print("- Esta es una estrategia 'Semi-Safe' porque diversifica entre activos estables y volátiles.")
    print("- El mayor riesgo está en DOGE (Casino), pero su tamaño de posición es pequeño.")
    print("- Para 'maximizar' más, tendrías que usar Futuros (Apalancamiento), lo cual aumenta el riesgo exponencialmente.")

if __name__ == "__main__":
    calculate_projection()
