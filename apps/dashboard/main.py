"""
Dashboard API - Real-time monitoring interface via HTTP and WebSocket
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json
import asyncio
from typing import List
from datetime import datetime

from core.database import redis_client

app = FastAPI(title="QuantMind-Alpha Dashboard")

# Active WebSocket connections
active_connections: List[WebSocket] = []

@app.on_event("startup")
async def startup():
    """Initialize Redis connection."""
    await redis_client.get_redis()

@app.on_event("shutdown")
async def shutdown():
    """Close Redis connection."""
    await redis_client.close()

@app.get("/")
async def root():
    """Serve a simple HTML monitoring page."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>QuantMind-Alpha Monitor</title>
        <style>
            body {
                font-family: 'Courier New', monospace;
                background: #0a0e27;
                color: #00ff41;
                padding: 20px;
            }
            h1 { color: #00d4ff; }
            pre {
                background: #1a1e37;
                padding: 15px;
                border-radius: 8px;
                border: 1px solid #00ff41;
            }
            .metric { color: #ffaa00; }
            .value { color: #00ff41; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>🚀 QuantMind-Alpha - Live Monitor</h1>
        <pre id="data">Connecting to WebSocket...</pre>
        <script>
            const ws = new WebSocket('ws://localhost:8000/ws/stream');
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                document.getElementById('data').innerHTML = 
                    `<span class="metric">Symbol:</span> <span class="value">${data.symbol || 'N/A'}</span>\\n` +
                    `<span class="metric">Last Price:</span> <span class="value">$${data.last || 'N/A'}</span>\\n` +
                    `<span class="metric">Bid:</span> <span class="value">$${data.bid || 'N/A'}</span>\\n` +
                    `<span class="metric">Ask:</span> <span class="value">$${data.ask || 'N/A'}</span>\\n` +
                    `<span class="metric">Volume:</span> <span class="value">${data.volume || 'N/A'}</span>\\n` +
                    `<span class="metric">Change %:</span> <span class="value">${data.change_percent?.toFixed(2) || 'N/A'}%</span>\\n\\n` +
                    `<span class="metric">Feed Latency:</span> <span class="value">${data.metrics?.feed_latency_ms?.toFixed(1) || 'N/A'} ms</span>\\n` +
                    `<span class="metric">Messages/sec:</span> <span class="value">${data.metrics?.messages_per_second?.toFixed(2) || 'N/A'}</span>\\n` +
                    `<span class="metric">Uptime:</span> <span class="value">${data.metrics?.uptime_seconds?.toFixed(0) || 'N/A'} sec</span>\\n` +
                    `<span class="metric">Spread (bps):</span> <span class="value">${data.metrics?.spread_bps?.toFixed(2) || 'N/A'}</span>`;
            };
            ws.onopen = () => {
                document.getElementById('data').textContent = 'Connected! Waiting for data...';
            };
            ws.onerror = (error) => {
                document.getElementById('data').textContent = 'WebSocket Error: ' + error;
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/metrics")
async def get_metrics():
    """Get current metrics from Redis."""
    redis_conn = await redis_client.get_redis()
    
    # Get latest metrics
    metrics_raw = await redis_conn.get("metrics:latest")
    metrics = json.loads(metrics_raw) if metrics_raw else {}
    
    # Get latest ticker
    ticker_raw = await redis_conn.get("ticker:BTC/USDT")
    ticker = json.loads(ticker_raw) if ticker_raw else {}
    
    return {
        "ticker": ticker,
        "metrics": metrics,
        "timestamp": datetime.now().isoformat()
    }

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time data streaming."""
    await websocket.accept()
    active_connections.append(websocket)
    
    redis_conn = await redis_client.get_redis()
    
    try:
        while True:
            # Read latest data from Redis
            ticker_raw = await redis_conn.get("ticker:BTC/USDT")
            metrics_raw = await redis_conn.get("metrics:latest")
            
            if ticker_raw:
                ticker = json.loads(ticker_raw)
                metrics = json.loads(metrics_raw) if metrics_raw else {}
                
                # Combine ticker + metrics
                payload = {**ticker, "metrics": metrics}
                
                # Send to client
                await websocket.send_json(payload)
            
            await asyncio.sleep(0.5)  # Update every 500ms
            
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)
