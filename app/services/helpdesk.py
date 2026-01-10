"""
Helpdesk API integration for sending voicemail notifications.

This is a placeholder. Configure the actual API endpoint via settings.
The implementation will be completed when the API details are provided.
"""

import logging
from pathlib import Path
import httpx

logger = logging.getLogger(__name__)


class HelpdeskService:
    """Send voicemail notifications to helpdesk system."""

    def __init__(self, api_url: str):
        self.api_url = api_url

    async def send_voicemail(
        self,
        voicemail_id: int,
        from_number: str,
        to_number: str,
        duration: int,
        received_at: str,
        summary: str,
        transcript: str,
        audio_path: str | None = None,
    ) -> dict:
        """
        Send a voicemail notification to the helpdesk.

        Args:
            voicemail_id: Internal voicemail ID
            from_number: Caller's phone number
            to_number: Called number
            duration: Call duration in seconds
            received_at: When the voicemail was received
            summary: LLM-generated summary
            transcript: Full corrected transcript
            audio_path: Path to MP3 file (optional)

        Returns:
            Response from the helpdesk API
        """
        if not self.api_url:
            raise ValueError("Helpdesk API URL not configured")

        # Prepare the payload
        # TODO: Adjust format based on actual API requirements
        payload = {
            "voicemail_id": voicemail_id,
            "from_number": from_number,
            "to_number": to_number,
            "duration": duration,
            "received_at": received_at,
            "summary": summary,
            "transcript": transcript,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # If audio file exists, send as multipart
            if audio_path and Path(audio_path).exists():
                files = {"audio": open(audio_path, "rb")}
                response = await client.post(
                    self.api_url,
                    data=payload,
                    files=files,
                )
            else:
                response = await client.post(
                    self.api_url,
                    json=payload,
                )

            response.raise_for_status()
            return response.json()
