# Phone

Internal phone management system for voicemail processing with automatic transcription and summarization.

## Features

- **Automatic sync** from Placetel API on configurable intervals
- **Auto-transcribe** using ElevenLabs Scribe v2
- **Auto-summarize** with LLM (OpenRouter/Gemini)
- **Helpdesk integration** via custom API (configurable)
- **Web interface** to browse, play, and manage voicemails
- **Settings UI** to configure processing behavior
- **Single container** deployment with Docker

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/stefanneubig/phone.git
cd phone

# Create .env.docker with the decryption key
echo "DOTENV_PRIVATE_KEY=your-key-here" > .env.docker
```

### 2. Start the application

```bash
docker compose up -d
```

The app will be available at **http://localhost:9000**

### 3. Configure settings

1. Open the web interface
2. Go to Settings (admin page)
3. Configure sync interval and processing options

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Phone App                                │
├─────────────────────────────────────────────────────────────┤
│  Frontend (React)          │  Backend (FastAPI)             │
│  ├─ /voicemails (list)     │  ├─ REST API                   │
│  ├─ /voicemails/:id        │  ├─ Background Scheduler       │
│  └─ /admin (settings)      │  └─ Helpdesk Integration       │
├─────────────────────────────────────────────────────────────┤
│  Background Worker (APScheduler)                            │
│  ├─ Sync job (configurable interval)                        │
│  ├─ Transcribe job (auto-process pending)                   │
│  ├─ Summarize job (auto-process transcribed)                │
│  └─ Helpdesk job (send to configured API)                   │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL 18                                               │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

### Settings (via Admin UI)

| Setting | Default | Description |
|---------|---------|-------------|
| Sync Interval | 15 min | How often to fetch from Placetel |
| Auto Transcribe | On | Automatically transcribe new voicemails |
| Auto Summarize | On | Automatically summarize after transcription |
| Send to Helpdesk | Off | Send completed voicemails to helpdesk API |
| Helpdesk API URL | - | Target endpoint for helpdesk integration |

### Environment Variables

All encrypted in `.env`, decrypted at runtime:

| Variable | Description |
|----------|-------------|
| `PLACETEL_API_KEY` | Placetel API access |
| `ELEVENLABS_API_KEY` | ElevenLabs transcription |
| `OPENROUTER_API_KEY` | OpenRouter LLM summarization |
| `DATABASE_URL` | PostgreSQL connection string |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/voicemails` | List all voicemails |
| GET | `/voicemails/{id}` | Get single voicemail |
| GET | `/voicemails/{id}/audio` | Stream audio file |
| DELETE | `/voicemails/{id}` | Delete voicemail |
| GET | `/settings` | Get all settings |
| PUT | `/settings/{key}` | Update a setting |
| POST | `/settings/sync-now` | Trigger manual sync |
| GET | `/health` | Health check |

API documentation: `/docs` (Swagger UI)

## Deployment

### Docker (Recommended)

```bash
# Clone repository
git clone https://github.com/stefanneubig/phone.git
cd phone

# Set the decryption key
echo "DOTENV_PRIVATE_KEY=xxx" > .env.docker

# Start
docker compose up -d

# Verify
curl http://localhost:9000/health
```

### With Dokploy / Coolify

1. Connect your GitHub repository
2. Set environment variable: `DOTENV_PRIVATE_KEY`
3. Deploy

## Development

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Tech Stack

- **Backend**: Python 3.13, FastAPI, SQLAlchemy 2.0, APScheduler
- **Frontend**: React 18, TypeScript, Tailwind CSS, Vite
- **Database**: PostgreSQL 18
- **Transcription**: ElevenLabs Scribe v2
- **Summarization**: OpenRouter (Gemini 3 Pro)
- **Secrets**: dotenvx (encrypted in repo)

## License

MIT
