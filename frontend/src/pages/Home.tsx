import { useState, useEffect, useRef } from 'react';
import { api } from '../api';
import type { Voicemail, HealthResponse } from '../types';
import Badge from '../components/Badge';
import Button from '../components/Button';
import AudioPlayer from '../components/AudioPlayer';

function formatDate(dateString: string | null): string {
  if (!dateString) return '—';
  const date = new Date(dateString);
  return date.toLocaleDateString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
  });
}

function formatTime(dateString: string | null): string {
  if (!dateString) return '';
  const date = new Date(dateString);
  return date.toLocaleTimeString('de-DE', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return 'Never';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === 0) return '—';
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatPhoneNumber(phone: string | null): string {
  if (!phone) return 'Unknown';
  if (phone.startsWith('+')) return phone;
  if (phone.startsWith('0') && !phone.startsWith('00')) {
    return '+49 ' + phone.slice(1);
  }
  if (phone.startsWith('00')) {
    return '+' + phone.slice(2);
  }
  return phone;
}

const SKIP_TEXTS = ['[No audio]', '[Too short]', '[No audio content]', '[No meaningful content]'];

function isSkipped(voicemail: Voicemail): boolean {
  return voicemail.transcription_status === 'skipped' ||
    (voicemail.duration !== null && voicemail.duration < 2) ||
    SKIP_TEXTS.includes(voicemail.transcription_text || '');
}

function getStatusInfo(voicemail: Voicemail): { label: string; variant: 'default' | 'success' | 'warning' | 'error' | 'muted' } {
  if (isSkipped(voicemail)) return { label: 'Skipped', variant: 'muted' };
  if (voicemail.summary && !SKIP_TEXTS.includes(voicemail.summary)) return { label: 'Ready', variant: 'success' };
  if (voicemail.transcription_status === 'completed') return { label: 'Transcribed', variant: 'warning' };
  if (voicemail.transcription_status === 'processing') return { label: 'Processing', variant: 'default' };
  if (voicemail.transcription_status === 'failed') return { label: 'Failed', variant: 'error' };
  return { label: 'Pending', variant: 'default' };
}

function getEmailStatusInfo(voicemail: Voicemail): { label: string; variant: 'default' | 'success' | 'warning' | 'error' | 'muted' } | null {
  if (isSkipped(voicemail)) return null;
  if (voicemail.email_status === 'sent') return { label: 'Sent', variant: 'success' };
  if (voicemail.email_status === 'failed') return { label: 'Failed', variant: 'error' };
  if (voicemail.email_status === 'pending' && voicemail.summary) return { label: 'Queued', variant: 'warning' };
  return null;
}

function getCategoryLabel(category: string | null): string {
  const labels: Record<string, string> = {
    sales_inquiry: 'Sales',
    existing_order: 'Order',
    new_inquiry: 'New Lead',
    complaint: 'Complaint',
    general: 'General',
  };
  return labels[category || ''] || '';
}

export default function Home() {
  const [voicemails, setVoicemails] = useState<Voicemail[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [showSkipped, setShowSkipped] = useState(false);
  const [selectedVoicemail, setSelectedVoicemail] = useState<Voicemail | null>(null);
  const [transcribing, setTranscribing] = useState(false);
  const [summarizing, setSummarizing] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [sendingEmail, setSendingEmail] = useState(false);

  // Audio playback state for inline play button
  const [playingId, setPlayingId] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  // Email preview modal state
  const [showEmailPreview, setShowEmailPreview] = useState(false);
  const [emailPreviewTab, setEmailPreviewTab] = useState<'html' | 'text'>('html');
  const [emailPreviewHtml, setEmailPreviewHtml] = useState<string>('');
  const [emailPreviewText, setEmailPreviewText] = useState<string>('');
  const [loadingEmailPreview, setLoadingEmailPreview] = useState(false);

  const fetchData = async () => {
    try {
      const [voicemailData, healthData] = await Promise.all([
        api.listVoicemails({ limit: 200 }),
        api.health(),
      ]);
      setVoicemails(voicemailData);
      setHealth(healthData);
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleSyncNow = async () => {
    setSyncing(true);
    try {
      await api.syncNow();
      await fetchData();
    } catch (error) {
      console.error('Sync failed:', error);
    } finally {
      setSyncing(false);
    }
  };

  const handleTranscribe = async () => {
    if (!selectedVoicemail) return;
    setTranscribing(true);
    try {
      await api.transcribeOne(selectedVoicemail.id);
      await fetchData();
      const updated = voicemails.find(v => v.id === selectedVoicemail.id);
      if (updated) setSelectedVoicemail(updated);
      else {
        const fresh = await api.getVoicemail(selectedVoicemail.id);
        setSelectedVoicemail(fresh);
      }
    } finally {
      setTranscribing(false);
    }
  };

  const handleSummarize = async () => {
    if (!selectedVoicemail) return;
    setSummarizing(true);
    try {
      await api.summarizeOne(selectedVoicemail.id);
      await fetchData();
      const fresh = await api.getVoicemail(selectedVoicemail.id);
      setSelectedVoicemail(fresh);
    } finally {
      setSummarizing(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedVoicemail || !confirm('Delete this voicemail?')) return;
    try {
      await api.deleteVoicemail(selectedVoicemail.id);
      setSelectedVoicemail(null);
      await fetchData();
    } catch (error) {
      console.error('Delete failed:', error);
    }
  };

  const handleReprocess = async () => {
    if (!selectedVoicemail || !confirm('Reprocess this voicemail? This will re-transcribe, re-summarize, and send a new email.')) return;
    setReprocessing(true);
    try {
      await api.reprocess(selectedVoicemail.id);
      await fetchData();
      const fresh = await api.getVoicemail(selectedVoicemail.id);
      setSelectedVoicemail(fresh);
    } catch (error) {
      console.error('Reprocess failed:', error);
    } finally {
      setReprocessing(false);
    }
  };

  const handleSendEmail = async () => {
    if (!selectedVoicemail || !confirm('Send email notification for this voicemail?')) return;
    setSendingEmail(true);
    try {
      await api.sendEmail(selectedVoicemail.id);
      await fetchData();
      const fresh = await api.getVoicemail(selectedVoicemail.id);
      setSelectedVoicemail(fresh);
    } catch (error) {
      console.error('Send email failed:', error);
      alert('Failed to send email. Check settings.');
    } finally {
      setSendingEmail(false);
    }
  };

  // Open email preview modal
  const openEmailPreview = async (id: number) => {
    setLoadingEmailPreview(true);
    setShowEmailPreview(true);
    setEmailPreviewTab('html');
    try {
      const [html, text] = await Promise.all([
        api.getEmailPreviewHtml(id),
        api.getEmailPreviewText(id),
      ]);
      setEmailPreviewHtml(html);
      setEmailPreviewText(text);
    } catch (error) {
      console.error('Failed to load email preview:', error);
      setEmailPreviewHtml('<p>Failed to load preview</p>');
      setEmailPreviewText('Failed to load preview');
    } finally {
      setLoadingEmailPreview(false);
    }
  };

  // Toggle audio playback for a voicemail
  const togglePlay = (id: number) => {
    const audio = audioRef.current;
    if (!audio) return;

    if (playingId === id) {
      // Currently playing this one - pause it
      audio.pause();
      setPlayingId(null);
    } else {
      // Play new audio
      audio.src = api.getAudioUrl(id);
      audio.play().catch(console.error);
      setPlayingId(id);
    }
  };

  const filteredVoicemails = showSkipped
    ? voicemails
    : voicemails.filter(v => !isSkipped(v));

  const stats = {
    total: voicemails.filter(v => !isSkipped(v)).length,
    pending: voicemails.filter(v => !isSkipped(v) && v.transcription_status === 'pending').length,
    ready: voicemails.filter(v => v.summary && !SKIP_TEXTS.includes(v.summary)).length,
    queued: voicemails.filter(v => v.email_status === 'pending' && v.summary && !SKIP_TEXTS.includes(v.summary)).length,
    sent: voicemails.filter(v => v.email_status === 'sent').length,
    skipped: voicemails.filter(v => isSkipped(v)).length,
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
      {/* Hidden audio element for inline playback */}
      <audio
        ref={audioRef}
        onEnded={() => setPlayingId(null)}
        onError={() => setPlayingId(null)}
      />

      {/* Dashboard Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-semibold tracking-tight">Voicemails</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-secondary">
              Last sync: {formatRelativeTime(health?.last_sync_at || null)}
            </span>
            <Button variant="primary" onClick={handleSyncNow} loading={syncing}>
              Sync Now
            </Button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-5 gap-4 mb-6">
          <div className="p-4 border border-border">
            <div className="text-2xl font-semibold">{stats.total}</div>
            <div className="text-sm text-secondary">Total</div>
          </div>
          <div className="p-4 border border-border">
            <div className="text-2xl font-semibold">{stats.ready}</div>
            <div className="text-sm text-secondary">Ready</div>
          </div>
          <div className="p-4 border border-border">
            <div className="text-2xl font-semibold">{stats.pending}</div>
            <div className="text-sm text-secondary">Pending</div>
          </div>
          <div className="p-4 border border-border">
            <div className="text-2xl font-semibold">{stats.queued}</div>
            <div className="text-sm text-secondary">Queued</div>
          </div>
          <div className="p-4 border border-border">
            <div className="text-2xl font-semibold">{stats.sent}</div>
            <div className="text-sm text-secondary">Sent</div>
          </div>
        </div>

        {/* Legend */}
        <div className="text-xs text-secondary mb-4 p-3 bg-hover border border-border">
          <strong>Processing pipeline:</strong>{' '}
          <span className="text-black">Pending</span> → Transcribe (ElevenLabs) →{' '}
          <span className="text-black">Transcribed</span> → Summarize (AI) →{' '}
          <span className="text-black">Ready</span> → Email notification →{' '}
          <span className="text-black">Sent</span>
        </div>

        {/* Filter */}
        <div className="flex items-center gap-2 text-sm">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={showSkipped}
              onChange={(e) => setShowSkipped(e.target.checked)}
              className="rounded border-border"
            />
            <span className="text-secondary">Show skipped ({stats.skipped})</span>
          </label>
        </div>
      </div>

      {/* Table */}
      {filteredVoicemails.length === 0 ? (
        <div className="text-center py-24 border border-border">
          <p className="text-secondary">No voicemails</p>
        </div>
      ) : (
        <div className="border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs font-medium text-secondary uppercase tracking-wide">
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">From</th>
                <th className="px-4 py-3">Summary</th>
                <th className="px-4 py-3 text-center">Duration</th>
                <th className="px-4 py-3 text-center">Status</th>
                <th className="px-4 py-3 text-center">Email</th>
                <th className="px-4 py-3 text-center">Listen</th>
              </tr>
            </thead>
            <tbody>
              {filteredVoicemails.map((voicemail) => {
                const status = getStatusInfo(voicemail);
                const emailStatus = getEmailStatusInfo(voicemail);
                const skipped = isSkipped(voicemail);

                return (
                  <tr
                    key={voicemail.id}
                    onClick={() => setSelectedVoicemail(voicemail)}
                    className={`border-b border-border hover:bg-hover cursor-pointer transition-colors duration-150 ${skipped ? 'opacity-40' : ''}`}
                  >
                    <td className="px-4 py-3 tabular-nums whitespace-nowrap">
                      <div>{formatDate(voicemail.started_at)}</div>
                      <div className="text-secondary text-xs">{formatTime(voicemail.started_at)}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium">{formatPhoneNumber(voicemail.from_number)}</div>
                      <div className="text-secondary text-xs">→ {voicemail.to_number_name || voicemail.to_number || '—'}</div>
                    </td>
                    <td className="px-4 py-3 max-w-lg">
                      {voicemail.email_subject && !skipped && (
                        <div className="font-medium text-xs mb-1">{voicemail.email_subject}</div>
                      )}
                      {voicemail.summary && !SKIP_TEXTS.includes(voicemail.summary) ? (
                        <div className="text-xs text-secondary line-clamp-3">{voicemail.summary}</div>
                      ) : skipped ? (
                        <span className="text-secondary italic text-xs">Skipped</span>
                      ) : (
                        <span className="text-secondary italic text-xs">Awaiting processing...</span>
                      )}
                      {voicemail.category && voicemail.category !== 'general' && (
                        <div className="mt-1">
                          <Badge variant="info" size="sm">{getCategoryLabel(voicemail.category)}</Badge>
                          {voicemail.priority === 'high' && <Badge variant="urgent" size="sm">High</Badge>}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center tabular-nums text-secondary">
                      {formatDuration(voicemail.duration)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <Badge variant={status.variant}>{status.label}</Badge>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {emailStatus ? (
                        <Badge variant={emailStatus.variant}>{emailStatus.label}</Badge>
                      ) : (
                        <span className="text-secondary">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {!skipped && voicemail.local_file_path && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            togglePlay(voicemail.id);
                          }}
                          className="w-8 h-8 flex items-center justify-center border border-border hover:bg-hover transition-colors duration-150"
                          aria-label={playingId === voicemail.id ? 'Pause' : 'Play'}
                        >
                          {playingId === voicemail.id ? (
                            <span className="text-sm">| |</span>
                          ) : (
                            <span className="text-sm ml-0.5">&#9654;</span>
                          )}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal */}
      {selectedVoicemail && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50"
          onClick={(e) => e.target === e.currentTarget && setSelectedVoicemail(null)}
        >
          <div className="bg-white w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-lg shadow-xl">
            {/* Modal Header */}
            <div className="sticky top-0 bg-white border-b border-border px-6 py-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">
                  {formatPhoneNumber(selectedVoicemail.from_number)}
                </h2>
                <p className="text-sm text-secondary">
                  {formatDate(selectedVoicemail.started_at)} at {formatTime(selectedVoicemail.started_at)}
                  → {selectedVoicemail.to_number_name || selectedVoicemail.to_number || '—'}
                </p>
              </div>
              <button
                onClick={() => setSelectedVoicemail(null)}
                className="text-secondary hover:text-black text-2xl leading-none"
              >
                &times;
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 space-y-6">
              {/* Audio */}
              {selectedVoicemail.local_file_path && (
                <div>
                  <AudioPlayer
                    src={api.getAudioUrl(selectedVoicemail.id)}
                    duration={selectedVoicemail.duration || undefined}
                  />
                </div>
              )}

              {/* Classification */}
              {(selectedVoicemail.sentiment || selectedVoicemail.category || selectedVoicemail.priority === 'high') && (
                <div className="flex flex-wrap gap-2">
                  {selectedVoicemail.priority === 'high' && <Badge variant="urgent">High Priority</Badge>}
                  {selectedVoicemail.sentiment && (
                    <Badge variant={selectedVoicemail.sentiment === 'negative' ? 'negative' : selectedVoicemail.sentiment === 'positive' ? 'positive' : 'default'}>
                      {selectedVoicemail.sentiment}
                    </Badge>
                  )}
                  {selectedVoicemail.emotion && <Badge variant="default">{selectedVoicemail.emotion}</Badge>}
                  {selectedVoicemail.category && <Badge variant="info">{getCategoryLabel(selectedVoicemail.category) || selectedVoicemail.category}</Badge>}
                </div>
              )}

              {/* Summary */}
              {selectedVoicemail.summary && !SKIP_TEXTS.includes(selectedVoicemail.summary) && (
                <div>
                  <h3 className="text-xs font-medium text-secondary uppercase tracking-wide mb-2">Summary</h3>
                  <div className="p-4 bg-hover">
                    {selectedVoicemail.summary}
                    {selectedVoicemail.summary_en && selectedVoicemail.summary_en !== selectedVoicemail.summary && (
                      <div className="mt-3 text-secondary italic">
                        <strong>English:</strong> {selectedVoicemail.summary_en}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Transcript */}
              {selectedVoicemail.transcription_text && !SKIP_TEXTS.includes(selectedVoicemail.transcription_text) && (
                <div>
                  <h3 className="text-xs font-medium text-secondary uppercase tracking-wide mb-2">
                    {selectedVoicemail.corrected_text ? 'Corrected Transcript' : 'Transcript'}
                  </h3>
                  <div className="p-4 border border-border text-sm whitespace-pre-wrap">
                    {selectedVoicemail.corrected_text || selectedVoicemail.transcription_text}
                  </div>
                </div>
              )}

              {/* Status Info */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-secondary">Status:</span>{' '}
                  <Badge variant={getStatusInfo(selectedVoicemail).variant}>
                    {getStatusInfo(selectedVoicemail).label}
                  </Badge>
                </div>
                <div>
                  <span className="text-secondary">Email:</span>{' '}
                  {getEmailStatusInfo(selectedVoicemail) ? (
                    <Badge variant={getEmailStatusInfo(selectedVoicemail)!.variant}>
                      {getEmailStatusInfo(selectedVoicemail)!.label}
                    </Badge>
                  ) : (
                    <span className="text-secondary">—</span>
                  )}
                </div>
                <div>
                  <span className="text-secondary">Duration:</span>{' '}
                  {formatDuration(selectedVoicemail.duration)}
                </div>
                {selectedVoicemail.transcription_language && (
                  <div>
                    <span className="text-secondary">Language:</span>{' '}
                    {selectedVoicemail.transcription_language.toUpperCase()}
                  </div>
                )}
              </div>

              {/* Email Details */}
              {(selectedVoicemail.email_status === 'sent' || selectedVoicemail.email_subject) && (
                <div className="border-t border-border pt-4">
                  <h3 className="text-xs font-medium text-secondary uppercase tracking-wide mb-2">Email Details</h3>
                  <div className="space-y-2 text-sm">
                    {selectedVoicemail.email_subject && (
                      <div>
                        <span className="text-secondary">Subject:</span>{' '}
                        <span className="font-medium">{selectedVoicemail.email_subject}</span>
                      </div>
                    )}
                    {selectedVoicemail.email_sent_at && (
                      <div>
                        <span className="text-secondary">Sent:</span>{' '}
                        {new Date(selectedVoicemail.email_sent_at).toLocaleString('de-DE')}
                      </div>
                    )}
                    {selectedVoicemail.email_message_id && (
                      <div>
                        <span className="text-secondary">Postmark ID:</span>{' '}
                        <code className="text-xs bg-hover px-1 py-0.5">{selectedVoicemail.email_message_id}</code>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="sticky bottom-0 bg-white border-t border-border px-6 py-4">
              <div className="flex items-center justify-between">
                {/* Left: Action buttons */}
                <div className="flex items-center gap-2">
                  {!isSkipped(selectedVoicemail) && selectedVoicemail.transcription_status === 'pending' && (
                    <Button variant="primary" onClick={handleTranscribe} loading={transcribing}>
                      Transcribe
                    </Button>
                  )}
                  {!isSkipped(selectedVoicemail) && selectedVoicemail.transcription_status === 'completed' && !selectedVoicemail.summary && (
                    <Button variant="primary" onClick={handleSummarize} loading={summarizing}>
                      Summarize
                    </Button>
                  )}
                  {!isSkipped(selectedVoicemail) && selectedVoicemail.summary && selectedVoicemail.email_status !== 'sent' && (
                    <Button variant="primary" onClick={handleSendEmail} loading={sendingEmail}>
                      Send Email
                    </Button>
                  )}
                  {!isSkipped(selectedVoicemail) && selectedVoicemail.local_file_path && (
                    <Button variant="ghost" onClick={handleReprocess} loading={reprocessing}>
                      Reprocess
                    </Button>
                  )}
                </div>

                {/* Right: Links and close */}
                <div className="flex items-center gap-2">
                  {!isSkipped(selectedVoicemail) && selectedVoicemail.listen_url && (
                    <a
                      href={selectedVoicemail.listen_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-secondary hover:text-black"
                    >
                      Listen Page ↗
                    </a>
                  )}
                  {!isSkipped(selectedVoicemail) && selectedVoicemail.summary && (
                    <button
                      onClick={() => openEmailPreview(selectedVoicemail.id)}
                      className="text-sm text-secondary hover:text-black"
                    >
                      Email Preview
                    </button>
                  )}
                  <div className="w-px h-6 bg-border mx-2" />
                  <Button variant="danger" size="sm" onClick={handleDelete}>
                    Delete
                  </Button>
                  <Button variant="secondary" onClick={() => setSelectedVoicemail(null)}>
                    Close
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Email Preview Modal */}
      {showEmailPreview && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-[60]"
          onClick={(e) => e.target === e.currentTarget && setShowEmailPreview(false)}
        >
          <div className="bg-white w-full max-w-4xl max-h-[90vh] overflow-hidden rounded-lg shadow-xl flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
              <div className="flex items-center gap-4">
                <h2 className="text-lg font-semibold">Email Preview</h2>
                <div className="flex border border-border rounded overflow-hidden">
                  <button
                    onClick={() => setEmailPreviewTab('html')}
                    className={`px-3 py-1 text-sm ${emailPreviewTab === 'html' ? 'bg-black text-white' : 'hover:bg-hover'}`}
                  >
                    HTML
                  </button>
                  <button
                    onClick={() => setEmailPreviewTab('text')}
                    className={`px-3 py-1 text-sm ${emailPreviewTab === 'text' ? 'bg-black text-white' : 'hover:bg-hover'}`}
                  >
                    Plain Text
                  </button>
                </div>
              </div>
              <button
                onClick={() => setShowEmailPreview(false)}
                className="text-secondary hover:text-black text-2xl leading-none"
              >
                &times;
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-auto">
              {loadingEmailPreview ? (
                <div className="flex items-center justify-center py-24">
                  <span className="text-secondary">Loading preview...</span>
                </div>
              ) : emailPreviewTab === 'html' ? (
                <iframe
                  srcDoc={emailPreviewHtml}
                  className="w-full h-full min-h-[600px] border-0"
                  title="Email HTML Preview"
                />
              ) : (
                <pre className="p-6 text-sm whitespace-pre-wrap font-mono bg-gray-50">{emailPreviewText}</pre>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
