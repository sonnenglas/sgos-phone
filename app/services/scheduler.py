"""
Background scheduler for automatic voicemail processing.

Jobs:
- sync_job: Fetch new voicemails from Placetel
- transcribe_job: Process pending transcriptions
- summarize_job: Process pending summaries
- email_job: Send completed voicemails to helpdesk
"""

import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.database import SessionLocal
from app.models import Setting, Call
from app.services.placetel import PlacetelService
from app.services.elevenlabs import ElevenLabsService
from app.services.openrouter import OpenRouterService

logger = logging.getLogger(__name__)

# Minimum duration for voicemails to be processed
MIN_DURATION_SECONDS = 2


def get_setting(key: str, default: str = "") -> str:
    """Get a setting value from the database."""
    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == key).first()
        return setting.value if setting else default
    finally:
        db.close()


def set_setting(key: str, value: str):
    """Set a setting value in the database."""
    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == key).first()
        if setting:
            setting.value = value
            setting.updated_at = datetime.now(timezone.utc)
        else:
            setting = Setting(key=key, value=value)
            db.add(setting)
        db.commit()
    finally:
        db.close()


def calculate_sync_days() -> int:
    """Calculate how many days back to sync based on last_sync_at.

    Returns days since last sync + 1 day buffer, capped at 30 days max.
    If never synced, returns 30 days.
    """
    last_sync = get_setting("last_sync_at", "")

    if not last_sync:
        logger.info("No previous sync found, fetching last 30 days")
        return 30

    try:
        last_sync_dt = datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days_since = (now - last_sync_dt).days + 1  # +1 day buffer

        # Clamp between 1 and 30 days
        days = max(1, min(days_since, 30))
        logger.info(f"Last sync: {last_sync_dt.isoformat()}, fetching last {days} days")
        return days
    except Exception as e:
        logger.warning(f"Failed to parse last_sync_at '{last_sync}': {e}, using 7 days")
        return 7


async def run_sync_job() -> dict:
    """Fetch new voicemails from Placetel."""
    logger.info("Starting sync job...")
    db = SessionLocal()
    try:
        placetel = PlacetelService()
        days = calculate_sync_days()
        voicemails = await placetel.fetch_voicemails(days=days)

        # Get email cutoff date - voicemails before this date should not be emailed
        email_only_after = get_setting("email_only_after", "")
        cutoff_date = None
        if email_only_after:
            try:
                cutoff_date = datetime.fromisoformat(email_only_after.replace("Z", "+00:00"))
                logger.info(f"Email cutoff date for sync: {cutoff_date.isoformat()}")
            except Exception:
                pass

        new_count = 0
        downloaded_count = 0
        skipped_by_cutoff = 0

        for vm_data in voicemails:
            external_id = str(vm_data["id"])
            existing = db.query(Call).filter(
                Call.external_id == external_id,
                Call.provider == "placetel"
            ).first()

            if existing:
                continue  # Already have this one

            to_number = vm_data.get("to_number", {})
            duration = vm_data.get("duration") or 0

            # Parse voicemail timestamp
            started_at = None
            if vm_data.get("received_at"):
                started_at = datetime.fromisoformat(vm_data["received_at"].replace("Z", "+00:00"))

            # Determine initial status
            if duration < MIN_DURATION_SECONDS:
                initial_status = "skipped"
                initial_text = "[Too short]" if duration > 0 else "[No audio]"
            else:
                initial_status = "pending"
                initial_text = None

            # Determine email status - apply cutoff check here
            if initial_status != "pending":
                email_status = "skipped"
            elif cutoff_date and started_at and started_at < cutoff_date:
                # Voicemail is before cutoff date - skip email
                email_status = "skipped"
                skipped_by_cutoff += 1
                logger.debug(f"Voicemail {external_id} before cutoff date, email skipped")
            else:
                email_status = "pending"

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
                email_status=email_status,
            )
            db.add(call)
            new_count += 1

            # Download audio if worth processing
            if duration >= MIN_DURATION_SECONDS and vm_data.get("file_url"):
                try:
                    local_path = await placetel.download_voicemail(external_id, vm_data["file_url"])
                    call.local_file_path = local_path
                    downloaded_count += 1
                except Exception as e:
                    logger.error(f"Failed to download voicemail {external_id}: {e}")

        db.commit()

        # Update last sync time
        set_setting("last_sync_at", datetime.now(timezone.utc).isoformat())

        logger.info(f"Sync complete: {new_count} new, {downloaded_count} downloaded, {skipped_by_cutoff} email-skipped by cutoff")
        return {"new": new_count, "downloaded": downloaded_count, "email_skipped_by_cutoff": skipped_by_cutoff}

    except Exception as e:
        logger.error(f"Sync job failed: {e}")
        return {"error": str(e)}
    finally:
        db.close()


