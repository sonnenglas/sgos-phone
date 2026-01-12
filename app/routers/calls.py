from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pathlib import Path
from typing import Optional, Literal
from datetime import datetime, timezone

from app.database import get_db
from app.models import Call
from app.schemas import CallResponse, NumbersResponse, PhoneNumber
from app.services.placetel import PlacetelService
from app.services.email import generate_email_html, generate_email_plain, voicemail_to_email_data
from app.services.access_token import get_public_url
from app.config import get_settings

router = APIRouter(tags=["calls"])


def call_to_response(call: Call) -> dict:
    """Convert a Call model to response dict with listen_url."""
    data = {
        "id": call.id,
        "external_id": call.external_id,
        "provider": call.provider,
        "direction": call.direction,
        "status": call.status,
        "from_number": call.from_number,
        "from_name": call.from_name,
        "to_number": call.to_number,
        "to_number_name": call.to_number_name,
        "duration": call.duration,
        "started_at": call.started_at,
        "answered_at": call.answered_at,
        "ended_at": call.ended_at,
        "local_file_path": call.local_file_path,
        "unread": call.unread,
        "transcription_status": call.transcription_status,
        "transcription_text": call.transcription_text,
        "transcription_language": call.transcription_language,
        "transcription_confidence": call.transcription_confidence,
        "transcription_model": call.transcription_model,
        "transcribed_at": call.transcribed_at,
        "corrected_text": call.corrected_text,
        "summary": call.summary,
        "summary_en": call.summary_en,
        "summary_model": call.summary_model,
        "summarized_at": call.summarized_at,
        "sentiment": call.sentiment,
        "emotion": call.emotion,
        "category": call.category,
        "priority": call.priority,
        "email_status": call.email_status,
        "email_sent_at": call.email_sent_at,
        "created_at": call.created_at,
        "updated_at": call.updated_at,
        "listen_url": get_public_url(call.id) if call.status == "voicemail" else None,
    }
    return data


@router.get("/calls")
def list_calls(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    direction: Optional[Literal["in", "out"]] = Query(None, description="Filter by direction"),
    status: Optional[str] = Query(None, description="Filter by status (answered, missed, voicemail, busy)"),
    search: Optional[str] = Query(None, description="Search in transcription/summary"),
    db: Session = Depends(get_db),
):
    """List all calls with pagination and filtering."""
    query = db.query(Call)

    if direction:
        query = query.filter(Call.direction == direction)

    if status:
        query = query.filter(Call.status == status)

    if search:
        query = query.filter(
            (Call.transcription_text.ilike(f"%{search}%")) |
            (Call.summary.ilike(f"%{search}%")) |
            (Call.from_number.ilike(f"%{search}%"))
        )

    calls = query.order_by(desc(Call.started_at)).offset(skip).limit(limit).all()
    return [call_to_response(c) for c in calls]


@router.get("/calls/{call_id}")
def get_call(call_id: int, db: Session = Depends(get_db)):
    """Get a single call by ID."""
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call_to_response(call)


@router.get("/calls/{call_id}/audio")
def get_call_audio(call_id: int, db: Session = Depends(get_db)):
    """Stream/download the voicemail audio file."""
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    if call.status != "voicemail":
        raise HTTPException(status_code=400, detail="This call has no voicemail")

    if not call.local_file_path:
        raise HTTPException(status_code=404, detail="Audio file not available")

    file_path = Path(call.local_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        filename=f"voicemail_{call_id}.mp3",
    )


@router.delete("/calls/{call_id}")
def delete_call(call_id: int, db: Session = Depends(get_db)):
    """Delete a call and its audio file (if voicemail)."""
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    # Delete the audio file if it exists
    if call.local_file_path:
        file_path = Path(call.local_file_path)
        if file_path.exists():
            file_path.unlink()

    db.delete(call)
    db.commit()

    return {"deleted": call_id}


# Backwards compatibility: /voicemails endpoints
@router.get("/voicemails")
def list_voicemails(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    transcription_status: Optional[str] = Query(None, description="Filter by transcription status"),
    search: Optional[str] = Query(None, description="Search in transcription/summary"),
    db: Session = Depends(get_db),
):
    """List voicemails only (calls with status='voicemail')."""
    query = db.query(Call).filter(Call.status == "voicemail")

    if transcription_status:
        query = query.filter(Call.transcription_status == transcription_status)

    if search:
        query = query.filter(
            (Call.transcription_text.ilike(f"%{search}%")) |
            (Call.summary.ilike(f"%{search}%")) |
            (Call.from_number.ilike(f"%{search}%"))
        )

    voicemails = query.order_by(desc(Call.started_at)).offset(skip).limit(limit).all()
    return [call_to_response(v) for v in voicemails]


