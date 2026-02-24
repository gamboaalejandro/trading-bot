"""
Sentiment Analysis Module
Fetches "Crypto Fear & Greed Index" and simulates News Sentiment.
"""
import requests
import logging
import random
from datetime import datetime

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """
    Analyzes market sentiment to adjust trading strategies.

    Sources:
    1. Alternative.me Crypto Fear & Greed Index (Public API)
    2. News Sentiment (Mocked/Placeholder for future API integration)
    """

    FEAR_GREED_API = "https://api.alternative.me/fng/"

    def __init__(self):
        self.last_update = None
        self.current_sentiment = {}

    def get_fear_and_greed(self):
        """
        Fetch the Crypto Fear & Greed Index.
        Returns a score from 0 (Extreme Fear) to 100 (Extreme Greed).
        """
        try:
            response = requests.get(self.FEAR_GREED_API, timeout=5)
            response.raise_for_status()
            data = response.json()

            if 'data' in data and len(data['data']) > 0:
                value = int(data['data'][0]['value'])
                classification = data['data'][0]['value_classification']
                logger.info(f"Fear & Greed Index: {value} ({classification})")
                return value, classification

        except Exception as e:
            logger.error(f"Error fetching Fear & Greed Index: {e}")

        # Fallback
        return 50, "Neutral"

    def get_news_sentiment(self, symbol="BTC"):
        """
        Get news sentiment for a specific symbol.
        Currently a placeholder that returns Neutral (0.0) or simulates data.

        Real implementation would use NewsAPI, CryptoPanic, or LunarCrush.
        """
        # Placeholder logic: Random walk around 0 (Neutral)
        # Score: -1.0 (Very Negative) to 1.0 (Very Positive)
        score = random.uniform(-0.2, 0.2)
        return score

    def get_sentiment_multiplier(self) -> float:
        """
        Calculate a multiplier for trading confidence based on sentiment.

        Logic:
        - Extreme Fear (<20): High risk. Reduce LONG confidence (0.8x), Boost SHORT (1.2x).
        - Fear (20-40): Cautious.
        - Neutral (40-60): No change (1.0x).
        - Greed (60-80): Bullish. Boost LONG (1.1x).
        - Extreme Greed (>80): FOMO risk. Be careful with LONGs (0.9x reversion risk?), or ride trend?
          Let's say in Spot we ride it: Boost LONG (1.2x).

        Returns:
            Multiplier for BUY signal confidence.
        """
        fng_value, _ = self.get_fear_and_greed()

        # Base logic for Spot (Long Only)
        if fng_value < 20:
            # Extreme Fear: potentially good entry (contrarian) OR falling knife.
            # Safety first: slightly reduce confidence to wait for confirmation
            return 0.9
        elif fng_value < 40:
            return 0.95
        elif fng_value > 80:
            # Extreme Greed: FOMO. High chance of correction.
            return 0.9
        elif fng_value > 60:
            # Greed: Strong trend.
            return 1.1
        else:
            return 1.0

if __name__ == "__main__":
    # Test
    sa = SentimentAnalyzer()
    score, label = sa.get_fear_and_greed()
    print(f"Index: {score} ({label})")
    print(f"Multiplier: {sa.get_sentiment_multiplier()}")
