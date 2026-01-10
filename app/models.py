from sqlalchemy import Column, String, Integer, Boolean, Float, Text, DateTime, func, UniqueConstraint
from app.database import Base


class Setting(Base):
    """Key-value settings store for app configuration."""
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Voicemail(Base):
    __tablename__ = "voicemails"
    __table_args__ = (
        UniqueConstraint('provider', 'external_id', name='uq_provider_external_id'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)  # Internal ID
    external_id = Column(String(100), nullable=False)  # Provider's voicemail ID
    provider = Column(String(50), nullable=False, default="placetel")  # Voicemail provider
    from_number = Column(String(50))
    to_number = Column(String(50))
    to_number_name = Column(String(255))
    duration = Column(Integer)  # seconds
    received_at = Column(DateTime(timezone=True))
    file_url = Column(Text)  # Original Placetel URL (expires)
    local_file_path = Column(String(500))  # Local storage path
    unread = Column(Boolean, default=True)

    # Transcription
    transcription_status = Column(String(20), default="pending")  # pending, processing, completed, failed
    transcription_text = Column(Text)
    transcription_language = Column(String(10))
    transcription_confidence = Column(Float)
    transcribed_at = Column(DateTime(timezone=True))

    # LLM Processing
    corrected_text = Column(Text)  # LLM-corrected transcript
    summary = Column(Text)  # Concise summary for support agents
    summary_model = Column(String(100))
    summarized_at = Column(DateTime(timezone=True))

    # AI Classification
    sentiment = Column(String(20))  # positive, negative, neutral
    emotion = Column(String(20))  # angry, frustrated, happy, confused, calm, urgent
    category = Column(String(30))  # sales_inquiry, existing_order, new_inquiry, complaint, general
    is_urgent = Column(Boolean, default=False)

    # Email/Helpdesk
    email_status = Column(String(20), default="pending")  # pending, sent, failed, skipped
    email_sent_at = Column(DateTime(timezone=True))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
