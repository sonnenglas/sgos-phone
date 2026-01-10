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
from app.models import Setting, Voicemail
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


async def run_sync_job() -> dict:
    """Fetch new voicemails from Placetel."""
    logger.info("Starting sync job...")
    db = SessionLocal()
    try:
        placetel = PlacetelService()
        voicemails = await placetel.fetch_voicemails(days=7)  # Last 7 days

        new_count = 0
        downloaded_count = 0

        for vm_data in voicemails:
            external_id = str(vm_data["id"])
            existing = db.query(Voicemail).filter(
                Voicemail.external_id == external_id,
                Voicemail.provider == "placetel"
            ).first()

            if existing:
                continue  # Already have this one

            to_number = vm_data.get("to_number", {})
            duration = vm_data.get("duration") or 0

            # Determine initial status
            if duration < MIN_DURATION_SECONDS:
                initial_status = "skipped"
                initial_text = "[Too short]" if duration > 0 else "[No audio]"
            else:
                initial_status = "pending"
                initial_text = None

            voicemail = Voicemail(
                external_id=external_id,
                provider="placetel",
                from_number=vm_data.get("from_number"),
                to_number=to_number.get("number") if isinstance(to_number, dict) else to_number,
                to_number_name=to_number.get("name") if isinstance(to_number, dict) else None,
                duration=duration,
                received_at=datetime.fromisoformat(vm_data["received_at"].replace("Z", "+00:00"))
                if vm_data.get("received_at") else None,
                file_url=vm_data.get("file_url"),
                unread=vm_data.get("unread", True),
                transcription_status=initial_status,
                transcription_text=initial_text,
                email_status="pending" if initial_status == "pending" else "skipped",
            )
            db.add(voicemail)
            new_count += 1

            # Download audio if worth processing
            if duration >= MIN_DURATION_SECONDS and vm_data.get("file_url"):
                try:
                    local_path = await placetel.download_voicemail(external_id, vm_data["file_url"])
                    voicemail.local_file_path = local_path
                    downloaded_count += 1
                except Exception as e:
                    logger.error(f"Failed to download voicemail {external_id}: {e}")

        db.commit()

        # Update last sync time
        set_setting("last_sync_at", datetime.now(timezone.utc).isoformat())

        logger.info(f"Sync complete: {new_count} new, {downloaded_count} downloaded")
        return {"new": new_count, "downloaded": downloaded_count}

    except Exception as e:
        logger.error(f"Sync job failed: {e}")
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
            db.query(Voicemail)
            .filter(Voicemail.transcription_status == "pending")
            .filter(Voicemail.local_file_path.isnot(None))
            .filter(Voicemail.duration >= MIN_DURATION_SECONDS)
            .limit(10)
            .all()
        )

        if not pending:
            return {"transcribed": 0}

        elevenlabs = ElevenLabsService()
        transcribed = 0
        failed = 0

        for voicemail in pending:
            try:
                voicemail.transcription_status = "processing"
                db.commit()

                result = await elevenlabs.transcribe(voicemail.local_file_path)

                voicemail.transcription_text = result.text
                voicemail.transcription_language = result.language
                voicemail.transcription_confidence = result.confidence
                voicemail.transcription_status = "completed"
                voicemail.transcribed_at = datetime.now(timezone.utc)
                transcribed += 1
                logger.info(f"Transcribed voicemail {voicemail.id}")

            except Exception as e:
                logger.error(f"Failed to transcribe voicemail {voicemail.id}: {e}")
                voicemail.transcription_status = "failed"
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
            db.query(Voicemail)
            .filter(Voicemail.transcription_status == "completed")
            .filter(Voicemail.transcription_text.isnot(None))
            .filter(Voicemail.summary.is_(None))
            .filter(Voicemail.transcription_text.notin_(skip_texts))
            .limit(10)
            .all()
        )

        if not pending:
            return {"summarized": 0}

        openrouter = OpenRouterService()
        summarized = 0
        failed = 0

        for voicemail in pending:
            # Skip very short transcripts
            if len(voicemail.transcription_text.strip()) < 20:
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
                voicemail.sentiment = result.sentiment
                voicemail.emotion = result.emotion
                voicemail.category = result.category
                voicemail.is_urgent = result.is_urgent
                summarized += 1
                logger.info(f"Summarized voicemail {voicemail.id} (sentiment={result.sentiment}, urgent={result.is_urgent})")

            except Exception as e:
                logger.error(f"Failed to summarize voicemail {voicemail.id}: {e}")
                failed += 1

        db.commit()
        logger.info(f"Summarize complete: {summarized} done, {failed} failed")
        return {"summarized": summarized, "failed": failed}

    finally:
        db.close()


async def run_email_job() -> dict:
    """Send voicemails to helpdesk (placeholder for custom API)."""
    if get_setting("auto_email", "false") != "true":
        return {"skipped": "auto_email disabled"}

    api_url = get_setting("helpdesk_api_url", "")
    if not api_url:
        return {"skipped": "helpdesk_api_url not configured"}

    logger.info("Starting email job...")
    db = SessionLocal()
    try:
        pending = (
            db.query(Voicemail)
            .filter(Voicemail.email_status == "pending")
            .filter(Voicemail.summary.isnot(None))
            .limit(10)
            .all()
        )

        if not pending:
            return {"sent": 0}

        # TODO: Implement actual API call when details are provided
        # For now, just mark as sent for testing
        sent = 0
        for voicemail in pending:
            # Placeholder: would call helpdesk API here
            logger.info(f"Would send voicemail {voicemail.id} to helpdesk")
            # voicemail.email_status = "sent"
            # voicemail.email_sent_at = datetime.now(timezone.utc)
            # sent += 1

        db.commit()
        return {"sent": sent, "pending": len(pending)}

    finally:
        db.close()


async def run_all_jobs():
    """Run all processing jobs in sequence."""
    await run_sync_job()
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

    # Get interval from settings (default 15 minutes)
    interval = int(get_setting("sync_interval_minutes", "15"))

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
