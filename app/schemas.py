from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal


class CallBase(BaseModel):
    id: int
    external_id: str
    provider: str = "placetel"

    # Call basics
    direction: Literal["in", "out"] = "in"
    status: Literal["answered", "missed", "voicemail", "busy"] = "voicemail"
    from_number: Optional[str] = None
    from_name: Optional[str] = None
    to_number: Optional[str] = None
    to_number_name: Optional[str] = None
    duration: Optional[int] = None

    # Timing
    started_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class CallResponse(CallBase):
    # Audio (voicemail)
    local_file_path: Optional[str] = None
    unread: bool = True

    # Transcription
    transcription_status: str = "pending"
    transcription_text: Optional[str] = None
    transcription_language: Optional[str] = None
    transcription_confidence: Optional[float] = None
    transcription_model: Optional[str] = None
    transcribed_at: Optional[datetime] = None

    # AI Processing
    corrected_text: Optional[str] = None
    summary: Optional[str] = None
    summary_model: Optional[str] = None
    summarized_at: Optional[datetime] = None

    # Classification
    sentiment: Optional[str] = None
    emotion: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[Literal["low", "default", "high"]] = "default"

    # Helpdesk
    email_status: str = "pending"
    email_sent_at: Optional[datetime] = None

    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Backwards compatibility aliases
VoicemailBase = CallBase
VoicemailResponse = CallResponse


# Settings schemas
class SettingResponse(BaseModel):
    key: str
    value: str
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SettingUpdate(BaseModel):
    value: str


class SettingsResponse(BaseModel):
    settings: dict[str, str]


# Sync responses
class SyncResponse(BaseModel):
    synced: int
    new: int
    updated: int
    downloaded: int


class TranscribeResponse(BaseModel):
    transcribed: int
    failed: int
    skipped: int


class SummarizeResponse(BaseModel):
    summarized: int
    failed: int
    skipped: int


class HealthResponse(BaseModel):
    status: str
    database: str
    calls_count: int
    voicemails_count: int  # Subset where status='voicemail'
    scheduler: str
    last_sync_at: Optional[str] = None


# Numbers (cached from Placetel)
class PhoneNumber(BaseModel):
    id: str
    number: str
    name: Optional[str] = None
    type: Optional[str] = None  # geographic, mobile, etc.


class NumbersResponse(BaseModel):
    numbers: list[PhoneNumber]
    cached_at: Optional[datetime] = None
