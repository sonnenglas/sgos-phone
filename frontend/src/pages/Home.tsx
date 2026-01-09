import { useState, useEffect } from 'react';
import { api } from '../api';
import type { Voicemail } from '../types';
import VoicemailRow from '../components/VoicemailRow';
import Button from '../components/Button';

export default function Home() {
  const [voicemails, setVoicemails] = useState<Voicemail[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncDays, setSyncDays] = useState(30);
  const [message, setMessage] = useState<string | null>(null);

  const fetchVoicemails = async () => {
    try {
      const data = await api.listVoicemails({ limit: 100 });
      setVoicemails(data);
    } catch (error) {
      console.error('Failed to fetch voicemails:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVoicemails();
  }, []);

  const handleSync = async () => {
    setSyncing(true);
    setMessage(null);
    try {
      const result = await api.sync(syncDays);
      if (result.new > 0) {
        setMessage(`Found ${result.new} new voicemails`);
      } else {
        setMessage('No new voicemails');
      }
      fetchVoicemails();
    } catch (error) {
      setMessage('Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  const handleTranscribe = async (id: number) => {
    try {
      await api.transcribeOne(id);
      fetchVoicemails();
    } catch (error) {
      console.error('Transcription failed:', error);
    }
  };

  const handleSummarize = async (id: number) => {
    try {
      await api.summarizeOne(id);
      fetchVoicemails();
    } catch (error) {
      console.error('Summarization failed:', error);
    }
  };

  const SKIP_TEXTS = ['[No audio]', '[Too short]', '[No audio content]', '[No meaningful content]'];

  const stats = {
    total: voicemails.length,
    skipped: voicemails.filter(v =>
      v.transcription_status === 'skipped' ||
      (v.duration !== null && v.duration < 2)
    ).length,
    pending: voicemails.filter(v =>
      v.transcription_status === 'pending' &&
      (v.duration === null || v.duration >= 2)
    ).length,
    transcribed: voicemails.filter(v =>
      v.transcription_status === 'completed' &&
      !v.summary &&
      !SKIP_TEXTS.includes(v.transcription_text || '')
    ).length,
    summarized: voicemails.filter(v =>
      v.summary && !SKIP_TEXTS.includes(v.summary)
    ).length,
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <span className="text-secondary">Loading...</span>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight mb-2">Messages</h1>
          <p className="text-secondary">
            {stats.total} total · {stats.summarized} summarized · {stats.transcribed} transcribed · {stats.pending} pending{stats.skipped > 0 ? ` · ${stats.skipped} skipped` : ''}
          </p>
        </div>
      </div>

      {/* Sync Controls */}
      <div className="mb-8 p-4 border border-border">
        <div className="flex items-center gap-4">
          <span className="text-sm text-secondary">Sync last</span>
          <select
            value={syncDays}
            onChange={(e) => setSyncDays(parseInt(e.target.value))}
            className="border border-border px-3 py-1.5 text-sm bg-white hover:border-black transition-colors duration-150"
          >
            <option value={7}>7 days</option>
            <option value={30}>30 days</option>
            <option value={60}>60 days</option>
            <option value={90}>90 days</option>
            <option value={180}>180 days</option>
            <option value={365}>365 days</option>
          </select>
          <Button variant="primary" onClick={handleSync} loading={syncing}>
            Sync from Placetel
          </Button>
          {message && (
            <span className="text-sm text-secondary">{message}</span>
          )}
        </div>
      </div>

      {/* Voicemail list */}
      {voicemails.length === 0 ? (
        <div className="text-center py-24 border border-border">
          <p className="text-secondary mb-4">No voicemails yet</p>
          <Button onClick={handleSync} loading={syncing}>
            Sync from Placetel
          </Button>
        </div>
      ) : (
        <div className="border border-border">
          {/* Table Header */}
          <div className="grid grid-cols-12 gap-4 px-4 py-3 border-b border-border text-xs font-medium text-secondary uppercase tracking-wide">
            <div className="col-span-3">From</div>
            <div className="col-span-3">To</div>
            <div className="col-span-1">Duration</div>
            <div className="col-span-2">Status</div>
            <div className="col-span-3 text-right">Actions</div>
          </div>

          {/* Table Body */}
          {voicemails.map((voicemail) => (
            <VoicemailRow
              key={voicemail.id}
              voicemail={voicemail}
              onTranscribe={handleTranscribe}
              onSummarize={handleSummarize}
            />
          ))}
        </div>
      )}
    </div>
  );
}
