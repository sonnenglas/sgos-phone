"""
Email service for voicemail notifications using Postmark.

Generates beautiful HTML emails with voicemail details.
"""

import httpx
import base64
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

POSTMARK_API_URL = "https://api.postmarkapp.com/email"


@dataclass
class VoicemailEmailData:
    """Data needed to generate a voicemail email."""
    id: int
    from_number: str
    to_number: str
    to_number_name: Optional[str]
    duration: int
    received_at: datetime
    summary: str  # Summary in original language
    summary_en: Optional[str]  # English translation
    corrected_text: str
    transcription_text: str
    sentiment: Optional[str]
    emotion: Optional[str]
    category: Optional[str]
    priority: Optional[str]
    audio_url: str
    email_subject: Optional[str] = None  # LLM-generated subject line
    local_file_path: Optional[str] = None


def format_duration(seconds: int) -> str:
    """Format duration as mm:ss or hh:mm:ss."""
    if seconds < 3600:
        return f"{seconds // 60}:{seconds % 60:02d}"
    return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def format_phone(number: str) -> str:
    """Format phone number for display with international format."""
    if not number:
        return "Unknown"

    # Normalize to +49 format
    clean = number.strip()
    if clean.startswith("0049"):
        clean = "+49" + clean[4:]
    elif clean.startswith("00"):
        clean = "+" + clean[2:]
    elif clean.startswith("0") and not clean.startswith("+"):
        clean = "+49" + clean[1:]

    # Add spaces for readability (German mobile: +49 176 1234 5678)
    if clean.startswith("+49"):
        rest = clean[3:]
        if len(rest) >= 10:
            # Mobile numbers (176, 177, 178, 179, 151, 152, 157, 160, 162, 163, 170, 171, 172, 173, 174, 175)
            return f"+49 {rest[:3]} {rest[3:7]} {rest[7:]}"
        elif len(rest) >= 7:
            # Shorter numbers
            return f"+49 {rest[:3]} {rest[3:]}"
        else:
            return f"+49 {rest}"

    return clean


def get_priority_badge(priority: Optional[str]) -> str:
    """Generate priority badge HTML."""
    if priority == "high":
        return '<span style="background-color: #fee2e2; color: #dc2626; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600;">High Priority</span>'
    elif priority == "low":
        return '<span style="background-color: #f3f4f6; color: #6b7280; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600;">Low Priority</span>'
    return ""


def get_sentiment_indicator(sentiment: Optional[str], emotion: Optional[str]) -> str:
    """Generate sentiment/emotion indicator."""
    if not sentiment and not emotion:
        return ""

    colors = {
        "positive": ("#dcfce7", "#16a34a"),
        "negative": ("#fee2e2", "#dc2626"),
        "neutral": ("#f3f4f6", "#6b7280"),
    }

    bg, text = colors.get(sentiment, ("#f3f4f6", "#6b7280"))

    label = emotion.capitalize() if emotion else sentiment.capitalize() if sentiment else ""
    if label:
        return f'<span style="background-color: {bg}; color: {text}; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 500;">{label}</span>'
    return ""


def get_category_badge(category: Optional[str]) -> str:
    """Generate category badge HTML."""
    if not category:
        return ""

    labels = {
        "sales_inquiry": "Sales Inquiry",
        "existing_order": "Existing Order",
        "new_inquiry": "New Inquiry",
        "complaint": "Complaint",
        "general": "General",
    }

    label = labels.get(category, category.replace("_", " ").title())
    return f'<span style="background-color: #e0e7ff; color: #4338ca; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 500;">{label}</span>'


