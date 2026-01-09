# Placetel Voicemail Transcription

A self-hosted service that automatically transcribes and summarizes voicemail messages from Placetel phone systems.

## Features

- **Sync voicemails** from Placetel API
- **Transcribe** audio using ElevenLabs Scribe v2
- **Summarize** with LLM (OpenRouter/Gemini)
- **Web interface** to browse, play, and manage voicemails
- **Single container** deployment with Docker

## Screenshots

The web interface shows all voicemails with transcription status, language detection, and summaries.

## Requirements

- Docker and Docker Compose
- Placetel account with API access
- ElevenLabs API key (for transcription)
- OpenRouter API key (for summarization, optional)

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/stefanneubig/placetel-voicemail.git
cd placetel-voicemail
```

### 2. Configure secrets

The repository uses encrypted secrets. You need the decryption key to run the app.

**If you have the key:**
```bash
echo "DOTENV_PRIVATE_KEY=your-key-here" > .env.docker
```

**If setting up fresh:** Create a `.env` file with your API keys:
```bash
cat > .env << 'EOF'
PLACETEL_API_KEY=your-placetel-api-key
ELEVENLABS_API_KEY=your-elevenlabs-api-key
OPENROUTER_API_KEY=your-openrouter-api-key
DATABASE_URL=postgresql://placetel:placetel@db:5432/placetel
EOF
```

Then encrypt it:
```bash
# Install dotenvx
brew install dotenvx/brew/dotenvx  # macOS
# or: curl -sfS https://dotenvx.sh | sh

# Encrypt
dotenvx encrypt

# Extract key for Docker
grep "^DOTENV_PRIVATE_KEY=" .env.keys > .env.docker
```

### 3. Start the application

```bash
docker compose up -d
```

The app will be available at **http://localhost:9000**

### 4. Sync voicemails

1. Open the web interface
2. Select how many days back to sync (7, 30, 60, etc.)
3. Click "Sync from Placetel"

### 5. Transcribe and summarize

- Click **Transcribe** on individual voicemails, or
- Use the Admin page to batch process

## Architecture

```
┌─────────────────────────────────────────────┐
│              Docker Compose                  │
├─────────────────────┬───────────────────────┤
│    App Container    │    Database           │
│    (FastAPI)        │    (PostgreSQL 18)    │
│                     │                       │
│  - React frontend   │  - Voicemail records  │
│  - REST API         │  - Transcriptions     │
│  - Background jobs  │  - Summaries          │
└─────────────────────┴───────────────────────┘
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/voicemails` | List all voicemails |
| GET | `/voicemails/{id}` | Get single voicemail |
| GET | `/voicemails/{id}/audio` | Stream audio file |
| POST | `/sync?days=30` | Sync from Placetel |
| POST | `/voicemails/{id}/transcribe` | Transcribe one |
| POST | `/voicemails/{id}/summarize` | Summarize one |
| POST | `/transcribe-pending` | Transcribe all pending |
| POST | `/summarize-pending` | Summarize all transcribed |
| GET | `/health` | Health check |

API documentation available at `/docs` (Swagger UI).

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `PLACETEL_API_KEY` | Placetel API key | Yes |
| `ELEVENLABS_API_KEY` | ElevenLabs API key | Yes |
| `OPENROUTER_API_KEY` | OpenRouter API key | No (for summaries) |
| `DATABASE_URL` | PostgreSQL connection string | Yes |

### Ports

Default port mapping in `docker-compose.yml`:
- **9000** → App (change as needed)

To use a different port:
```yaml
ports:
  - "3000:8000"  # Access at localhost:3000
```

## Deployment

### With Dokploy / Coolify / CapRover

1. Connect your GitHub repository
2. Set environment variable: `DOTENV_PRIVATE_KEY`
3. Deploy

The app exposes port 8000 internally. Your platform handles external routing.

### With Cloudflare Tunnel

Point your tunnel to `http://app:8000` (or whatever your container is named).

### Manual Server

```bash
git clone https://github.com/stefanneubig/placetel-voicemail.git
cd placetel-voicemail
echo "DOTENV_PRIVATE_KEY=xxx" > .env.docker
docker compose up -d
```

## Development

### Local frontend development

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173` with hot reload.

### Backend development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn app.main:app --reload
```

## MCP Server (Claude Integration)

The API can be exposed as an MCP server, allowing Claude to interact directly with your voicemails.

### Setup

1. Install dependencies:
```bash
python -m venv .venv
.venv/bin/pip install fastmcp httpx
```

2. Make sure the API is running:
```bash
docker compose up -d
```

3. Run the MCP server:
```bash
VOICEMAIL_API_URL=http://localhost:9000 .venv/bin/python -m app.mcp_server
```

### Claude Code Configuration

Add to `~/.claude/claude_desktop_config.json`:

```json
{
    "mcpServers": {
        "voicemail": {
            "command": "python",
            "args": ["-m", "app.mcp_server"],
            "cwd": "/path/to/placetel-api",
            "env": {
                "VOICEMAIL_API_URL": "http://localhost:9000"
            }
        }
    }
}
```

### Available Tools

- `list_voicemails` - List all voicemails
- `get_voicemail` - Get details of a specific voicemail
- `sync_voicemails` - Sync from Placetel
- `transcribe_voicemail` - Transcribe a voicemail
- `summarize_voicemail` - Summarize a voicemail
- `health_check` - Check API health

## Tech Stack

- **Backend**: Python 3.13, FastAPI, SQLAlchemy 2.0
- **Frontend**: React 18, TypeScript, Tailwind CSS, Vite
- **Database**: PostgreSQL 18
- **Transcription**: ElevenLabs Scribe v2
- **Summarization**: OpenRouter (Gemini 3 Pro)
- **Secrets**: dotenvx (encrypted in repo)

## License

MIT

## Acknowledgments

- [Placetel](https://www.placetel.de/) for the phone system API
- [ElevenLabs](https://elevenlabs.io/) for speech-to-text
- [OpenRouter](https://openrouter.ai/) for LLM access
