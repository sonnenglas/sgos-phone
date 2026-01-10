"""
Placetel Webhook Handler

Receives notifications when calls end (including voicemails).
Documentation: https://github.com/Placetel/call-control-notify-api

Setup in Placetel:
1. Go to Settings → External APIs
2. Set Notification URL to: https://your-domain/webhook/placetel
3. Enable notifications for your phone numbers
4. Optional: Set a shared secret for HMAC verification
"""

import hashlib
import hmac
import logging
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks

from app.config import get_settings

router = APIRouter(prefix="/webhook", tags=["webhook"])
logger = logging.getLogger(__name__)


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

    logger.info(f"Webhook received: event={event}, type={call_type}, from={from_number}, direction={direction}")

    # Only process voicemail hangup events
    if event == "HungUp" and call_type == "voicemail" and direction == "in":
        # Trigger sync in background to respond quickly
        background_tasks.add_task(process_voicemail_notification)
        return {"status": "accepted", "message": "Sync triggered"}

    # Acknowledge other events but don't process
    return {"status": "ok", "event": event}


@router.get("/placetel")
async def placetel_webhook_verify():
    """Health check endpoint for webhook verification."""
    return {"status": "ok", "service": "sgos.phone", "webhook": "placetel"}
