import httpx
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from app.config import get_settings


class PlacetelService:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.placetel_base_url
        self.headers = {
            "Authorization": f"Bearer {self.settings.placetel_api_key}",
            "Content-Type": "application/json",
        }

    async def fetch_voicemails(self, days: int = 30) -> list[dict]:
        """Fetch voicemails from Placetel API for the specified number of days."""
        all_voicemails = []

        async with httpx.AsyncClient() as client:
            for days_ago in range(days):
                date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                params = {
                    "filter[date]": date,
                    "filter[type]": "voicemail",
                    "per_page": 100,
                }

                response = await client.get(
                    f"{self.base_url}/calls",
                    headers=self.headers,
                    params=params,
                )

                if response.status_code == 200:
                    calls = response.json()
                    # Only include voicemails with file_url
                    voicemails = [c for c in calls if c.get("file_url")]
                    all_voicemails.extend(voicemails)

        return all_voicemails

    async def download_voicemail(self, voicemail_id: int, file_url: str, storage_path: Optional[str] = None) -> str:
        """Download a voicemail MP3 file and return the local path."""
        if storage_path is None:
            storage_path = self.settings.voicemail_storage_path

        Path(storage_path).mkdir(parents=True, exist_ok=True)

        filename = f"voicemail_{voicemail_id}.mp3"
        local_path = Path(storage_path) / filename

        async with httpx.AsyncClient() as client:
            response = await client.get(file_url)
            response.raise_for_status()

            with open(local_path, "wb") as f:
                f.write(response.content)

        return str(local_path)
