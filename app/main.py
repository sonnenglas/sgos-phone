from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
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

app.include_router(voicemails.router)
app.include_router(sync.router)


@app.get("/", tags=["root"])
def root():
    return {
        "name": "Placetel Voicemail Transcription API",
        "version": "1.0.0",
        "docs": "/docs",
    }


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