async def run_retry_downloads_job() -> dict:
    """
    Retry downloading audio for voicemails that are pending but have no local file.

    This handles cases where:
    - Initial download failed
    - Signed URL expired before download
    - Network issues during download

    The PlacetelService.download_voicemail() will automatically fetch a fresh
    signed URL from the API if the stored URL has expired.
    """
    logger.info("Starting retry downloads job...")
    db = SessionLocal()
    try:
        # Find voicemails that need downloading
        pending = (
            db.query(Call)
            .filter(Call.status == "voicemail")
            .filter(Call.transcription_status == "pending")
            .filter(Call.local_file_path.is_(None))
            .filter(Call.duration >= MIN_DURATION_SECONDS)
            .filter(Call.external_id.isnot(None))
            .limit(10)
            .all()
        )

        if not pending:
            return {"retried": 0, "success": 0}

        placetel = PlacetelService()
        success = 0
        failed = 0

        for call in pending:
            try:
                logger.info(f"Retrying download for voicemail {call.id} (external_id={call.external_id})")

                # Try with stored URL first, will auto-refresh if expired
                file_url = call.file_url
                if not file_url:
                    # No stored URL, fetch from API
                    fresh_data = await placetel.fetch_voicemail_by_id(call.external_id)
                    if fresh_data and fresh_data.get("file_url"):
                        file_url = fresh_data["file_url"]
                        call.file_url = file_url
                    else:
                        logger.warning(f"No file_url available for voicemail {call.id}")
                        continue

                local_path = await placetel.download_voicemail(call.external_id, file_url)
                call.local_file_path = local_path
                success += 1
                logger.info(f"Successfully downloaded voicemail {call.id}")

            except Exception as e:
                logger.error(f"Failed to retry download for voicemail {call.id}: {e}")
                failed += 1

        db.commit()
        logger.info(f"Retry downloads complete: {success} success, {failed} failed")
        return {"retried": len(pending), "success": success, "failed": failed}

    except Exception as e:
        logger.error(f"Retry downloads job failed: {e}")
        return {"error": str(e)}
    finally:
        db.close()


async def run_transcribe_job() -> dict:
    """Transcribe pending voicemails."""
    if get_setting("auto_transcribe", "true") != "true":
        return {"skipped": "auto_transcribe disabled"}

    logger.info("Starting transcribe job...")
    db = SessionLocal()
    try:
        pending = (
            db.query(Call)
            .filter(Call.status == "voicemail")
            .filter(Call.transcription_status == "pending")
            .filter(Call.local_file_path.isnot(None))
            .filter(Call.duration >= MIN_DURATION_SECONDS)
            .limit(10)
            .all()
        )

        if not pending:
            return {"transcribed": 0}

        elevenlabs = ElevenLabsService()
        transcribed = 0
        failed = 0

        for call in pending:
            try:
                call.transcription_status = "processing"
                db.commit()

                result = await elevenlabs.transcribe(call.local_file_path)

                call.transcription_text = result.text
                call.transcription_language = result.language
                call.transcription_confidence = result.confidence
                call.transcription_model = result.model
                call.transcription_status = "completed"
                call.transcribed_at = datetime.now(timezone.utc)
                transcribed += 1
                logger.info(f"Transcribed voicemail {call.id}")

            except Exception as e:
                logger.error(f"Failed to transcribe voicemail {call.id}: {e}")
                call.transcription_status = "failed"
                failed += 1

        db.commit()
        logger.info(f"Transcribe complete: {transcribed} done, {failed} failed")
        return {"transcribed": transcribed, "failed": failed}

    finally:
        db.close()


