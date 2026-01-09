from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import time

from app.database import get_db
from app.models import Voicemail
from app.schemas import SyncResponse, TranscribeResponse, SummarizeResponse
from app.services.placetel import PlacetelService
from app.services.elevenlabs import ElevenLabsService
from app.services.openrouter import OpenRouterService

router = APIRouter(tags=["sync"])

# Voicemails shorter than this are considered noise (hangups, rings, etc.)
MIN_DURATION_SECONDS = 2


@router.post("/sync", response_model=SyncResponse)
async def sync_voicemails(
    days: int = Query(30, ge=1, le=365, description="Number of days to sync"),
    db: Session = Depends(get_db),
):
    """Fetch voicemails from Placetel and store them in the database."""
    placetel = PlacetelService()

    voicemails = await placetel.fetch_voicemails(days=days)

    new_count = 0
    updated_count = 0
    downloaded_count = 0

    for vm_data in voicemails:
        vm_id = vm_data["id"]
        existing = db.query(Voicemail).filter(Voicemail.id == vm_id).first()

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

            # Create new record
            voicemail = Voicemail(
                id=vm_id,
                from_number=vm_data.get("from_number"),
                to_number=to_number.get("number") if isinstance(to_number, dict) else to_number,
                to_number_name=to_number.get("name") if isinstance(to_number, dict) else None,
                duration=duration,
                received_at=datetime.fromisoformat(vm_data["received_at"].replace("Z", "+00:00"))
                if vm_data.get("received_at")
                else None,
                file_url=vm_data.get("file_url"),
                unread=vm_data.get("unread", True),
                transcription_status=initial_status,
                transcription_text=initial_text,
            )
            db.add(voicemail)
            new_count += 1

            # Only download if worth processing
            if duration >= MIN_DURATION_SECONDS:
                try:
                    local_path = await placetel.download_voicemail(vm_id, vm_data["file_url"])
                    voicemail.local_file_path = local_path
                    downloaded_count += 1
                except Exception as e:
                    print(f"Failed to download voicemail {vm_id}: {e}")

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
    voicemail = db.query(Voicemail).filter(Voicemail.id == voicemail_id).first()
    if not voicemail:
        return {"error": "Voicemail not found"}

    if voicemail.duration is not None and voicemail.duration < MIN_DURATION_SECONDS:
        return {"error": f"Voicemail too short ({voicemail.duration}s < {MIN_DURATION_SECONDS}s)"}

    if not voicemail.local_file_path:
        return {"error": "Audio file not available"}

    elevenlabs = ElevenLabsService()

    try:
        voicemail.transcription_status = "processing"
        db.commit()

        start_time = time.time()
        result = await elevenlabs.transcribe(voicemail.local_file_path)
        elapsed = time.time() - start_time

        voicemail.transcription_text = result.text
        voicemail.transcription_language = result.language
        voicemail.transcription_confidence = result.confidence
        voicemail.transcription_status = "completed"
        voicemail.transcribed_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "id": voicemail_id,
            "status": "completed",
            "text": result.text,
            "language": result.language,
            "confidence": result.confidence,
            "duration_seconds": voicemail.duration,
            "processing_time_seconds": round(elapsed, 2),
        }
    except Exception as e:
        voicemail.transcription_status = "failed"
        db.commit()
        return {"id": voicemail_id, "status": "failed", "error": str(e)}