def generate_email_html(data: VoicemailEmailData) -> str:
    """Generate the HTML email body for a voicemail notification."""

    # Format values
    caller = format_phone(data.from_number)
    destination = data.to_number_name or format_phone(data.to_number)
    duration = format_duration(data.duration)
    received = data.received_at.strftime("%d.%m.%Y um %H:%M Uhr")

    # Generate badges
    priority_badge = get_priority_badge(data.priority)
    sentiment_badge = get_sentiment_indicator(data.sentiment, data.emotion)
    category_badge = get_category_badge(data.category)

    badges_html = " ".join(filter(None, [priority_badge, sentiment_badge, category_badge]))
    if badges_html:
        badges_html = f'<div style="margin-bottom: 20px;">{badges_html}</div>'

    # Use corrected text if available, otherwise original transcription
    transcript = data.corrected_text or data.transcription_text or "No transcription available."

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>New Voicemail</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f9fafb; color: #111827;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f9fafb; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden;">

                    <!-- Header -->
                    <tr>
                        <td style="background-color: #1f2937; padding: 24px 32px;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td>
                                        <h1 style="margin: 0; color: #ffffff; font-size: 20px; font-weight: 600;">
                                            New Voicemail
                                        </h1>
                                    </td>
                                    <td align="right">
                                        <span style="color: #9ca3af; font-size: 14px;">{received}</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Call Info -->
                    <tr>
                        <td style="padding: 24px 32px; border-bottom: 1px solid #e5e7eb;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td width="50%" style="padding-right: 16px;">
                                        <div style="margin-bottom: 4px; font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em;">From</div>
                                        <div style="font-size: 18px; font-weight: 600; color: #111827;">{caller}</div>
                                    </td>
                                    <td width="25%">
                                        <div style="margin-bottom: 4px; font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em;">To</div>
                                        <div style="font-size: 16px; color: #374151;">{destination}</div>
                                    </td>
                                    <td width="25%" align="right">
                                        <div style="margin-bottom: 4px; font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em;">Duration</div>
                                        <div style="font-size: 16px; color: #374151;">{duration}</div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Badges -->
                    {"<tr><td style='padding: 20px 32px 0 32px;'>" + badges_html + "</td></tr>" if badges_html else ""}

                    <!-- Summary -->
                    <tr>
                        <td style="padding: 24px 32px;">
                            <div style="margin-bottom: 12px; font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em;">Summary</div>
                            <div style="font-size: 16px; line-height: 1.6; color: #374151; background-color: #f9fafb; padding: 16px; border-radius: 8px; border-left: 4px solid #3b82f6;">
                                {data.summary or "No summary available."}
                            </div>
                            {"<div style='margin-top: 12px; font-size: 14px; line-height: 1.6; color: #6b7280; font-style: italic;'><strong>English:</strong> " + data.summary_en + "</div>" if data.summary_en and data.summary_en != data.summary else ""}
                        </td>
                    </tr>

                    <!-- Listen Button -->
                    <tr>
                        <td style="padding: 0 32px 24px 32px;">
                            <a href="{data.audio_url}" style="display: inline-block; background-color: #3b82f6; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: 600; font-size: 14px;">
                                Listen to Voicemail
                            </a>
                        </td>
                    </tr>

                    <!-- Transcript -->
                    <tr>
                        <td style="padding: 24px 32px; background-color: #f9fafb; border-top: 1px solid #e5e7eb;">
                            <div style="margin-bottom: 12px; font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em;">Full Transcript</div>
                            <div style="font-size: 14px; line-height: 1.7; color: #4b5563; white-space: pre-wrap;">{transcript}</div>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 32px; background-color: #f3f4f6; border-top: 1px solid #e5e7eb;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td style="font-size: 12px; color: #9ca3af;">
                                        Phone App &middot; Voicemail #{data.id}
                                    </td>
                                    <td align="right" style="font-size: 12px; color: #9ca3af;">
                                        Transcribed automatically
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    return html


