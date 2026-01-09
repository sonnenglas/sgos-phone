import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import type { HealthResponse } from '../types';

export default function Admin() {
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(console.error);
  }, []);

  return (
    <div className="animate-fade-in">
      <Link to="/" className="inline-block text-secondary hover:text-black transition-colors duration-150 mb-8">
        &larr; Back to messages
      </Link>

      <h1 className="text-3xl font-semibold tracking-tight mb-8">Admin</h1>

      {/* System Status */}
      <section className="mb-12">
        <h2 className="text-xs font-medium text-secondary uppercase tracking-wide mb-4">System Status</h2>
        <div className="border border-border p-4">
          {health ? (
            <div className="grid grid-cols-3 gap-8 text-sm">
              <div>
                <span className="text-secondary">Status</span>
                <p className="mt-1 font-medium">{health.status}</p>
              </div>
              <div>
                <span className="text-secondary">Database</span>
                <p className="mt-1 font-medium">{health.database}</p>
              </div>
              <div>
                <span className="text-secondary">Voicemails</span>
                <p className="mt-1 font-medium">{health.voicemails_count}</p>
              </div>
            </div>
          ) : (
            <p className="text-secondary">Loading...</p>
          )}
        </div>
      </section>

      {/* Data Model */}
      <section className="mb-12">
        <h2 className="text-xs font-medium text-secondary uppercase tracking-wide mb-4">Data Model</h2>

        <div className="border border-border p-6">
          {/* Entity Relationship Diagram (ASCII) */}
          <pre className="text-xs font-mono mb-6 overflow-x-auto">
{`┌─────────────────────────────────────────────────────────────────┐
│                          VOICEMAIL                              │
├─────────────────────────────────────────────────────────────────┤
│  id                 BIGINT        PK    Placetel voicemail ID   │
├─────────────────────────────────────────────────────────────────┤
│  from_number        VARCHAR(50)         Caller phone number     │
│  to_number          VARCHAR(50)         Destination number      │
│  to_number_name     VARCHAR(255)        Destination name        │
│  duration           INTEGER             Duration in seconds     │
│  received_at        TIMESTAMPTZ         When call was received  │
├─────────────────────────────────────────────────────────────────┤
│  file_url           TEXT                Placetel URL (expires)  │
│  local_file_path    VARCHAR(500)        Local MP3 path          │
│  unread             BOOLEAN             Read status             │
├─────────────────────────────────────────────────────────────────┤
│  transcription_status  VARCHAR(20)      pending|processing|     │
│                                         completed|failed|skipped│
│  transcription_text    TEXT             Raw transcript          │
│  transcription_language VARCHAR(10)     ISO language code       │
│  transcription_confidence FLOAT         0.0 - 1.0               │
│  transcribed_at        TIMESTAMPTZ      When transcribed        │
├─────────────────────────────────────────────────────────────────┤
│  corrected_text     TEXT                LLM-corrected text      │
│  summary            TEXT                Concise summary         │
│  summary_model      VARCHAR(100)        Model used              │
│  summarized_at      TIMESTAMPTZ         When summarized         │
├─────────────────────────────────────────────────────────────────┤
│  created_at         TIMESTAMPTZ         Record created          │
│  updated_at         TIMESTAMPTZ         Record updated          │
└─────────────────────────────────────────────────────────────────┘`}
          </pre>
        </div>
      </section>

      {/* Field Reference */}
      <section className="mb-12">
        <h2 className="text-xs font-medium text-secondary uppercase tracking-wide mb-4">Field Reference</h2>

        <div className="border border-border divide-y divide-border">
          <FieldRow
            name="id"
            type="BIGINT"
            description="Primary key from Placetel API. Unique identifier for each voicemail."
          />
          <FieldRow
            name="from_number"
            type="VARCHAR(50)"
            description="The caller's phone number in international format."
          />
          <FieldRow
            name="to_number"
            type="VARCHAR(50)"
            description="The destination phone number that received the call."
          />
          <FieldRow
            name="to_number_name"
            type="VARCHAR(255)"
            description="Human-readable name for the destination (e.g., 'Kundenservice Hotline DE')."
          />
          <FieldRow
            name="duration"
            type="INTEGER"
            description="Length of the voicemail in seconds. Messages < 2s are auto-skipped."
          />
          <FieldRow
            name="received_at"
            type="TIMESTAMPTZ"
            description="When the voicemail was received, with timezone."
          />
          <FieldRow
            name="file_url"
            type="TEXT"
            description="Signed Google Cloud Storage URL from Placetel. Expires after ~1 hour."
          />
          <FieldRow
            name="local_file_path"
            type="VARCHAR(500)"
            description="Path to downloaded MP3 file on local storage (/app/data/voicemails/)."
          />
          <FieldRow
            name="transcription_status"
            type="VARCHAR(20)"
            description="One of: pending (awaiting), processing (in progress), completed (done), failed (error), skipped (too short)."
          />
          <FieldRow
            name="transcription_text"
            type="TEXT"
            description="Raw transcript from ElevenLabs Scribe v2. May contain filler words and errors."
          />
          <FieldRow
            name="transcription_language"
            type="VARCHAR(10)"
            description="Detected language code (e.g., 'deu' for German, 'eng' for English)."
          />
          <FieldRow
            name="transcription_confidence"
            type="FLOAT"
            description="Language detection confidence from 0.0 to 1.0 (e.g., 0.998 = 99.8%)."
          />
          <FieldRow
            name="corrected_text"
            type="TEXT"
            description="LLM-corrected transcript with filler words removed and errors fixed."
          />
          <FieldRow
            name="summary"
            type="TEXT"
            description="Concise 2-3 sentence summary for customer support agents."
          />
          <FieldRow
            name="summary_model"
            type="VARCHAR(100)"
            description="OpenRouter model used for summarization (e.g., 'google/gemini-3-pro-preview')."
          />
        </div>
      </section>

      {/* Processing Pipeline */}
      <section className="mb-12">
        <h2 className="text-xs font-medium text-secondary uppercase tracking-wide mb-4">Processing Pipeline</h2>

        <div className="border border-border p-6">
          <pre className="text-xs font-mono overflow-x-auto">
{`Placetel API                    ElevenLabs                   OpenRouter
     │                              │                            │
     │  GET /calls                  │                            │
     │  filter[type]=voicemail      │                            │
     ▼                              │                            │
┌─────────┐                         │                            │
│  Sync   │  Download MP3           │                            │
│         │  if duration >= 2s      │                            │
└────┬────┘                         │                            │
     │                              │                            │
     │  status: pending             │                            │
     ▼                              ▼                            │
┌─────────┐                   ┌──────────┐                       │
│Transcribe│ ───────────────► │ Scribe   │                       │
│         │   POST /speech-   │   v2     │                       │
└────┬────┘   to-text         └────┬─────┘                       │
     │                              │                            │
     │  status: completed           │ text, language,            │
     │  transcription_text          │ confidence                 │
     ▼                              ▼                            ▼
┌─────────┐                                               ┌───────────┐
│Summarize│ ─────────────────────────────────────────────►│ Gemini 3  │
│         │   POST /chat/completions                      │   Pro     │
└────┬────┘                                               └─────┬─────┘
     │                                                          │
     │  corrected_text                                          │
     │  summary                                                 │
     ▼                                                          │
┌─────────┐                                                     │
│  Done   │◄────────────────────────────────────────────────────┘
└─────────┘`}
          </pre>
        </div>
      </section>

      {/* API Endpoints */}
      <section>
        <h2 className="text-xs font-medium text-secondary uppercase tracking-wide mb-4">API Endpoints</h2>

        <div className="border border-border divide-y divide-border text-sm">
          <EndpointRow method="GET" path="/voicemails" description="List all voicemails with pagination" />
          <EndpointRow method="GET" path="/voicemails/{id}" description="Get single voicemail details" />
          <EndpointRow method="GET" path="/voicemails/{id}/audio" description="Stream MP3 audio file" />
          <EndpointRow method="DELETE" path="/voicemails/{id}" description="Delete voicemail and audio" />
          <EndpointRow method="POST" path="/sync?days=30" description="Fetch voicemails from Placetel" />
          <EndpointRow method="POST" path="/voicemails/{id}/transcribe" description="Transcribe single voicemail" />
          <EndpointRow method="POST" path="/transcribe-pending" description="Transcribe all pending" />
          <EndpointRow method="POST" path="/voicemails/{id}/summarize" description="Summarize single voicemail" />
          <EndpointRow method="POST" path="/summarize-pending" description="Summarize all transcribed" />
          <EndpointRow method="GET" path="/health" description="System health check" />
        </div>
      </section>
    </div>
  );
}

function FieldRow({ name, type, description }: { name: string; type: string; description: string }) {
  return (
    <div className="p-4 grid grid-cols-12 gap-4 text-sm">
      <div className="col-span-3 font-mono">{name}</div>
      <div className="col-span-2 text-secondary font-mono text-xs">{type}</div>
      <div className="col-span-7 text-secondary">{description}</div>
    </div>
  );
}

function EndpointRow({ method, path, description }: { method: string; path: string; description: string }) {
  return (
    <div className="p-4 grid grid-cols-12 gap-4">
      <div className="col-span-1">
        <span className={`font-mono text-xs ${method === 'GET' ? 'text-secondary' : ''}`}>
          {method}
        </span>
      </div>
      <div className="col-span-5 font-mono text-sm">{path}</div>
      <div className="col-span-6 text-secondary text-sm">{description}</div>
    </div>
  );
}
