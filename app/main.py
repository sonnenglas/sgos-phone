import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.routers import voicemails, sync, settings
from app.schemas import HealthResponse
from app.models import Voicemail, Setting


# Global scheduler reference (set during startup)
scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global scheduler
    # Import here to avoid circular imports
    from app.services.scheduler import create_scheduler

    scheduler = await create_scheduler()
    yield
    # Shutdown
    if scheduler:
        scheduler.shutdown()


app = FastAPI(
    title="Phone API",
    description="Internal phone management system - voicemail processing with automatic transcription and summarization.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(voicemails.router)
app.include_router(sync.router)
app.include_router(settings.router)


def get_scheduler_status() -> str:
    """Get current scheduler status."""
    global scheduler
    if scheduler is None:
        return "not_started"
    return "running" if scheduler.running else "stopped"


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    voicemails_count = db.query(Voicemail).count()

    # Get last sync time from settings
    last_sync = db.query(Setting).filter(Setting.key == "last_sync_at").first()
    last_sync_at = last_sync.value if last_sync and last_sync.value else None

    return HealthResponse(
        status="healthy" if db_status == "healthy" else "unhealthy",
        database=db_status,
        voicemails_count=voicemails_count,
        scheduler=get_scheduler_status(),
        last_sync_at=last_sync_at,
    )


# Serve frontend static files
STATIC_DIR = Path("/app/static")

if STATIC_DIR.exists():
    # Serve static assets (JS, CSS, etc.)
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    # SPA catch-all: serve index.html for all non-API routes
    @app.get("/{path:path}", include_in_schema=False)
    async def serve_spa(path: str):
        # Check if it's a file request
        file_path = STATIC_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html for SPA routing
        return FileResponse(STATIC_DIR / "index.html")
