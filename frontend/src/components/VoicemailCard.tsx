import { Link } from 'react-router-dom';
import type { Voicemail } from '../types';
import Badge from './Badge';

interface VoicemailCardProps {
  voicemail: Voicemail;
}

function formatDate(dateString: string | null): string {
  if (!dateString) return '—';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffHours = diffMs / (1000 * 60 * 60);

  if (diffHours < 24) {
    return date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  }
  if (diffHours < 48) {
    return 'Yesterday';
  }
  return date.toLocaleDateString('de-DE', { day: 'numeric', month: 'short' });
}

function formatDuration(seconds: number | null): string {
  if (!seconds) return '0s';
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

const SKIP_TEXTS = ['[No audio]', '[Too short]', '[No audio content]', '[Audio too short to transcribe]', '[No meaningful content]'];

function isSkipped(voicemail: Voicemail): boolean {
  return voicemail.transcription_status === 'skipped' ||
    (voicemail.duration !== null && voicemail.duration < 2) ||
    SKIP_TEXTS.includes(voicemail.transcription_text || '');
}

function getStatusBadge(voicemail: Voicemail) {
  if (isSkipped(voicemail)) {
    return <Badge variant="muted">Skipped</Badge>;
  }
  if (voicemail.summary && !SKIP_TEXTS.includes(voicemail.summary)) {
    return <Badge variant="success">Summarized</Badge>;
  }
  if (voicemail.transcription_status === 'completed') {
    return <Badge variant="warning">Transcribed</Badge>;
  }
  if (voicemail.transcription_status === 'processing') {
    return <Badge variant="default">Processing</Badge>;
  }
  if (voicemail.transcription_status === 'failed') {
    return <Badge variant="error">Failed</Badge>;
  }
  return <Badge variant="default">Pending</Badge>;
}

function getPreviewText(voicemail: Voicemail): { text: string; italic: boolean } {
  if (isSkipped(voicemail)) {
    const duration = voicemail.duration || 0;
    if (duration === 0) {
      return { text: 'No audio recorded', italic: true };
    }
    return { text: `Too short (${duration}s) — likely a hangup`, italic: true };
  }

  if (voicemail.summary && !SKIP_TEXTS.includes(voicemail.summary)) {
    return { text: voicemail.summary, italic: false };
  }

  if (voicemail.transcription_text && !SKIP_TEXTS.includes(voicemail.transcription_text)) {
    return { text: voicemail.transcription_text, italic: false };
  }

  return { text: 'Awaiting transcription', italic: true };
}

export default function VoicemailCard({ voicemail }: VoicemailCardProps) {
  const displayName = voicemail.to_number_name || voicemail.to_number || '—';
  const skipped = isSkipped(voicemail);
  const preview = getPreviewText(voicemail);

  return (
    <Link
      to={`/voicemail/${voicemail.id}`}
      className={`block border-b border-border py-4 hover:bg-hover transition-colors duration-150 -mx-4 px-4 ${skipped ? 'opacity-50' : ''}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-1">
            <span className={`font-medium truncate ${skipped ? 'text-secondary' : ''}`}>
              {voicemail.from_number || 'Unknown'}
            </span>
            {getStatusBadge(voicemail)}
          </div>

          <div className="text-sm text-secondary mb-2">
            To: {displayName}
          </div>

          <p className={`text-sm text-secondary line-clamp-2 ${preview.italic ? 'italic' : ''}`}>
            {preview.text}
          </p>
        </div>

        <div className="text-right flex-shrink-0">
          <div className="text-sm text-secondary">
            {formatDate(voicemail.received_at)}
          </div>
          <div className="text-sm text-secondary mt-1">
            {formatDuration(voicemail.duration)}
          </div>
        </div>
      </div>
    </Link>
  );
}
