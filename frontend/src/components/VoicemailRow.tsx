import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { Voicemail } from '../types';
import Badge from './Badge';
import Button from './Button';

interface VoicemailRowProps {
  voicemail: Voicemail;
  onTranscribe: (id: number) => Promise<void>;
  onSummarize: (id: number) => Promise<void>;
}

function formatPhoneNumber(phone: string | null): string {
  if (!phone) return '—';
  // Already has + prefix
  if (phone.startsWith('+')) return phone;
  // German number starting with 0
  if (phone.startsWith('0') && !phone.startsWith('00')) {
    return '+49 ' + phone.slice(1);
  }
  // International with 00 prefix
  if (phone.startsWith('00')) {
    return '+' + phone.slice(2);
  }
  return phone;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === 0) return '0s';
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function getLanguageLabel(code: string | null): string {
  if (!code) return '—';
  const languages: Record<string, string> = {
    'deu': 'DE',
    'eng': 'EN',
    'fra': 'FR',
    'spa': 'ES',
    'ita': 'IT',
    'nld': 'NL',
    'pol': 'PL',
    'por': 'PT',
    'rus': 'RU',
    'tur': 'TR',
    'ara': 'AR',
    'zho': 'ZH',
    'jpn': 'JP',
  };
  return languages[code] || code.toUpperCase().slice(0, 2);
}

const SKIP_TEXTS = ['[No audio]', '[Too short]', '[No audio content]', '[No meaningful content]'];

function isSkipped(voicemail: Voicemail): boolean {
  return voicemail.transcription_status === 'skipped' ||
    (voicemail.duration !== null && voicemail.duration < 2) ||
    SKIP_TEXTS.includes(voicemail.transcription_text || '');
}

function getStatus(voicemail: Voicemail): { label: string; variant: 'default' | 'success' | 'warning' | 'error' | 'muted' } {
  if (isSkipped(voicemail)) {
    return { label: 'Skipped', variant: 'muted' };
  }
  if (voicemail.summary && !SKIP_TEXTS.includes(voicemail.summary)) {
    return { label: 'Summarized', variant: 'success' };
  }
  if (voicemail.transcription_status === 'completed' && voicemail.transcription_text && !SKIP_TEXTS.includes(voicemail.transcription_text)) {
    return { label: 'Transcribed', variant: 'warning' };
  }
  if (voicemail.transcription_status === 'processing') {
    return { label: 'Processing', variant: 'default' };
  }
  if (voicemail.transcription_status === 'failed') {
    return { label: 'Failed', variant: 'error' };
  }
  return { label: 'Pending', variant: 'default' };
}

export default function VoicemailRow({ voicemail, onTranscribe, onSummarize }: VoicemailRowProps) {
  const [transcribing, setTranscribing] = useState(false);
  const [summarizing, setSummarizing] = useState(false);

  const skipped = isSkipped(voicemail);
  const status = getStatus(voicemail);

  const canTranscribe = !skipped &&
    (voicemail.transcription_status === 'pending' || voicemail.transcription_status === 'failed');

  const canSummarize = !skipped &&
    voicemail.transcription_status === 'completed' &&
    voicemail.transcription_text &&
    !SKIP_TEXTS.includes(voicemail.transcription_text) &&
    (!voicemail.summary || SKIP_TEXTS.includes(voicemail.summary));

  const handleTranscribe = async () => {
    setTranscribing(true);
    try {
      await onTranscribe(voicemail.id);
    } finally {
      setTranscribing(false);
    }
  };

  const handleSummarize = async () => {
    setSummarizing(true);
    try {
      await onSummarize(voicemail.id);
    } finally {
      setSummarizing(false);
    }
  };

  return (
    <div className={`grid grid-cols-12 gap-4 px-4 py-3 border-b border-border hover:bg-hover transition-colors duration-150 text-sm ${skipped ? 'opacity-50' : ''}`}>
      {/* From */}
      <div className="col-span-3 flex items-center gap-2">
        <Link to={`/voicemail/${voicemail.id}`} className="hover:underline font-medium truncate">
          {formatPhoneNumber(voicemail.from_number)}
        </Link>
        {voicemail.transcription_language && (
          <span className="text-xs text-secondary px-1 border border-border">
            {getLanguageLabel(voicemail.transcription_language)}
          </span>
        )}
      </div>

      {/* To */}
      <div className="col-span-3 truncate text-secondary">
        {voicemail.to_number_name || formatPhoneNumber(voicemail.to_number)}
      </div>

      {/* Duration */}
      <div className="col-span-1 text-secondary tabular-nums">
        {formatDuration(voicemail.duration)}
      </div>

      {/* Status */}
      <div className="col-span-2">
        <Badge variant={status.variant}>{status.label}</Badge>
      </div>

      {/* Actions */}
      <div className="col-span-3 flex items-center justify-end gap-2">
        {canTranscribe && (
          <Button size="sm" variant="secondary" onClick={handleTranscribe} loading={transcribing}>
            Transcribe
          </Button>
        )}
        {canSummarize && (
          <Button size="sm" variant="secondary" onClick={handleSummarize} loading={summarizing}>
            Summarize
          </Button>
        )}
        <Link
          to={`/voicemail/${voicemail.id}`}
          className="text-xs text-secondary hover:text-black transition-colors duration-150"
        >
          View
        </Link>
      </div>
    </div>
  );
}
