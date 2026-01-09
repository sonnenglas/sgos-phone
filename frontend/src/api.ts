import type { Voicemail, SyncResponse, TranscribeResponse, SummarizeResponse, HealthResponse } from './types';

const API_BASE = '/api';

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
};