def generate_email_plain(data: VoicemailEmailData) -> str:
    """Generate plain text email body for clients that don't support HTML."""

    caller = format_phone(data.from_number)
    destination = data.to_number_name or format_phone(data.to_number)
    duration = format_duration(data.duration)
    received = data.received_at.strftime("%d.%m.%Y at %H:%M")
    transcript = data.corrected_text or data.transcription_text or "No transcription available."

    lines = []

    # High priority alert at top
    if data.priority == "high":
        lines.extend([
            "!!! HIGH PRIORITY !!!",
            "",
        ])

    # Header with key info
    lines.extend([
        "=" * 50,
        "  NEW VOICEMAIL",
        f"  From: {caller}",
        f"  To:   {destination}",
        f"  Date: {received}  ({duration})",
        "=" * 50,
        "",
    ])

    # Classification badges inline
    badges = []
    if data.category and data.category != "general":
        badges.append(data.category.replace('_', ' ').title())
    if data.emotion and data.emotion not in ("calm", "neutral"):
        badges.append(data.emotion.capitalize())
    if badges:
        lines.append(f"[{' | '.join(badges)}]")
        lines.append("")

    # Summary section - most important
    lines.extend([
        "SUMMARY",
        "-" * 50,
        "",
        data.summary or "No summary available.",
    ])

    # Add English translation if different from original
    if data.summary_en and data.summary_en != data.summary:
        lines.extend([
            "",
            f"(English: {data.summary_en})",
        ])

    lines.extend([
        "",
        "",
        "TRANSCRIPT",
        "-" * 50,
        "",
        transcript,
        "",
        "",
        "=" * 50,
        f"Listen: {data.audio_url}",
        f"Callback: {caller}",
        "=" * 50,
        "",
        f"Phone App | Voicemail #{data.id}",
    ])

    return "\n".join(lines)


class PostmarkEmailService:
    """Service for sending voicemail notification emails via Postmark."""

    def __init__(self, api_token: str, from_email: str, from_name: str = "Phone App"):
        self.api_token = api_token
        self.from_email = from_email
        self.from_name = from_name

    async def send(
        self,
        to_email: str,
        data: VoicemailEmailData,
        attach_audio: bool = False,
    ) -> Optional[str]:
        """Send a voicemail notification email via Postmark.

        Returns the Postmark MessageID on success, or None on failure.
        """

        caller = format_phone(data.from_number)
        duration = format_duration(data.duration)
        received = data.received_at.strftime("%d.%m.%Y %H:%M")

        # Build subject line with LLM-generated topic, phone, and date/time
        subject_topic = data.email_subject or "Voicemail"
        subject = f"{subject_topic} | {caller} | {received}"

        payload = {
            "From": f"{self.from_name} <{self.from_email}>",
            "To": to_email,
            "Subject": subject,
            "HtmlBody": generate_email_html(data),
            "TextBody": generate_email_plain(data),
            "MessageStream": "outbound",
        }

        # Optionally attach audio file
        if attach_audio and data.local_file_path:
            audio_path = Path(data.local_file_path)
            if audio_path.exists():
                with open(audio_path, "rb") as f:
                    audio_content = base64.b64encode(f.read()).decode("utf-8")
                    payload["Attachments"] = [{
                        "Name": f"voicemail_{data.id}.mp3",
                        "Content": audio_content,
                        "ContentType": "audio/mpeg",
                    }]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    POSTMARK_API_URL,
                    json=payload,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "X-Postmark-Server-Token": self.api_token,
                    },
                    timeout=30.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    message_id = result.get('MessageID')
                    logger.info(f"Email sent to {to_email} for voicemail #{data.id} (MessageID: {message_id})")
                    return message_id
                else:
                    logger.error(f"Postmark error: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return None


def voicemail_to_email_data(call, base_url: str) -> VoicemailEmailData:
    """Convert a Call model instance to VoicemailEmailData."""
    from app.services.access_token import get_public_url

    return VoicemailEmailData(
        id=call.id,
        from_number=call.from_number or "Unknown",
        to_number=call.to_number or "",
        to_number_name=call.to_number_name,
        duration=call.duration or 0,
        received_at=call.started_at or call.created_at,
        summary=call.summary or "",
        summary_en=call.summary_en,
        corrected_text=call.corrected_text or "",
        transcription_text=call.transcription_text or "",
        sentiment=call.sentiment,
        emotion=call.emotion,
        category=call.category,
        priority=call.priority,
        audio_url=get_public_url(call.id),  # Public player page with token
        email_subject=call.email_subject,
        local_file_path=call.local_file_path,
    )
