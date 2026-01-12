import type { Voicemail, SyncResponse, TranscribeResponse, SummarizeResponse, HealthResponse, NumbersResponse } from './types';

const API_BASE = '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

export const api = {
  // Auth
  me: () => request<{ email: string | null }>('/me'),

  // Health
  health: () => request<HealthResponse>('/health'),

  // Voicemails
  listVoicemails: (params?: { status?: string; search?: string; skip?: number; limit?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.search) searchParams.set('search', params.search);
    if (params?.skip) searchParams.set('skip', params.skip.toString());
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    const query = searchParams.toString();
    return request<Voicemail[]>(`/voicemails${query ? `?${query}` : ''}`);
  },

  getVoicemail: (id: number) => request<Voicemail>(`/voicemails/${id}`),

  deleteVoicemail: (id: number) => request<{ deleted: number }>(`/voicemails/${id}`, { method: 'DELETE' }),

  getAudioUrl: (id: number) => `${API_BASE}/voicemails/${id}/audio`,

  getEmailPreviewUrl: (id: number) => `${API_BASE}/voicemails/${id}/email-preview`,

  getEmailPreviewHtml: async (id: number): Promise<string> => {
    const response = await fetch(`${API_BASE}/voicemails/${id}/email-preview`);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return response.text();
  },

  getEmailPreviewText: async (id: number): Promise<string> => {
    const response = await fetch(`${API_BASE}/voicemails/${id}/email-preview-text`);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return response.text();
  },

  // Sync
  sync: (days: number = 30) => request<SyncResponse>(`/sync?days=${days}`, { method: 'POST' }),

  // Transcribe
  transcribeOne: (id: number) => request<{ id: number; status: string; text?: string; error?: string }>(
    `/voicemails/${id}/transcribe`,
    { method: 'POST' }
  ),

  transcribePending: (limit: number = 10) => request<TranscribeResponse>(
    `/transcribe-pending?limit=${limit}`,
    { method: 'POST' }
  ),

  // Summarize
  summarizeOne: (id: number) => request<{ id: number; status: string; summary?: string; error?: string }>(
    `/voicemails/${id}/summarize`,
    { method: 'POST' }
  ),

  summarizePending: (limit: number = 10) => request<SummarizeResponse>(
    `/summarize-pending?limit=${limit}`,
    { method: 'POST' }
  ),

  // Settings
  getSettings: () => request<{ settings: Record<string, string> }>('/settings'),

  updateSetting: (key: string, value: string) => request<{ key: string; value: string }>(
    `/settings/${key}`,
    { method: 'PUT', body: JSON.stringify({ value }) }
  ),

  syncNow: () => request<{ status: string; result: unknown }>('/settings/sync-now', { method: 'POST' }),

  reprocess: (id: number) => request<{ voicemail_id: number; steps: string[] }>(
    `/settings/reprocess/${id}`,
    { method: 'POST' }
  ),

  sendEmail: (id: number) => request<{ status: string; to: string; voicemail_id: number }>(
    `/settings/send-email/${id}`,
    { method: 'POST' }
  ),

  setEmailCutoffNow: () => request<{ cutoff_date: string; skipped_count: number; message: string }>(
    '/settings/email-cutoff-now',
    { method: 'POST' }
  ),

  // Numbers
  listNumbers: (refresh: boolean = false) => request<NumbersResponse>(`/numbers${refresh ? '?refresh=true' : ''}`),
};
