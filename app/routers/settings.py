from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database import get_db
from app.models import Setting
from app.schemas import SettingResponse, SettingUpdate, SettingsResponse

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
def list_settings(db: Session = Depends(get_db)):
    """Get all settings as a dictionary."""
    settings = db.query(Setting).all()
    return SettingsResponse(
        settings={s.key: s.value for s in settings}
    )


@router.get("/{key}", response_model=SettingResponse)
def get_setting(key: str, db: Session = Depends(get_db)):
    """Get a single setting by key."""
    setting = db.query(Setting).filter(Setting.key == key).first()
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return setting


@router.put("/{key}", response_model=SettingResponse)
def update_setting(key: str, update: SettingUpdate, db: Session = Depends(get_db)):
    """Update a setting value."""
    setting = db.query(Setting).filter(Setting.key == key).first()
    if not setting:
        # Create new setting if it doesn't exist
        setting = Setting(key=key, value=update.value)
        db.add(setting)
    else:
        setting.value = update.value
        setting.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(setting)

    # If sync interval changed, reschedule the job
    if key == "sync_interval_minutes":
        from app.main import scheduler
        if scheduler:
            from app.services.scheduler import reschedule_sync_job
            reschedule_sync_job(scheduler, int(update.value))

    return setting


@router.post("/sync-now")
async def trigger_sync(db: Session = Depends(get_db)):
    """Manually trigger an immediate sync."""
    from app.services.scheduler import run_sync_job
    result = await run_sync_job()
    return {"status": "completed", "result": result}


