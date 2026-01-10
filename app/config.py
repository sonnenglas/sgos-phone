from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Environment
    env: str = "development"  # development, production

    database_url: str = "postgresql://placetel:placetel@db:5432/placetel"
    placetel_api_key: str
    elevenlabs_api_key: str
    openrouter_api_key: str = ""

    # Placetel API
    placetel_base_url: str = "https://api.placetel.de/v2"
    placetel_webhook_secret: str = ""  # Optional: HMAC secret for webhook verification

    # ElevenLabs API
    elevenlabs_base_url: str = "https://api.elevenlabs.io/v1"
    elevenlabs_model: str = "scribe_v2"

    # OpenRouter API
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "google/gemini-3-pro-preview"

    # File storage
    voicemail_storage_path: str = "/app/data/voicemails"

    # Postmark Email (for voicemail notifications)
    postmark_api_token: str = ""
    email_from: str = ""  # Must be verified in Postmark
    email_from_name: str = "Phone App"

    # Base URL for links in emails (e.g., https://phone.example.com)
    base_url: str = "http://localhost:9000"

    # Access control
    allowed_email: str = "stefan@sonnenglas.net"  # Only this user can access the app
    public_access_secret: str = "change-me-in-production"  # Secret for generating public audio links

    # Error tracking (GlitchTip/Sentry)
    sentry_dsn: str = "https://7099df1a0e1945ecba8d7884b9e4a01c@glitchtip.sgl.as/2"

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore dotenvx's DOTENV_PUBLIC_KEY etc.


@lru_cache
def get_settings() -> Settings:
    return Settings()
