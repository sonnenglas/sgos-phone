import os
from pathlib import Path

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.routers import voicemails, sync
from app.schemas import HealthResponse
from app.models import Voicemail

app = FastAPI(
    title="Placetel Voicemail Transcription API",
    description="Fetch voicemails from Placetel, transcribe with ElevenLabs Scribe v2, and store in PostgreSQL.",
    version="1.0.0",
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


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    voicemails_count = db.query(Voicemail).count()

    return HealthResponse(
        status="healthy" if db_status == "healthy" else "unhealthy",
        database=db_status,
        voicemails_count=voicemails_count,
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