@router.post("/reprocess/{voicemail_id}")
async def reprocess_voicemail(voicemail_id: int, db: Session = Depends(get_db)):
    """Reset a voicemail and reprocess it from scratch (transcribe, summarize, email)."""
    from app.models import Call
    from app.services.elevenlabs import ElevenLabsService
    from app.services.openrouter import OpenRouterService
    from app.services.email import PostmarkEmailService, voicemail_to_email_data
    from app.config import get_settings

    settings = get_settings()

    # Get voicemail
    call = db.query(Call).filter(Call.id == voicemail_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Voicemail not found")

    if call.status != "voicemail":
        raise HTTPException(status_code=400, detail="This call is not a voicemail")

    if not call.local_file_path:
        raise HTTPException(status_code=400, detail="No audio file available")

    result = {"voicemail_id": voicemail_id, "steps": []}

    # Step 1: Reset fields
    call.transcription_status = "pending"
    call.transcription_text = None
    call.transcription_language = None
    call.transcription_confidence = None
    call.transcription_model = None
    call.transcribed_at = None
    call.corrected_text = None
    call.summary = None
    call.summary_en = None
    call.summary_model = None
    call.summarized_at = None
    call.sentiment = None
    call.emotion = None
    call.category = None
    call.priority = "default"
    call.email_status = "pending"
    call.email_sent_at = None
    db.commit()
    result["steps"].append("reset")

    # Step 2: Transcribe
    try:
        call.transcription_status = "processing"
        db.commit()

        elevenlabs = ElevenLabsService()
        transcription = await elevenlabs.transcribe(call.local_file_path)

        call.transcription_text = transcription.text
        call.transcription_language = transcription.language
        call.transcription_confidence = transcription.confidence
        call.transcription_model = transcription.model
        call.transcription_status = "completed"
        call.transcribed_at = datetime.now(timezone.utc)
        db.commit()
        result["steps"].append("transcribed")
        result["transcription"] = transcription.text[:200] + "..." if len(transcription.text) > 200 else transcription.text
    except Exception as e:
        call.transcription_status = "failed"
        db.commit()
        result["steps"].append(f"transcription_failed: {str(e)}")
        return result

    # Step 3: Summarize
    try:
        openrouter = OpenRouterService()
        summary_result = await openrouter.process_transcript(
            transcript=call.transcription_text,
            language=call.transcription_language or "de",
        )

        call.corrected_text = summary_result.corrected_text
        call.summary = summary_result.summary
        call.summary_en = summary_result.summary_en
        call.summary_model = openrouter.model
        call.summarized_at = datetime.now(timezone.utc)
        call.sentiment = summary_result.sentiment
        call.emotion = summary_result.emotion
        call.category = summary_result.category
        call.priority = summary_result.priority
        db.commit()
        result["steps"].append("summarized")
        result["summary"] = summary_result.summary
    except Exception as e:
        result["steps"].append(f"summarization_failed: {str(e)}")
        return result

    # Step 4: Send email (if configured)
    notification_setting = db.query(Setting).filter(Setting.key == "notification_email").first()
    to_email = notification_setting.value if notification_setting else ""

    if to_email and settings.postmark_api_token and settings.email_from:
        try:
            email_service = PostmarkEmailService(
                api_token=settings.postmark_api_token,
                from_email=settings.email_from,
                from_name=settings.email_from_name,
            )
            email_data = voicemail_to_email_data(call, settings.base_url)
            success = await email_service.send(to_email=to_email, data=email_data)

            if success:
                call.email_status = "sent"
                call.email_sent_at = datetime.now(timezone.utc)
                db.commit()
                result["steps"].append("email_sent")
            else:
                call.email_status = "failed"
                db.commit()
                result["steps"].append("email_failed")
        except Exception as e:
            result["steps"].append(f"email_error: {str(e)}")
    else:
        result["steps"].append("email_skipped (not configured)")

    return result


@router.post("/email-cutoff-now")
async def set_email_cutoff_now(db: Session = Depends(get_db)):
    """Set email cutoff to now and mark all existing pending emails as skipped.

    This prevents old voicemails from being emailed when auto_email is enabled.
    Only voicemails received AFTER this cutoff will be emailed.
    """
    from app.models import Call

    now = datetime.now(timezone.utc)

    # Set the cutoff date
    cutoff_setting = db.query(Setting).filter(Setting.key == "email_only_after").first()
    if cutoff_setting:
        cutoff_setting.value = now.isoformat()
        cutoff_setting.updated_at = now
    else:
        db.add(Setting(key="email_only_after", value=now.isoformat()))

    # Mark all pending emails as skipped
    pending_count = db.query(Call).filter(
        Call.email_status == "pending"
    ).update({"email_status": "skipped"})

    db.commit()

    return {
        "cutoff_date": now.isoformat(),
        "skipped_count": pending_count,
        "message": f"Cutoff set to {now.isoformat()}. {pending_count} pending emails marked as skipped."
    }


@router.post("/send-email/{voicemail_id}")
async def send_email(voicemail_id: int, db: Session = Depends(get_db)):
    """Manually send email notification for a voicemail and mark as sent."""
    from app.models import Call
    from app.config import get_settings
    from app.services.email import PostmarkEmailService, voicemail_to_email_data

    settings = get_settings()

    # Check Postmark config
    if not settings.postmark_api_token:
        raise HTTPException(status_code=400, detail="POSTMARK_API_TOKEN not configured")
    if not settings.email_from:
        raise HTTPException(status_code=400, detail="EMAIL_FROM not configured")

    # Get notification email from settings
    notification_setting = db.query(Setting).filter(Setting.key == "notification_email").first()
    to_email = notification_setting.value if notification_setting else ""

    if not to_email:
        raise HTTPException(status_code=400, detail="notification_email not set in settings")

    # Get voicemail
    call = db.query(Call).filter(Call.id == voicemail_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Voicemail not found")

    if call.status != "voicemail":
        raise HTTPException(status_code=400, detail="This call is not a voicemail")

    if not call.summary:
        raise HTTPException(status_code=400, detail="Voicemail not summarized yet")

    # Send email
    email_service = PostmarkEmailService(
        api_token=settings.postmark_api_token,
        from_email=settings.email_from,
        from_name=settings.email_from_name,
    )

    email_data = voicemail_to_email_data(call, settings.base_url)
    success = await email_service.send(to_email=to_email, data=email_data)

    if success:
        call.email_status = "sent"
        call.email_sent_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "sent", "to": to_email, "voicemail_id": voicemail_id}
    else:
        call.email_status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to send email - check logs")
