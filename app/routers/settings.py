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