@router.get("/voicemails/{voicemail_id}")
def get_voicemail(voicemail_id: int, db: Session = Depends(get_db)):
    """Get a single voicemail by ID."""
    return get_call(voicemail_id, db)


@router.get("/voicemails/{voicemail_id}/audio")
def get_voicemail_audio(voicemail_id: int, db: Session = Depends(get_db)):
    """Stream/download the voicemail audio file."""
    return get_call_audio(voicemail_id, db)


@router.delete("/voicemails/{voicemail_id}")
def delete_voicemail(voicemail_id: int, db: Session = Depends(get_db)):
    """Delete a voicemail."""
    return delete_call(voicemail_id, db)


@router.get("/voicemails/{voicemail_id}/email-preview", response_class=HTMLResponse)
def preview_voicemail_email(voicemail_id: int, db: Session = Depends(get_db)):
    """Preview the HTML email that would be sent for this voicemail."""
    call = db.query(Call).filter(Call.id == voicemail_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Voicemail not found")

    if call.status != "voicemail":
        raise HTTPException(status_code=400, detail="This call is not a voicemail")

    settings = get_settings()
    email_data = voicemail_to_email_data(call, settings.base_url)
    html = generate_email_html(email_data)

    return HTMLResponse(content=html)


@router.get("/voicemails/{voicemail_id}/email-preview-text", response_class=PlainTextResponse)
def preview_voicemail_email_text(voicemail_id: int, db: Session = Depends(get_db)):
    """Preview the plain text email that would be sent for this voicemail."""
    call = db.query(Call).filter(Call.id == voicemail_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Voicemail not found")

    if call.status != "voicemail":
        raise HTTPException(status_code=400, detail="This call is not a voicemail")

    settings = get_settings()
    email_data = voicemail_to_email_data(call, settings.base_url)
    text = generate_email_plain(email_data)

    return PlainTextResponse(content=text)


@router.patch("/voicemails/{voicemail_id}/read")
def mark_voicemail_read(voicemail_id: int, db: Session = Depends(get_db)):
    """Mark a voicemail as read."""
    call = db.query(Call).filter(Call.id == voicemail_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Voicemail not found")

    call.unread = False
    db.commit()

    return {"id": voicemail_id, "unread": False}


@router.get("/voicemails/{voicemail_id}/listen-url")
def get_listen_url(voicemail_id: int, db: Session = Depends(get_db)):
    """Get the public listen URL with access token for a voicemail."""
    from app.services.access_token import get_public_url

    call = db.query(Call).filter(Call.id == voicemail_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Voicemail not found")

    return {"url": get_public_url(voicemail_id)}


# Simple in-memory cache for numbers
_numbers_cache: dict = {"numbers": [], "cached_at": None}


@router.get("/numbers", response_model=NumbersResponse)
async def list_numbers(refresh: bool = Query(False, description="Force refresh from API")):
    """List phone numbers from Placetel (cached)."""
    global _numbers_cache

    # Return cached if available and not forcing refresh (cache for 1 hour)
    if not refresh and _numbers_cache["cached_at"]:
        cache_age = (datetime.now(timezone.utc) - _numbers_cache["cached_at"]).total_seconds()
        if cache_age < 3600:  # 1 hour
            return NumbersResponse(
                numbers=_numbers_cache["numbers"],
                cached_at=_numbers_cache["cached_at"],
            )

    # Fetch from API
    placetel = PlacetelService()
    raw_numbers = await placetel.fetch_numbers()

    numbers = [
        PhoneNumber(
            id=str(n.get("id", "")),
            number=n.get("number", ""),
            name=n.get("name"),
            type=n.get("type"),
        )
        for n in raw_numbers
    ]

    # Update cache
    _numbers_cache = {
        "numbers": numbers,
        "cached_at": datetime.now(timezone.utc),
    }

    return NumbersResponse(numbers=numbers, cached_at=_numbers_cache["cached_at"])
