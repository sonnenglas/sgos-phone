import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { api } from '../api';
import type { Voicemail } from '../types';
import Button from '../components/Button';
import Badge from '../components/Badge';
import AudioPlayer from '../components/AudioPlayer';

function formatDateTime(dateString: string | null): string {
  if (!dateString) return '—';
  const date = new Date(dateString);
  return date.toLocaleDateString('de-DE', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatDuration(seconds: number | null): string {
  if (!seconds) return '0 seconds';
  if (seconds < 60) return `${seconds} seconds`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export default function VoicemailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [voicemail, setVoicemail] = useState<Voicemail | null>(null);
  const [loading, setLoading] = useState(true);
  const [transcribing, setTranscribing] = useState(false);
  const [summarizing, setSummarizing] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);

  const fetchVoicemail = async () => {
    if (!id) return;
    try {
      const data = await api.getVoicemail(parseInt(id));
      setVoicemail(data);
    } catch (error) {
      console.error('Failed to fetch voicemail:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVoicemail();
  }, [id]);

  const handleTranscribe = async () => {
    if (!id) return;
    setTranscribing(true);
    try {
      await api.transcribeOne(parseInt(id));
      fetchVoicemail();
    } catch (error) {
      console.error('Transcription failed:', error);
    } finally {
      setTranscribing(false);
    }
  };

  const handleSummarize = async () => {
    if (!id) return;
    setSummarizing(true);
    try {
      await api.summarizeOne(parseInt(id));
      fetchVoicemail();
    } catch (error) {
      console.error('Summarization failed:', error);
    } finally {
      setSummarizing(false);
    }
  };

  const handleDelete = async () => {
    if (!id || !confirm('Delete this voicemail?')) return;
    try {
      await api.deleteVoicemail(parseInt(id));
      navigate('/');
    } catch (error) {
      console.error('Delete failed:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <span className="text-secondary">Loading...</span>
      </div>
    );
  }

  if (!voicemail) {
    return (
      <div className="text-center py-24">
        <p className="text-secondary mb-4">Voicemail not found</p>
        <Link to="/" className="text-black underline">
          Back to messages
        </Link>
      </div>
    );
  }

  const canTranscribe = voicemail.transcription_status === 'pending' || voicemail.transcription_status === 'failed';
  const canSummarize = voicemail.transcription_status === 'completed' && !voicemail.summary &&
    voicemail.transcription_text !== '[No audio content]';

  return (
    <div className="animate-fade-in">
      {/* Back link */}
      <Link to="/" className="inline-block text-secondary hover:text-black transition-colors duration-150 mb-8">
        &larr; Back to messages
      </Link>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-2xl font-semibold tracking-tight">
            {voicemail.from_number || 'Unknown caller'}
          </h1>
          {voicemail.summary ? (
            <Badge variant="success">Summarized</Badge>
          ) : voicemail.transcription_status === 'completed' ? (
            <Badge variant="warning">Transcribed</Badge>
          ) : (
            <Badge variant="default">{voicemail.transcription_status}</Badge>
          )}
        </div>
        <p className="text-secondary">
          To: {voicemail.to_number_name || voicemail.to_number}
        </p>
      </div>

      {/* Meta info */}
      <div className="flex gap-8 mb-8 text-sm">
        <div>
          <span className="text-secondary">Received</span>
          <p className="mt-1">{formatDateTime(voicemail.received_at)}</p>
        </div>
        <div>
          <span className="text-secondary">Duration</span>
          <p className="mt-1">{formatDuration(voicemail.duration)}</p>
        </div>
        {voicemail.transcription_language && (
          <div>
            <span className="text-secondary">Language</span>
            <p className="mt-1">{voicemail.transcription_language.toUpperCase()}</p>
          </div>
        )}
      </div>

      {/* Audio player */}
      {voicemail.local_file_path && (
        <div className="mb-12 p-4 border border-border">
          <AudioPlayer
            src={api.getAudioUrl(voicemail.id)}
            duration={voicemail.duration || undefined}
          />
        </div>
      )}

      {/* Summary */}
      {voicemail.summary && (
        <div className="mb-8">
          <h2 className="text-xs font-medium text-secondary uppercase tracking-wide mb-3">
            Summary
          </h2>
          <div className="p-4 bg-hover">
            <p className="leading-relaxed">{voicemail.summary}</p>
          </div>
        </div>
      )}

      {/* Classification */}
      {(voicemail.sentiment || voicemail.category || voicemail.is_urgent) && (
        <div className="mb-8">
          <h2 className="text-xs font-medium text-secondary uppercase tracking-wide mb-3">
            Classification
          </h2>
          <div className="flex flex-wrap gap-4 p-4 border border-border">
            {voicemail.is_urgent && (
              <div>
                <span className="text-xs text-secondary block mb-1">Priority</span>
                <Badge variant="urgent">Urgent</Badge>
              </div>
            )}
            {voicemail.sentiment && (
              <div>
                <span className="text-xs text-secondary block mb-1">Sentiment</span>
                <Badge variant={voicemail.sentiment === 'negative' ? 'negative' : voicemail.sentiment === 'positive' ? 'positive' : 'default'}>
                  {voicemail.sentiment.charAt(0).toUpperCase() + voicemail.sentiment.slice(1)}
                </Badge>
              </div>
            )}
            {voicemail.emotion && (
              <div>
                <span className="text-xs text-secondary block mb-1">Emotion</span>
                <Badge variant="default">
                  {voicemail.emotion.charAt(0).toUpperCase() + voicemail.emotion.slice(1)}
                </Badge>
              </div>
            )}
            {voicemail.category && (
              <div>
                <span className="text-xs text-secondary block mb-1">Category</span>
                <Badge variant="info">
                  {voicemail.category.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                </Badge>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Transcript */}
      {voicemail.transcription_text && voicemail.transcription_text !== '[No audio content]' && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-medium text-secondary uppercase tracking-wide">
              {voicemail.corrected_text ? 'Corrected Transcript' : 'Transcript'}
            </h2>
            {voicemail.corrected_text && (
              <button
                onClick={() => setShowOriginal(!showOriginal)}
                className="text-xs text-secondary hover:text-black transition-colors duration-150"
              >
                {showOriginal ? 'Show corrected' : 'Show original'}
              </button>
            )}
          </div>
          <div className="p-4 border border-border">
            <p className="leading-relaxed whitespace-pre-wrap">
              {showOriginal ? voicemail.transcription_text : (voicemail.corrected_text || voicemail.transcription_text)}
            </p>
          </div>
          {voicemail.transcription_confidence && (
            <p className="text-xs text-secondary mt-2">
              Confidence: {(voicemail.transcription_confidence * 100).toFixed(1)}%
            </p>
          )}
        </div>
      )}

      {/* No transcript message */}
      {(!voicemail.transcription_text || voicemail.transcription_text === '[No audio content]') && (
        <div className="mb-8 p-4 border border-border text-center text-secondary">
          {voicemail.transcription_text === '[No audio content]'
            ? 'This voicemail has no audio content'
            : 'No transcription available'}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 pt-8 border-t border-border">
        {canTranscribe && (
          <Button variant="primary" onClick={handleTranscribe} loading={transcribing}>
            Transcribe
          </Button>
        )}
        {canSummarize && (
          <Button variant="primary" onClick={handleSummarize} loading={summarizing}>
            Summarize
          </Button>
        )}
        <Button variant="secondary" onClick={handleDelete}>
          Delete
        </Button>
      </div>

      {/* Model info */}
      {voicemail.summary_model && (
        <p className="text-xs text-secondary mt-8">
          Summarized with {voicemail.summary_model}
        </p>
      )}
    </div>
  );
}
