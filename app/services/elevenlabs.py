import httpx
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from app.config import get_settings


@dataclass
class TranscriptionResult:
    text: str
    language: str
    confidence: float
    words: Optional[list] = None


class ElevenLabsService:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.elevenlabs_base_url
        self.model = self.settings.elevenlabs_model
        self.headers = {
            "xi-api-key": self.settings.elevenlabs_api_key,
        }

    async def transcribe(self, file_path: str) -> TranscriptionResult:
        """Transcribe an audio file using ElevenLabs Scribe v2."""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(path, "rb") as f:
                files = {"file": (path.name, f, "audio/mpeg")}
                data = {"model_id": self.model}

                response = await client.post(
                    f"{self.base_url}/speech-to-text",
                    headers=self.headers,
                    files=files,
                    data=data,
                )

            if response.status_code != 200:
                error_detail = response.json().get("detail", {})
                if isinstance(error_detail, dict) and error_detail.get("status") == "audio_too_short":
                    return TranscriptionResult(
                        text="[Audio too short to transcribe]",
                        language="unknown",
                        confidence=0.0,
                    )
                raise Exception(f"Transcription failed: {response.text}")

            result = response.json()

            return TranscriptionResult(
                text=result.get("text", ""),
                language=result.get("language_code", "unknown"),
                confidence=result.get("language_probability", 0.0),
                words=result.get("words"),
            )
