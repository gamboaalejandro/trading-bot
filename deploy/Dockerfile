# Trading bot: daily portfolio executor (apps/live/portfolio_executor.py)
FROM python:3.13-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app

COPY requirements.txt requirements-research.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-research.txt

COPY . .

# Journal/state live in data/live (mounted as a volume so they survive restarts)
CMD ["sh", "-c", "python -m apps.live.portfolio_executor --engine ${BOT_ENGINE:-T3} ${BOT_SYMBOLS:+--symbols $BOT_SYMBOLS}"]