@router.post("/transcribe-pending", response_model=TranscribeResponse)
async def transcribe_pending(
    limit: int = Query(10, ge=1, le=100, description="Maximum number to transcribe"),
    db: Session = Depends(get_db),
):
    """Transcribe all pending voicemails (skips those < 2 seconds)."""
    pending = (
        db.query(Voicemail)
        .filter(Voicemail.transcription_status == "pending")
        .filter(Voicemail.local_file_path.isnot(None))
        .filter(Voicemail.duration >= MIN_DURATION_SECONDS)
        .limit(limit)
        .all()
    )

    elevenlabs = ElevenLabsService()

    transcribed = 0
    failed = 0
    skipped = 0
    total_audio_duration = 0
    total_processing_time = 0

    for voicemail in pending:
        try:
            voicemail.transcription_status = "processing"
            db.commit()

            start_time = time.time()
            result = await elevenlabs.transcribe(voicemail.local_file_path)
            elapsed = time.time() - start_time

            voicemail.transcription_text = result.text
            voicemail.transcription_language = result.language
            voicemail.transcription_confidence = result.confidence
            voicemail.transcription_status = "completed"
            voicemail.transcribed_at = datetime.now(timezone.utc)
            transcribed += 1

            total_audio_duration += voicemail.duration or 0
            total_processing_time += elapsed

            print(f"Transcribed {voicemail.id}: {voicemail.duration}s audio in {elapsed:.2f}s")

        except Exception as e:
            print(f"Failed to transcribe voicemail {voicemail.id}: {e}")
            voicemail.transcription_status = "failed"
            failed += 1

    db.commit()

    if transcribed > 0:
        print(f"Total: {total_audio_duration}s audio transcribed in {total_processing_time:.2f}s "
              f"({total_audio_duration/total_processing_time:.1f}x realtime)")

    return TranscribeResponse(transcribed=transcribed, failed=failed, skipped=skipped)


@router.post("/voicemails/{voicemail_id}/summarize")
async def summarize_voicemail(voicemail_id: int, db: Session = Depends(get_db)):
    """Summarize and correct a single voicemail transcript using LLM."""
    voicemail = db.query(Voicemail).filter(Voicemail.id == voicemail_id).first()
    if not voicemail:
        return {"error": "Voicemail not found"}

    if not voicemail.transcription_text:
        return {"error": "No transcription available. Transcribe first."}

    if voicemail.transcription_status == "skipped":
        return {"error": "This voicemail was skipped (too short)"}

    # Check for placeholder texts
    skip_texts = ["[No audio]", "[Too short]", "[No audio content]", "[Audio too short to transcribe]"]
    if voicemail.transcription_text in skip_texts:
        return {"error": "No meaningful transcription to summarize"}

    openrouter = OpenRouterService()

    try:
        result = await openrouter.process_transcript(
            transcript=voicemail.transcription_text,
            language=voicemail.transcription_language or "de",
        )

        voicemail.corrected_text = result.corrected_text
        voicemail.summary = result.summary
        voicemail.summary_model = openrouter.model
        voicemail.summarized_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "id": voicemail_id,
            "status": "completed",
            "original_text": voicemail.transcription_text,
            "corrected_text": result.corrected_text,
            "summary": result.summary,
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
        db.query(Voicemail)
        .filter(Voicemail.transcription_status == "completed")
        .filter(Voicemail.transcription_text.isnot(None))
        .filter(Voicemail.summary.is_(None))
        .filter(Voicemail.transcription_text.notin_(skip_texts))
        .filter(Voicemail.duration >= MIN_DURATION_SECONDS)
        .limit(limit)
        .all()
    )

    openrouter = OpenRouterService()

    summarized = 0
    failed = 0
    skipped = 0

    for voicemail in pending:
        # Skip very short transcripts (just noise detected)
        if len(voicemail.transcription_text.strip()) < 20:
            skipped += 1
            voicemail.summary = "[No meaningful content]"
            voicemail.summarized_at = datetime.now(timezone.utc)
            continue

        try:
            result = await openrouter.process_transcript(
                transcript=voicemail.transcription_text,
                language=voicemail.transcription_language or "de",
            )

            voicemail.corrected_text = result.corrected_text
            voicemail.summary = result.summary
            voicemail.summary_model = openrouter.model
            voicemail.summarized_at = datetime.now(timezone.utc)
            summarized += 1
        except Exception as e:
            print(f"Failed to summarize voicemail {voicemail.id}: {e}")
            failed += 1

    db.commit()

    return SummarizeResponse(summarized=summarized, failed=failed, skipped=skipped)