async def run_summarize_job() -> dict:
    """Summarize transcribed voicemails."""
    if get_setting("auto_summarize", "true") != "true":
        return {"skipped": "auto_summarize disabled"}

    logger.info("Starting summarize job...")
    db = SessionLocal()
    try:
        skip_texts = ["[No audio]", "[Too short]", "[No audio content]"]

        pending = (
            db.query(Call)
            .filter(Call.status == "voicemail")
            .filter(Call.transcription_status == "completed")
            .filter(Call.transcription_text.isnot(None))
            .filter(Call.summary.is_(None))
            .filter(Call.transcription_text.notin_(skip_texts))
            .limit(10)
            .all()
        )

        if not pending:
            return {"summarized": 0}

        openrouter = OpenRouterService()
        summarized = 0
        failed = 0

        for call in pending:
            # Skip very short transcripts
            if len(call.transcription_text.strip()) < 20:
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
                call.email_subject = result.email_subject
                summarized += 1
                logger.info(f"Summarized voicemail {call.id} (sentiment={result.sentiment}, priority={result.priority})")

            except Exception as e:
                logger.error(f"Failed to summarize voicemail {call.id}: {e}")
                failed += 1

        db.commit()
        logger.info(f"Summarize complete: {summarized} done, {failed} failed")
        return {"summarized": summarized, "failed": failed}

    finally:
        db.close()


async def run_email_job() -> dict:
    """Send voicemail notification emails via Postmark."""
    from app.config import get_settings
    from app.services.email import PostmarkEmailService, voicemail_to_email_data

    if get_setting("auto_email", "false") != "true":
        return {"skipped": "auto_email disabled"}

    to_email = get_setting("notification_email", "")
    if not to_email:
        return {"skipped": "notification_email not configured"}

    settings = get_settings()
    if not settings.postmark_api_token or not settings.email_from:
        return {"skipped": "Postmark not configured (missing token or from email)"}

    # Check cutoff date - only email voicemails received after this date
    email_only_after = get_setting("email_only_after", "")
    cutoff_date = None
    if email_only_after:
        try:
            cutoff_date = datetime.fromisoformat(email_only_after.replace("Z", "+00:00"))
        except Exception:
            pass

    logger.info("Starting email job...")
    db = SessionLocal()
    try:
        query = (
            db.query(Call)
            .filter(Call.email_status == "pending")
            .filter(Call.summary.isnot(None))
        )

        # Apply cutoff date filter if set
        if cutoff_date:
            query = query.filter(Call.started_at >= cutoff_date)
            logger.info(f"Email cutoff date: {cutoff_date.isoformat()}")

        pending = query.limit(10).all()

        if not pending:
            return {"sent": 0}

        email_service = PostmarkEmailService(
            api_token=settings.postmark_api_token,
            from_email=settings.email_from,
            from_name=settings.email_from_name,
        )

        sent = 0
        failed = 0

        for call in pending:
            email_data = voicemail_to_email_data(call, settings.base_url)

            message_id = await email_service.send(
                to_email=to_email,
                data=email_data,
                attach_audio=False,  # Link only, no attachment
            )

            if message_id:
                call.email_status = "sent"
                call.email_sent_at = datetime.now(timezone.utc)
                call.email_message_id = message_id  # Store for delivery verification
                sent += 1
            else:
                call.email_status = "failed"
                failed += 1

        db.commit()
        logger.info(f"Email job complete: {sent} sent, {failed} failed")
        return {"sent": sent, "failed": failed}

    finally:
        db.close()


async def run_all_jobs():
    """Run all processing jobs in sequence."""
    await run_sync_job()
    await run_retry_downloads_job()  # Retry any failed downloads with fresh URLs
    await run_transcribe_job()
    await run_summarize_job()
    await run_email_job()


def reschedule_sync_job(scheduler: AsyncIOScheduler, interval_minutes: int):
    """Reschedule the sync job with a new interval."""
    try:
        scheduler.remove_job("sync_job")
    except Exception:
        pass

    scheduler.add_job(
        run_all_jobs,
        IntervalTrigger(minutes=interval_minutes),
        id="sync_job",
        replace_existing=True,
    )
    logger.info(f"Rescheduled sync job to run every {interval_minutes} minutes")


async def create_scheduler() -> AsyncIOScheduler:
    """Create and start the background scheduler."""
    scheduler = AsyncIOScheduler()

    # Get interval from settings (default 5 minutes for faster voicemail pickup)
    interval = int(get_setting("sync_interval_minutes", "5"))

    # Add the main processing job
    scheduler.add_job(
        run_all_jobs,
        IntervalTrigger(minutes=interval),
        id="sync_job",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"Scheduler started. Sync job runs every {interval} minutes.")

    # Don't run immediately on startup - let the first scheduled run happen
    # Users can trigger manual sync from the admin UI if needed

    return scheduler
