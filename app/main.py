import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import get_db
from app.routers import calls, sync, settings, webhook
from app.schemas import HealthResponse
from app.models import Call, Setting
from app.config import get_settings


# Global scheduler reference (set during startup)
scheduler = None


# Routes that don't require authentication
PUBLIC_ROUTES = {
    "/health",
    "/webhook/placetel",
    "/docs",
    "/openapi.json",
    "/redoc",
}

# Route prefixes for token-based access (email links)
TOKEN_ROUTES = (
    "/listen/",  # Public voicemail player
    "/public/",  # Public audio files
)

# Route prefixes accessible to all @sonnenglas.net users
VIEWER_ROUTES = (
    "/listen/",
    "/public/",
)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce Cloudflare Zero Trust authentication.

    Permission model:
    - Token routes (/listen, /public with ?token=): No auth required (for email links)
    - @sonnenglas.net emails: VIEW access (listen pages only)
    - stefan@sonnenglas.net: ADMIN access (everything)
    """

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        path = request.url.path

        # Skip auth for public routes (health, webhook, docs)
        if path in PUBLIC_ROUTES:
            return await call_next(request)

        # Token-based routes: allow if valid token is present
        if path.startswith(TOKEN_ROUTES) and "token=" in str(request.url.query):
            return await call_next(request)

        # Skip auth in development
        if settings.env == "development":
            return await call_next(request)

        # Check Cloudflare Zero Trust header
        email = request.headers.get("Cf-Access-Authenticated-User-Email", "").lower()

        if not email:
            return HTMLResponse(
                content="<h1>401 Unauthorized</h1><p>Authentication required.</p>",
                status_code=401
            )

        # Admin: stefan@sonnenglas.net has full access
        if email == settings.allowed_email.lower():
            return await call_next(request)

        # Viewer: @sonnenglas.net can access viewer routes
        if email.endswith("@sonnenglas.net") and path.startswith(VIEWER_ROUTES):
            return await call_next(request)

        # Default: deny access
        return HTMLResponse(
            content=f"<h1>403 Forbidden</h1><p>Access denied for {email}.</p>",
            status_code=403
        )


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

# Add auth middleware first
app.add_middleware(AuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(calls.router)
app.include_router(sync.router)
app.include_router(settings.router)
app.include_router(webhook.router)


def get_scheduler_status() -> str:
    """Get current scheduler status."""
    global scheduler
    if scheduler is None:
        return "not_started"
    return "running" if scheduler.running else "stopped"


@app.get("/me", tags=["auth"])
def get_current_user(request: Request):
    """Get current user from Cloudflare Zero Trust headers."""
    settings = get_settings()

    email = request.headers.get("Cf-Access-Authenticated-User-Email")
    # Development fallback
    if not email and settings.env == "development":
        email = "stefan@sonnenglas.net"
    return {"email": email}


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    calls_count = db.query(Call).count()
    voicemails_count = db.query(Call).filter(Call.status == "voicemail").count()

    # Get last sync time from settings
    last_sync = db.query(Setting).filter(Setting.key == "last_sync_at").first()
    last_sync_at = last_sync.value if last_sync and last_sync.value else None

    return HealthResponse(
        status="healthy" if db_status == "healthy" else "unhealthy",
        database=db_status,
        calls_count=calls_count,
        voicemails_count=voicemails_count,
        scheduler=get_scheduler_status(),
        last_sync_at=last_sync_at,
    )


# =============================================================================
# PUBLIC ROUTES (no auth required, but need valid token)
# =============================================================================

@app.get("/listen/{voicemail_id}", response_class=HTMLResponse, tags=["public"])
def public_listen_page(
    voicemail_id: int,
    token: str = Query(..., description="Access token"),
    db: Session = Depends(get_db),
):
    """Public page with audio player for voicemail. Requires valid token."""
    from app.services.access_token import verify_access_token

    # Verify token
    if not verify_access_token(voicemail_id, token):
        raise HTTPException(status_code=403, detail="Invalid or expired token")

    # Get voicemail
    call = db.query(Call).filter(Call.id == voicemail_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Voicemail not found")

    if call.status != "voicemail":
        raise HTTPException(status_code=400, detail="Not a voicemail")

    # Format data for display
    from_number = call.from_number or "Unknown"
    if from_number.startswith("+49"):
        from_number = f"0{from_number[3:]}"

    destination = call.to_number_name or call.to_number or "Unknown"
    duration_mins = (call.duration or 0) // 60
    duration_secs = (call.duration or 0) % 60
    duration = f"{duration_mins}:{duration_secs:02d}"

    received = ""
    if call.started_at:
        received = call.started_at.strftime("%d.%m.%Y um %H:%M Uhr")

    # Build the page
    audio_url = f"/public/{voicemail_id}/audio?token={token}"

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voicemail from {from_number}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .card {{
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            max-width: 480px;
            width: 100%;
            overflow: hidden;
        }}
        .header {{
            background: #1f2937;
            color: #ffffff;
            padding: 24px;
        }}
        .header h1 {{
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 4px;
        }}
        .header .date {{
            color: #9ca3af;
            font-size: 14px;
        }}
        .content {{
            padding: 24px;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 24px;
        }}
        .info-item {{

        }}
        .info-label {{
            font-size: 11px;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 4px;
        }}
        .info-value {{
            font-size: 16px;
            color: #111827;
            font-weight: 500;
        }}
        .info-value.large {{
            font-size: 20px;
            font-weight: 600;
        }}
        .player {{
            background: #f3f4f6;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
        }}
        audio {{
            width: 100%;
            height: 48px;
        }}
        .summary {{
            background: #f9fafb;
            border-left: 4px solid #3b82f6;
            padding: 16px;
            border-radius: 0 8px 8px 0;
            margin-bottom: 24px;
        }}
        .summary-label {{
            font-size: 11px;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
        }}
        .summary-text {{
            font-size: 15px;
            line-height: 1.6;
            color: #374151;
        }}
        .transcript {{
            border-top: 1px solid #e5e7eb;
            padding-top: 24px;
        }}
        .transcript-label {{
            font-size: 11px;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 12px;
        }}
        .transcript-text {{
            font-size: 14px;
            line-height: 1.7;
            color: #4b5563;
            white-space: pre-wrap;
        }}
        .footer {{
            background: #f9fafb;
            padding: 16px 24px;
            border-top: 1px solid #e5e7eb;
            text-align: center;
            font-size: 12px;
            color: #9ca3af;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 500;
            margin-right: 8px;
            margin-bottom: 8px;
        }}
        .badge.high {{
            background: #fee2e2;
            color: #dc2626;
        }}
        .badge.category {{
            background: #e0e7ff;
            color: #4338ca;
        }}
        .badges {{
            margin-bottom: 16px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <h1>Voicemail</h1>
            <div class="date">{received}</div>
        </div>
        <div class="content">
            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">From</div>
                    <div class="info-value large">{from_number}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">To</div>
                    <div class="info-value">{destination}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Duration</div>
                    <div class="info-value">{duration}</div>
                </div>
            </div>

            {"<div class='badges'>" + ("<span class='badge high'>High Priority</span>" if call.priority == "high" else "") + (f"<span class='badge category'>{(call.category or '').replace('_', ' ').title()}</span>" if call.category else "") + "</div>" if call.priority == "high" or call.category else ""}

            <div class="player">
                <audio controls preload="metadata">
                    <source src="{audio_url}" type="audio/mpeg">
                    Your browser does not support the audio element.
                </audio>
            </div>

            {f'''<div class="summary">
                <div class="summary-label">Summary</div>
                <div class="summary-text">{call.summary}</div>
                {f'<div class="summary-text" style="margin-top: 12px; color: #6b7280; font-style: italic;"><strong>English:</strong> {call.summary_en}</div>' if call.summary_en and call.summary_en != call.summary else ''}
            </div>''' if call.summary else ""}

            {f'''<div class="transcript">
                <div class="transcript-label">Full Transcript</div>
                <div class="transcript-text">{call.corrected_text or call.transcription_text}</div>
            </div>''' if call.corrected_text or call.transcription_text else ""}
        </div>
        <div class="footer">
            Phone App &middot; Voicemail #{voicemail_id}
        </div>
    </div>
</body>
</html>"""

    return HTMLResponse(content=html)


@app.get("/public/{voicemail_id}/audio", tags=["public"])
def public_audio(
    voicemail_id: int,
    token: str = Query(..., description="Access token"),
    db: Session = Depends(get_db),
):
    """Public audio file access. Requires valid token."""
    from app.services.access_token import verify_access_token

    # Verify token
    if not verify_access_token(voicemail_id, token):
        raise HTTPException(status_code=403, detail="Invalid or expired token")

    # Get voicemail
    call = db.query(Call).filter(Call.id == voicemail_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Voicemail not found")

    if not call.local_file_path:
        raise HTTPException(status_code=404, detail="Audio file not available")

    file_path = Path(call.local_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        filename=f"voicemail_{voicemail_id}.mp3",
    )


# =============================================================================
# STATIC FILES & SPA
# =============================================================================

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
