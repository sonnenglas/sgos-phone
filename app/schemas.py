from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class VoicemailBase(BaseModel):
    id: int
    external_id: str
    provider: str = "placetel"
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    to_number_name: Optional[str] = None
    duration: Optional[int] = None
    received_at: Optional[datetime] = None
    unread: bool = True


class VoicemailResponse(VoicemailBase):
    local_file_path: Optional[str] = None
    transcription_status: str = "pending"
    transcription_text: Optional[str] = None
    transcription_language: Optional[str] = None
    transcription_confidence: Optional[float] = None
    transcribed_at: Optional[datetime] = None
    corrected_text: Optional[str] = None
    summary: Optional[str] = None
    summary_model: Optional[str] = None
    summarized_at: Optional[datetime] = None
    sentiment: Optional[str] = None
    emotion: Optional[str] = None
    category: Optional[str] = None
    is_urgent: bool = False
    email_status: str = "pending"
    email_sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


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
    voicemails_count: int
    scheduler: str
    last_sync_at: Optional[str] = None
