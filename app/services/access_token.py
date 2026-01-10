"""
Public access token generation and verification.

Uses HMAC-SHA256 to create unguessable tokens for voicemail access.
Tokens don't expire - they're tied to the voicemail ID.
"""

import hmac
import hashlib
from app.config import get_settings


def generate_access_token(voicemail_id: int) -> str:
    """Generate a public access token for a voicemail."""
    settings = get_settings()
    message = f"voicemail:{voicemail_id}"
    signature = hmac.new(
        settings.public_access_secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()[:32]  # Use first 32 chars for shorter URLs
    return signature


def verify_access_token(voicemail_id: int, token: str) -> bool:
    """Verify a public access token for a voicemail."""
    expected = generate_access_token(voicemail_id)
    return hmac.compare_digest(token, expected)


def get_public_url(voicemail_id: int) -> str:
    """Get the full public URL for listening to a voicemail."""
    settings = get_settings()
    token = generate_access_token(voicemail_id)
    return f"{settings.base_url}/listen/{voicemail_id}?token={token}"
