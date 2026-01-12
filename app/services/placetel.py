import logging
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from app.config import get_settings

logger = logging.getLogger(__name__)


class PlacetelService:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.placetel_base_url
        self.headers = {
            "Authorization": f"Bearer {self.settings.placetel_api_key}",
            "Content-Type": "application/json",
        }

    async def fetch_voicemail_by_id(self, external_id: str) -> Optional[dict]:
        """Fetch a single voicemail by its external ID to get a fresh signed URL."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/calls/{external_id}",
                headers=self.headers,
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.warning(f"Voicemail {external_id} not found in Placetel API")
                return None
            else:
                logger.error(f"Failed to fetch voicemail {external_id}: {response.status_code}")
                return None

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

    async def download_voicemail(
        self,
        external_id: str,
        file_url: str,
        storage_path: Optional[str] = None,
        retry_on_expired: bool = True,
    ) -> str:
        """
        Download a voicemail MP3 file and return the local path.

        If the signed URL has expired (400/403), automatically fetches a fresh
        URL from the Placetel API and retries the download.
        """
        if storage_path is None:
            storage_path = self.settings.voicemail_storage_path

        Path(storage_path).mkdir(parents=True, exist_ok=True)

        filename = f"voicemail_{external_id}.mp3"
        local_path = Path(storage_path) / filename

        async with httpx.AsyncClient() as client:
            response = await client.get(file_url)

            # Handle expired signed URLs
            if response.status_code in (400, 403) and retry_on_expired:
                logger.warning(f"Signed URL expired for voicemail {external_id}, fetching fresh URL...")

                # Fetch fresh voicemail data with new signed URL
                fresh_data = await self.fetch_voicemail_by_id(external_id)
                if fresh_data and fresh_data.get("file_url"):
                    new_url = fresh_data["file_url"]
                    logger.info(f"Got fresh URL for voicemail {external_id}, retrying download...")

                    # Retry with fresh URL (don't retry again to avoid infinite loop)
                    return await self.download_voicemail(
                        external_id, new_url, storage_path, retry_on_expired=False
                    )
                else:
                    raise Exception(f"Could not get fresh URL for voicemail {external_id}")

            response.raise_for_status()

            with open(local_path, "wb") as f:
                f.write(response.content)

        logger.info(f"Downloaded voicemail {external_id} to {local_path}")
        return str(local_path)

    async def fetch_numbers(self) -> list[dict]:
        """Fetch all phone numbers from Placetel API."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/numbers",
                headers=self.headers,
                params={"per_page": 100},
            )

            if response.status_code == 200:
                return response.json()
            return []
