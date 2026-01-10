from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import time

from app.database import get_db
from app.models import Call, Setting
from app.schemas import SyncResponse, TranscribeResponse, SummarizeResponse
from app.services.placetel import PlacetelService
from app.services.elevenlabs import ElevenLabsService
from app.services.openrouter import OpenRouterService

router = APIRouter(tags=["sync"])

# Voicemails shorter than this are considered noise (hangups, rings, etc.)
MIN_DURATION_SECONDS = 2


@router.post("/sync", response_model=SyncResponse)
async def sync_voicemails(
    days: int = Query(7, ge=1, le=365, description="Number of days to sync"),
    db: Session = Depends(get_db),
):
    """Fetch voicemails from Placetel and store them in the database."""
    placetel = PlacetelService()

    voicemails = await placetel.fetch_voicemails(days=days)

    new_count = 0
    updated_count = 0
    downloaded_count = 0

    for vm_data in voicemails:
        external_id = str(vm_data["id"])
        existing = db.query(Call).filter(
            Call.external_id == external_id,
            Call.provider == "placetel"
        ).first()

        to_number = vm_data.get("to_number", {})
        duration = vm_data.get("duration") or 0

        if existing:
            # Update existing record if file_url changed (it expires)
            if existing.file_url != vm_data.get("file_url"):
                existing.file_url = vm_data.get("file_url")
                updated_count += 1
        else:
            # Determine initial status based on duration
            if duration < MIN_DURATION_SECONDS:
                initial_status = "skipped"
                initial_text = "[Too short]" if duration > 0 else "[No audio]"
            else:
                initial_status = "pending"
                initial_text = None

            # Parse timestamp
            started_at = None
            if vm_data.get("received_at"):
                started_at = datetime.fromisoformat(vm_data["received_at"].replace("Z", "+00:00"))

            # Create new record
            call = Call(
                external_id=external_id,
                provider="placetel",
                direction="in",
                status="voicemail",
                from_number=vm_data.get("from_number"),
                to_number=to_number.get("number") if isinstance(to_number, dict) else to_number,
                to_number_name=to_number.get("name") if isinstance(to_number, dict) else None,
                duration=duration,
                started_at=started_at,
                file_url=vm_data.get("file_url"),
                unread=vm_data.get("unread", True),
                transcription_status=initial_status,
                transcription_text=initial_text,
                email_status="pending" if initial_status == "pending" else "skipped",
            )
            db.add(call)
            new_count += 1

            # Only download if worth processing
            if duration >= MIN_DURATION_SECONDS:
                try:
                    local_path = await placetel.download_voicemail(external_id, vm_data["file_url"])
                    call.local_file_path = local_path
                    downloaded_count += 1
                except Exception as e:
                    print(f"Failed to download voicemail {external_id}: {e}")

    # Update last_sync_at
    last_sync = db.query(Setting).filter(Setting.key == "last_sync_at").first()
    now = datetime.now(timezone.utc).isoformat()
    if last_sync:
        last_sync.value = now
        last_sync.updated_at = datetime.now(timezone.utc)
    else:
        db.add(Setting(key="last_sync_at", value=now))

    db.commit()

    return SyncResponse(
        synced=len(voicemails),
        new=new_count,
        updated=updated_count,
        downloaded=downloaded_count,
    )


@router.post("/voicemails/{voicemail_id}/transcribe")
async def transcribe_voicemail(voicemail_id: int, db: Session = Depends(get_db)):
    """Transcribe a single voicemail."""
    call = db.query(Call).filter(Call.id == voicemail_id).first()
    if not call:
        return {"error": "Voicemail not found"}

    if call.status != "voicemail":
        return {"error": "This call is not a voicemail"}

    if call.duration is not None and call.duration < MIN_DURATION_SECONDS:
        return {"error": f"Voicemail too short ({call.duration}s < {MIN_DURATION_SECONDS}s)"}

    if not call.local_file_path:
        return {"error": "Audio file not available"}

    elevenlabs = ElevenLabsService()

    try:
        call.transcription_status = "processing"
        db.commit()

        start_time = time.time()
        result = await elevenlabs.transcribe(call.local_file_path)
        elapsed = time.time() - start_time

        call.transcription_text = result.text
        call.transcription_language = result.language
        call.transcription_confidence = result.confidence
        call.transcription_model = result.model
        call.transcription_status = "completed"
        call.transcribed_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "id": voicemail_id,
            "status": "completed",
            "text": result.text,
            "language": result.language,
            "confidence": result.confidence,
            "duration_seconds": call.duration,
            "processing_time_seconds": round(elapsed, 2),
        }
    except Exception as e:
        call.transcription_status = "failed"
        db.commit()
        return {"id": voicemail_id, "status": "failed", "error": str(e)}


