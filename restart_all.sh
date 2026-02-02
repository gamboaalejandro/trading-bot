#!/bin/bash
# Restart all services with one command

echo "Restarting all services..."

# Stop existing
./stop_all.sh

echo "Waiting 2 seconds..."
sleep 2

# Start Redis
sudo docker compose up -d redis
sleep 1

# Start Feed Handler in background
nohup ./run_feed_handler.sh > logs/feed_handler.log 2>&1 &
echo "Feed Handler started (PID: $!)"
sleep 2

# Start Metrics Collector in background  
nohup ./run_metrics_collector.sh > logs/metrics_collector.log 2>&1 &
echo "Metrics Collector started (PID: $!)"
sleep 1

# Start Dashboard in background
nohup ./run_dashboard.sh > logs/dashboard.log 2>&1 &
echo "Dashboard started (PID: $!)"

echo ""
echo "All services started!"
echo "Dashboard: http://localhost:8000"
echo ""
echo "Check logs:"
echo "  tail -f logs/feed_handler.log"
echo "  tail -f logs/metrics_collector.log"
echo "  tail -f logs/dashboard.log"
