#!/bin/bash
# Script para probar conectividad con Binance Futures Testnet

echo "🧪 Probando Binance Futures Testnet"
echo "===================================="
echo ""

# Cargar variables de entorno
source .env

# URLs del testnet
TESTNET_BASE="https://testnet.binancefuture.com"
API_KEY="${BINANCE_TESTNET_API_KEY}"
SECRET="${BINANCE_TESTNET_SECRET}"

echo "📡 Test 1: Ping al servidor (público - sin autenticación)"
echo "-----------------------------------------------------------"
curl -s "${TESTNET_BASE}/fapi/v1/ping" | jq '.' || echo "Response: OK (empty JSON expected)"
echo ""
echo ""

echo "⏰ Test 2: Server Time (público)"
echo "-----------------------------------------------------------"
curl -s "${TESTNET_BASE}/fapi/v1/time" | jq '.'
echo ""
echo ""

echo "📊 Test 3: Exchange Info (público)"
echo "-----------------------------------------------------------"
curl -s "${TESTNET_BASE}/fapi/v1/exchangeInfo" | jq '.symbols[0] | {symbol, status, contractType}' | head -20
echo ""
echo ""

echo "💰 Test 4: Balance (privado - requiere firma)"
echo "-----------------------------------------------------------"
echo "Preparando request firmado..."

# Generar timestamp
TIMESTAMP=$(date +%s000)

# Query string
QUERY_STRING="timestamp=${TIMESTAMP}"

# Generar firma HMAC SHA256
SIGNATURE=$(echo -n "${QUERY_STRING}" | openssl dgst -sha256 -hmac "${SECRET}" | cut -d' ' -f2)

# Request completo
FULL_URL="${TESTNET_BASE}/fapi/v2/balance?${QUERY_STRING}&signature=${SIGNATURE}"

echo "Timestamp: ${TIMESTAMP}"
echo "Query: ${QUERY_STRING}"
echo "Signature: ${SIGNATURE}"
echo ""

# Ejecutar request
echo "Ejecutando request..."
RESPONSE=$(curl -s -H "X-MBX-APIKEY: ${API_KEY}" "${FULL_URL}")

# Mostrar resultado
echo ""
if echo "${RESPONSE}" | jq '.' > /dev/null 2>&1; then
    echo "✅ Response válida:"
    echo "${RESPONSE}" | jq '.[] | select(.balance != "0") | {asset, balance, availableBalance}'
else
    echo "❌ Error en la respuesta:"
    echo "${RESPONSE}"
fi

echo ""
echo ""
echo "📍 Test 5: Posiciones Actuales (privado)"
echo "-----------------------------------------------------------"

# Nuevo timestamp para otro request
TIMESTAMP=$(date +%s000)
QUERY_STRING="timestamp=${TIMESTAMP}"
SIGNATURE=$(echo -n "${QUERY_STRING}" | openssl dgst -sha256 -hmac "${SECRET}" | cut -d' ' -f2)
FULL_URL="${TESTNET_BASE}/fapi/v2/positionRisk?${QUERY_STRING}&signature=${SIGNATURE}"

RESPONSE=$(curl -s -H "X-MBX-APIKEY: ${API_KEY}" "${FULL_URL}")

if echo "${RESPONSE}" | jq '.' > /dev/null 2>&1; then
    echo "✅ Response válida:"
    echo "${RESPONSE}" | jq '.[] | select(.positionAmt != "0") | {symbol, positionAmt, entryPrice, unrealizedProfit}'
    
    # Si no hay posiciones abiertas
    if [ "$(echo "${RESPONSE}" | jq '[.[] | select(.positionAmt != "0")] | length')" = "0" ]; then
        echo "ℹ️  No hay posiciones abiertas"
    fi
else
    echo "❌ Error en la respuesta:"
    echo "${RESPONSE}"
fi

echo ""
echo "===================================="
echo "Tests completados"
echo "===================================="