@router.post("/transcribe-pending", response_model=TranscribeResponse)
async def transcribe_pending(
    limit: int = Query(10, ge=1, le=100, description="Maximum number to transcribe"),
    db: Session = Depends(get_db),
):
    """Transcribe all pending voicemails (skips those < 2 seconds)."""
    pending = (
        db.query(Call)
        .filter(Call.status == "voicemail")
        .filter(Call.transcription_status == "pending")
        .filter(Call.local_file_path.isnot(None))
        .filter(Call.duration >= MIN_DURATION_SECONDS)
        .limit(limit)
        .all()
    )

    elevenlabs = ElevenLabsService()

    transcribed = 0
    failed = 0
    skipped = 0
    total_audio_duration = 0
    total_processing_time = 0

    for call in pending:
        try:
            call.transcription_status = "processing"
            db.commit()

            start_time = time.time()
            result = await elevenlabs.transcribe(call.local_file_path)
            elapsed = time.time() - start_time

            call.transcription_text = result.text
            call.transcription_language = result.language
            call.transcription_confidence = result.confidence
            call.transcription_model = result.model
            call.transcription_status = "completed"
            call.transcribed_at = datetime.now(timezone.utc)
            transcribed += 1

            total_audio_duration += call.duration or 0
            total_processing_time += elapsed

            print(f"Transcribed {call.id}: {call.duration}s audio in {elapsed:.2f}s")

        except Exception as e:
            print(f"Failed to transcribe voicemail {call.id}: {e}")
            call.transcription_status = "failed"
            failed += 1

    db.commit()

    if transcribed > 0:
        print(f"Total: {total_audio_duration}s audio transcribed in {total_processing_time:.2f}s "
              f"({total_audio_duration/total_processing_time:.1f}x realtime)")

    return TranscribeResponse(transcribed=transcribed, failed=failed, skipped=skipped)


@router.post("/voicemails/{voicemail_id}/summarize")
async def summarize_voicemail(voicemail_id: int, db: Session = Depends(get_db)):
    """Summarize and correct a single voicemail transcript using LLM."""
    call = db.query(Call).filter(Call.id == voicemail_id).first()
    if not call:
        return {"error": "Voicemail not found"}

    if not call.transcription_text:
        return {"error": "No transcription available. Transcribe first."}

    if call.transcription_status == "skipped":
        return {"error": "This voicemail was skipped (too short)"}

    # Check for placeholder texts
    skip_texts = ["[No audio]", "[Too short]", "[No audio content]", "[Audio too short to transcribe]"]
    if call.transcription_text in skip_texts:
        return {"error": "No meaningful transcription to summarize"}

    openrouter = OpenRouterService()

    try:
        result = await openrouter.process_transcript(
            transcript=call.transcription_text,
            language=call.transcription_language or "de",
        )

        call.corrected_text = result.corrected_text
        call.summary = result.summary
        call.summary_en = result.summary_en
        call.summary_model = openrouter.model
        call.summarized_at = datetime.now(timezone.utc)
        call.sentiment = result.sentiment
        call.emotion = result.emotion
        call.category = result.category
        call.priority = result.priority
        db.commit()

        return {
            "id": voicemail_id,
            "status": "completed",
            "original_text": call.transcription_text,
            "corrected_text": result.corrected_text,
            "summary": result.summary,
            "sentiment": result.sentiment,
            "emotion": result.emotion,
            "category": result.category,
            "priority": result.priority,
            "model": openrouter.model,
        }
    except Exception as e:
        return {"id": voicemail_id, "status": "failed", "error": str(e)}


@router.post("/summarize-pending", response_model=SummarizeResponse)
async def summarize_pending(
    limit: int = Query(10, ge=1, le=100, description="Maximum number to summarize"),
    db: Session = Depends(get_db),
):
    """Summarize all transcribed voicemails that haven't been summarized yet."""
    skip_texts = ["[No audio]", "[Too short]", "[No audio content]", "[Audio too short to transcribe]"]

    pending = (
        db.query(Call)
        .filter(Call.status == "voicemail")
        .filter(Call.transcription_status == "completed")
        .filter(Call.transcription_text.isnot(None))
        .filter(Call.summary.is_(None))
        .filter(Call.transcription_text.notin_(skip_texts))
        .filter(Call.duration >= MIN_DURATION_SECONDS)
        .limit(limit)
        .all()
    )

    openrouter = OpenRouterService()

    summarized = 0
    failed = 0
    skipped = 0

    for call in pending:
        # Skip very short transcripts (just noise detected)
        if len(call.transcription_text.strip()) < 20:
            skipped += 1
            call.summary = "[No meaningful content]"
            call.summarized_at = datetime.now(timezone.utc)
            continue

        try:
            result = await openrouter.process_transcript(
                transcript=call.transcription_text,
                language=call.transcription_language or "de",
            )

            call.corrected_text = result.corrected_text
            call.summary = result.summary
            call.summary_en = result.summary_en
            call.summary_model = openrouter.model
            call.summarized_at = datetime.now(timezone.utc)
            call.sentiment = result.sentiment
            call.emotion = result.emotion
            call.category = result.category
            call.priority = result.priority
            summarized += 1
        except Exception as e:
            print(f"Failed to summarize voicemail {call.id}: {e}")
            failed += 1

    db.commit()

    return SummarizeResponse(summarized=summarized, failed=failed, skipped=skipped)
