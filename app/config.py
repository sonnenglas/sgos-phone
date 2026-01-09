from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://placetel:placetel@db:5432/placetel"
    placetel_api_key: str
    elevenlabs_api_key: str
    openrouter_api_key: str = ""

    # Placetel API
    placetel_base_url: str = "https://api.placetel.de/v2"

    # ElevenLabs API
    elevenlabs_base_url: str = "https://api.elevenlabs.io/v1"
    elevenlabs_model: str = "scribe_v2"

    # OpenRouter API
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "google/gemini-3-pro-preview"

    # File storage
    voicemail_storage_path: str = "/app/data/voicemails"

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore dotenvx's DOTENV_PUBLIC_KEY etc.


@lru_cache
def get_settings() -> Settings:
    return Settings()
