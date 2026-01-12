"""
Placetel Webhook Handler

Receives notifications when calls end (including voicemails).
Documentation: https://github.com/Placetel/call-control-notify-api

Setup in Placetel:
1. Go to Settings → External APIs
2. Set Notification URL to: https://your-domain/webhook/placetel
3. Enable notifications for your phone numbers
4. Optional: Set a shared secret for HMAC verification

IMPORTANT: When a voicemail webhook arrives, we immediately fetch and download
the audio file because Placetel's signed URLs expire quickly (~20 minutes).
"""

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks

from app.config import get_settings
from app.database import SessionLocal
from app.models import Call

router = APIRouter(prefix="/webhook", tags=["webhook"])
logger = logging.getLogger(__name__)

# Minimum duration for voicemails to be processed
MIN_DURATION_SECONDS = 2


def verify_signature(request_body: bytes, signature: str, secret: str) -> bool:
    """Verify Placetel HMAC-SHA256 signature."""
    if not secret:
        return True  # Skip verification if no secret configured

    expected = hmac.new(
        secret.encode(),
        request_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected)


async def process_voicemail_immediate(call_id: str):
    """
    Immediately fetch and download voicemail when webhook is received.

    This is critical because Placetel's signed URLs expire in ~20 minutes.
    We fetch the voicemail data and download the audio file right away,
    then queue the rest of the processing (transcription, etc.).
    """
    from app.services.placetel import PlacetelService
    from app.services.scheduler import run_transcribe_job, run_summarize_job, run_email_job

    logger.info(f"Webhook: Immediately processing voicemail {call_id}")
    db = SessionLocal()
    try:
        placetel = PlacetelService()

        # Check if we already have this voicemail
        existing = db.query(Call).filter(
            Call.external_id == call_id,
            Call.provider == "placetel"
        ).first()

        if existing and existing.local_file_path:
            logger.info(f"Voicemail {call_id} already downloaded, skipping immediate fetch")
            return

        # Fetch voicemail data from Placetel API
        vm_data = await placetel.fetch_voicemail_by_id(call_id)
        if not vm_data:
            logger.warning(f"Could not fetch voicemail {call_id} from Placetel API")
            return

        duration = vm_data.get("duration") or 0
        file_url = vm_data.get("file_url")

        if existing:
            # Update existing record with fresh data
            call = existing
            if file_url and not call.file_url:
                call.file_url = file_url
        else:
            # Create new record
            to_number = vm_data.get("to_number", {})

            if duration < MIN_DURATION_SECONDS:
                initial_status = "skipped"
                initial_text = "[Too short]" if duration > 0 else "[No audio]"
            else:
                initial_status = "pending"
                initial_text = None

            call = Call(
                external_id=call_id,
                provider="placetel",
                direction="in",
                status="voicemail",
                from_number=vm_data.get("from_number"),
                to_number=to_number.get("number") if isinstance(to_number, dict) else to_number,
                to_number_name=to_number.get("name") if isinstance(to_number, dict) else None,
                duration=duration,
                started_at=datetime.fromisoformat(vm_data["received_at"].replace("Z", "+00:00"))
                if vm_data.get("received_at") else None,
                file_url=file_url,
                unread=vm_data.get("unread", True),
                transcription_status=initial_status,
                transcription_text=initial_text,
                email_status="pending" if initial_status == "pending" else "skipped",
            )
            db.add(call)
            db.flush()  # Get the ID

        # Download audio immediately if not already downloaded
        if duration >= MIN_DURATION_SECONDS and file_url and not call.local_file_path:
            try:
                local_path = await placetel.download_voicemail(call_id, file_url)
                call.local_file_path = local_path
                logger.info(f"Webhook: Downloaded voicemail {call_id} immediately")
            except Exception as e:
                logger.error(f"Webhook: Failed to download voicemail {call_id}: {e}")

        db.commit()

        # Trigger processing jobs
        logger.info(f"Webhook: Starting processing for voicemail {call_id}")
        await run_transcribe_job()
        await run_summarize_job()
        await run_email_job()
        logger.info(f"Webhook: Completed processing for voicemail {call_id}")

    except Exception as e:
        logger.error(f"Webhook: Failed to process voicemail {call_id}: {e}")
        db.rollback()
    finally:
        db.close()


async def process_voicemail_notification():
    """Background task to sync recent voicemails when webhook triggers."""
    from app.services.scheduler import run_sync_job

    logger.info("Webhook triggered - syncing recent voicemails")
    try:
        result = await run_sync_job()
        logger.info(f"Webhook sync complete: {result}")
    except Exception as e:
        logger.error(f"Webhook sync failed: {e}")


@router.post("/placetel")
async def placetel_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Receive Placetel call notifications.

    Events:
    - IncomingCall: New incoming call
    - CallAccepted: Call was answered
    - HungUp: Call ended (check type=voicemail for voicemails)
    - OutgoingCall: New outgoing call

    IMPORTANT: For voicemails, we immediately fetch and download the audio
    in a background task because Placetel's signed URLs expire in ~20 minutes.
    """
    settings = get_settings()

    # Get raw body for signature verification
    body = await request.body()

    # Verify signature if secret is configured
    signature = request.headers.get("X-PLACETEL-SIGNATURE", "")
    webhook_secret = getattr(settings, "placetel_webhook_secret", "")

    if webhook_secret and not verify_signature(body, signature, webhook_secret):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse form data
    form = await request.form()
    event = form.get("event")
    call_type = form.get("type")
    call_id = form.get("call_id")
    from_number = form.get("from")
    to_number = form.get("to")
    direction = form.get("direction")

    logger.info(f"Webhook received: event={event}, type={call_type}, call_id={call_id}, from={from_number}, direction={direction}")

    # Only process voicemail hangup events
    if event == "HungUp" and call_type == "voicemail" and direction == "in" and call_id:
        # CRITICAL: Immediately process to download audio before URL expires
        # Placetel signed URLs expire in ~20 minutes, so we can't wait for scheduled sync
        background_tasks.add_task(process_voicemail_immediate, str(call_id))
        return {"status": "accepted", "message": "Immediate processing triggered"}

    # Acknowledge other events but don't process
    return {"status": "ok", "event": event}


@router.get("/placetel")
async def placetel_webhook_verify():
    """Health check endpoint for webhook verification."""
    return {"status": "ok", "service": "sgos.phone", "webhook": "placetel"}
