# Phone (sgos.phone)

Internal phone management system. Currently handles **voicemail/mailbox messages** from Placetel:

1. **Syncs** voicemails from Placetel API
2. **Transcribes** audio using ElevenLabs speech-to-text
3. **Summarizes** transcripts with AI (sentiment, emotion, category, urgency)
4. **Forwards** to helpdesk via configurable API

## Current Integration: Voicemail

The only active module is voicemail processing. Future modules may include call logs, IVR management, etc.

### Processing Pipeline

```
Placetel API → Sync → Download MP3 → Transcribe → Summarize/Classify → Helpdesk API
```

Each voicemail gets:
- **Transcription**: Full text from audio
- **Corrected text**: LLM-cleaned transcript
- **Summary**: 2-3 sentence summary for support agents
- **Classification**: sentiment, emotion, category, is_urgent

## Quick Start

```bash
git clone https://github.com/stefanneubig/sgos.phone.git
cd sgos.phone

# Set decryption key for encrypted .env
echo "DOTENV_PRIVATE_KEY=your-key-here" > .env.docker

# Start
docker compose up -d
```

App runs at **http://localhost:9000**

## Configuration

### Settings (Admin UI)

| Setting | Default | Description |
|---------|---------|-------------|
| Sync Interval | 15 min | How often to fetch from Placetel |
| Auto Transcribe | On | Transcribe new voicemails automatically |
| Auto Summarize | On | Summarize after transcription |
| Send to Helpdesk | Off | Forward to helpdesk API |
| Helpdesk API URL | — | Target endpoint |

### Environment Variables

Encrypted in `.env`, decrypted at runtime with dotenvx:

| Variable | Description |
|----------|-------------|
| `PLACETEL_API_KEY` | Placetel API access |
| `ELEVENLABS_API_KEY` | ElevenLabs transcription |
| `OPENROUTER_API_KEY` | OpenRouter LLM |
| `DATABASE_URL` | PostgreSQL connection |

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/voicemails` | List voicemails |
| GET | `/voicemails/{id}` | Get single voicemail |
| GET | `/voicemails/{id}/audio` | Stream audio |
| DELETE | `/voicemails/{id}` | Delete voicemail |
| GET | `/settings` | Get settings |
| PUT | `/settings/{key}` | Update setting |
| POST | `/settings/sync-now` | Manual sync |
| GET | `/health` | Health check |

Full docs at `/docs` (Swagger UI)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Phone (sgos.phone)                      │
├─────────────────────────────────────────────────────────────┤
│  Frontend (React)          │  Backend (FastAPI)             │
│  ├─ Voicemail list         │  ├─ REST API                   │
│  ├─ Voicemail detail       │  ├─ Background scheduler       │
│  └─ Settings               │  └─ Helpdesk integration       │
├─────────────────────────────────────────────────────────────┤
│  Background Jobs (APScheduler, every N minutes)             │
│  ├─ Sync from Placetel                                      │
│  ├─ Transcribe pending                                      │
│  ├─ Summarize & classify                                    │
│  └─ Forward to helpdesk                                     │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL 18                                              │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Backend**: Python 3.13, FastAPI, SQLAlchemy 2.0, APScheduler
- **Frontend**: React 18, TypeScript, Tailwind CSS, Vite
- **Database**: PostgreSQL 18
- **Transcription**: ElevenLabs Scribe v2
- **Summarization**: OpenRouter (Gemini 2.5 Pro)
- **Secrets**: dotenvx

## Development

```bash
# Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## License

Proprietary
