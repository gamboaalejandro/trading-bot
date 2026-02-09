#  Guía de Uso: Sistema de Perfiles de Trading

## Resumen

El sistema de perfiles permite ajustar automáticamente cómo el trading bot combina señales de múltiples estrategias según tu capital y nivel de riesgo.

---

##  Perfiles Disponibles

### **1. Conservative (Conservador)**
```
Capital recomendado: < $10,000
Combination Method: consensus (todas las estrategias deben coincidir)
Min Confidence: 65%
Risk per Trade: 1%
Max Positions: 1
```

**Características:**
-  **Máxima seguridad** - Solo opera con consenso total
-  **Ideal para principiantes**
-  **Pocas señales** pero alta precisión
-  Puede perder oportunidades

**Cuándo usar:**
- Tu primer mes de trading
- Capital < $10k
- Prefieres seguridad sobre frecuencia

---

### **2. Moderate (Moderado)**
```
Capital recomendado: $10,000 - $50,000
Combination Method: majority (>50% de estrategias coinciden)
Min Confidence: 60%
Risk per Trade: 2%
Max Positions: 3
```

**Características:**
-  **Balance entre seguridad y oportunidades**
-  **Más señales** que conservative
-  Permite múltiples posiciones
- ️ Riesgo moderado

**Cuándo usar:**
- Tienes experiencia (3+ meses)
- Capital entre $10k-$50k
- Quieres balance

---

### **3. Advanced (Avanzado)**
```
Capital recomendado: > $50,000
Combination Method: weighted (ponderado por confianza)
Min Confidence: 55%
Risk per Trade: 3%
Max Positions: 5
```

**Características:**
-  **Máxima frecuencia de trades**
-  Usa ponderación inteligente
- ️ **Mayor riesgo/recompensa**
-  Para traders experimentados

**Cuándo usar:**
- Experiencia > 6 meses
- Capital > $50k
- Puedes manejar volatilidad

---

## ️ Cómo Cambiar de Perfil

### **Método 1: Editar .env (Recomendado)**

```bash
# 1. Abrir .env
nano .env

# 2. Cambiar línea:
TRADING_PROFILE=moderate  # cambiar a: conservative, moderate, advanced

# 3. Reiniciar bot
./run_dry_run.sh
```

### **Método 2: Override Manual**

Puedes sobrescribir configuraciones individuales:

```bash
# .env
TRADING_PROFILE=conservative
STRATEGY_COMBINATION_METHOD=majority  # Override el método
MIN_CONFIDENCE_THRESHOLD=0.70          # Override el threshold
```

---

##  Métodos de Combinación Explicados

### **Consensus** (Conservador)
```python
# TODAS las estrategias deben coincidir
Momentum:      BUY  (65%)
Mean Reversion: BUY  (70%)
→ Resultado: BUY 

Momentum:      BUY  (65%)
Mean Reversion: HOLD (30%)
→ Resultado: NO TRADE 
```

### **Majority** (Moderado)
```python
# >50% de estrategias deben coincidir
Con 3 estrategias:
Momentum:      BUY  (75%)
Mean Reversion: BUY  (60%)
Breakout:      HOLD (40%)
→ 2/3 = BUY 

Con 2 estrategias (como ahora):
Momentum:      BUY  (75%)
Mean Reversion: BUY  (60%)
→ 2/2 = BUY 
```

### **Weighted** (Avanzado)
```python
# Suma ponderada por confianza
Momentum:      BUY  @ 80% = +0.80
Mean Reversion: SELL @ 55% = -0.55
→ Diferencia: 0.25 (BUY gana) 

# Requiere diferencia >0.3 para ejecutar
Momentum:      BUY  @ 60% = +0.60
Mean Reversion: SELL @ 58% = -0.58
→ Diferencia: 0.02 (muy close, NO TRADE) 
```

### **Any** (Agresivo - No recomendado sin experiencia)
```python
# Cualquier señal >min_confidence
Momentum:      HOLD (30%)
Mean Reversion: BUY  (65%)
→ Resultado: BUY 

# Genera MUCHAS señales, mayor riesgo
```

---

##  Logs al Iniciar

Cuando el bot arranca, verás estos logs mostrando el perfil activo:

```
2026-02-05 23:00:00 - __main__ - INFO - Trading Profile: Moderate
2026-02-05 23:00:00 - __main__ - INFO - Combination Method: majority
2026-02-05 23:00:00 - __main__ - INFO - Min Confidence: 60%
2026-02-05 23:00:00 - __main__ - INFO - Max Risk per Trade: 2.0%
```

---

##  Recomendación de Prueba

### **Día 1-7: Conservative**
```
TRADING_PROFILE=conservative
```
- Observa cómo funciona el bot
- Entiende las señales
- Valida estrategias

### **Día 8-30: Moderate (si resultados positivos)**
```
TRADING_PROFILE=moderate
```
- Más frecuencia de trades
- Monitorea win rate
- Ajusta si es necesario

### **Mes 2+: Advanced (solo si win rate >55%)**
```
TRADING_PROFILE=advanced
```
- Solo si tienes buenos resultados
- Monitorea drawdown diario
- Vuelve a Moderate si pierdes >5% en un día

---

## ️ Advertencias

1. **NO uses Advanced sin experiencia** - El sistema puede generar muchas señales
2. **DRY_RUN primero SIEMPRE** - Prueba 1-2 semanas antes de trading real
3. **Monitorea el win rate** - Si cae <45%, vuelve a Conservative
4. **Daily loss limit** - Si pierdes >5% en un día, DETENTE

---

##  Comparación Rápida

| Aspecto | Conservative | Moderate | Advanced |
|---|---|---|---|
| **Señales/día** | 1-3 | 5-10 | 10-20+ |
| **Precisión** | Alta (>60%) | Media (>55%) | Variable |
| **Capital min** | $1k | $10k | $50k |
| **Riesgo** | Bajo | Medio | Alto |
| **Para quién** | Principiantes | Experimentados | Expertos |

---

**Última actualización:** 2026-02-05
