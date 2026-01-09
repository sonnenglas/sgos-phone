from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pathlib import Path
from typing import Optional

from app.database import get_db
from app.models import Voicemail
from app.schemas import VoicemailResponse

router = APIRouter(prefix="/voicemails", tags=["voicemails"])


@router.get("", response_model=list[VoicemailResponse])
def list_voicemails(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by transcription status"),
    search: Optional[str] = Query(None, description="Search in transcription text"),
    db: Session = Depends(get_db),
):
    """List all voicemails with pagination and filtering."""
    query = db.query(Voicemail)

    if status:
        query = query.filter(Voicemail.transcription_status == status)

    if search:
        query = query.filter(Voicemail.transcription_text.ilike(f"%{search}%"))

    voicemails = query.order_by(desc(Voicemail.received_at)).offset(skip).limit(limit).all()
    return voicemails


@router.get("/{voicemail_id}", response_model=VoicemailResponse)
def get_voicemail(voicemail_id: int, db: Session = Depends(get_db)):
    """Get a single voicemail by ID."""
    voicemail = db.query(Voicemail).filter(Voicemail.id == voicemail_id).first()
    if not voicemail:
        raise HTTPException(status_code=404, detail="Voicemail not found")
    return voicemail


@router.get("/{voicemail_id}/audio")
def get_voicemail_audio(voicemail_id: int, db: Session = Depends(get_db)):
    """Stream/download the voicemail audio file."""
    voicemail = db.query(Voicemail).filter(Voicemail.id == voicemail_id).first()
    if not voicemail:
        raise HTTPException(status_code=404, detail="Voicemail not found")

    if not voicemail.local_file_path:
        raise HTTPException(status_code=404, detail="Audio file not available")

    file_path = Path(voicemail.local_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        filename=f"voicemail_{voicemail_id}.mp3",
    )


@router.delete("/{voicemail_id}")
def delete_voicemail(voicemail_id: int, db: Session = Depends(get_db)):
    """Delete a voicemail and its audio file."""
    voicemail = db.query(Voicemail).filter(Voicemail.id == voicemail_id).first()
    if not voicemail:
        raise HTTPException(status_code=404, detail="Voicemail not found")

    # Delete the audio file if it exists
    if voicemail.local_file_path:
        file_path = Path(voicemail.local_file_path)
        if file_path.exists():
            file_path.unlink()

    db.delete(voicemail)
    db.commit()

    return {"deleted": voicemail_id}
