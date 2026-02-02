import hashlib
import hmac
from core.config import settings

def sign_data(data: str) -> str:
    """Signs data using the BINANCE_SECRET (or internal secret) for integrity verification."""
    return hmac.new(
        settings.BINANCE_SECRET.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def verify_signature(data: str, signature: str) -> bool:
    """Verifies that the data matches the provided signature."""
    expected_doc = sign_data(data)
    return hmac.compare_digest(expected_doc, signature)
