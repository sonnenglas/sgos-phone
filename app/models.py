from sqlalchemy import Column, String, Integer, Boolean, Float, Text, DateTime, func, UniqueConstraint
from app.database import Base


class Setting(Base):
    """Key-value settings store for app configuration."""
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Call(Base):
    """
    All phone calls - incoming, outgoing, answered, missed, voicemail.

    Voicemail-specific fields (transcription, summary, etc.) are nullable
    and only populated for calls with status='voicemail'.
    """
    __tablename__ = "calls"
    __table_args__ = (
        UniqueConstraint('provider', 'external_id', name='uq_provider_external_id'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=False, default="placetel")

    # Call basics
    direction = Column(String(10), default="in")  # in, out
    status = Column(String(20), default="voicemail")  # answered, missed, voicemail, busy
    from_number = Column(String(50))
    from_name = Column(String(255))  # Caller name if known
    to_number = Column(String(50))
    to_number_name = Column(String(255))  # Destination name (e.g., "Support")
    duration = Column(Integer)  # Total duration in seconds

    # Timing
    started_at = Column(DateTime(timezone=True))  # When call started ringing
    answered_at = Column(DateTime(timezone=True))  # When call was answered (null if missed/voicemail)
    ended_at = Column(DateTime(timezone=True))  # When call ended

    # Voicemail audio
    file_url = Column(Text)  # Original provider URL (may expire)
    local_file_path = Column(String(500))  # Local storage path
    unread = Column(Boolean, default=True)

    # Transcription (voicemail only)
    transcription_status = Column(String(20), default="pending")  # pending, processing, completed, failed, skipped
    transcription_text = Column(Text)
    transcription_language = Column(String(10))
    transcription_confidence = Column(Float)
    transcription_model = Column(String(100))  # Model used for transcription
    transcribed_at = Column(DateTime(timezone=True))

    # AI Processing (voicemail only)
    corrected_text = Column(Text)
    summary = Column(Text)  # Summary in original language
    summary_en = Column(Text)  # English translation of summary
    summary_model = Column(String(100))
    summarized_at = Column(DateTime(timezone=True))

    # AI Classification (voicemail only)
    sentiment = Column(String(20))  # positive, negative, neutral
    emotion = Column(String(20))  # angry, frustrated, happy, confused, calm, urgent
    category = Column(String(30))  # sales_inquiry, existing_order, new_inquiry, complaint, general
    priority = Column(String(10), default="default")  # low, default, high

    # Helpdesk forwarding (voicemail only)
    email_status = Column(String(20), default="pending")  # pending, sent, failed, skipped
    email_sent_at = Column(DateTime(timezone=True))
    email_subject = Column(String(255))  # LLM-generated email subject line
    email_message_id = Column(String(100))  # Postmark MessageID for delivery tracking

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# Alias for backwards compatibility during transition
Voicemail = Call
