from sqlalchemy import Column, BigInteger, String, Integer, Boolean, Float, Text, DateTime, func
from app.database import Base


class Voicemail(Base):
    __tablename__ = "voicemails"

    id = Column(BigInteger, primary_key=True)  # Placetel voicemail ID
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

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
