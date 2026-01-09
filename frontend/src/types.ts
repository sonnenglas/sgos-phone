export interface Voicemail {
  id: number;
  from_number: string | null;
  to_number: string | null;
  to_number_name: string | null;
  duration: number | null;
  received_at: string | null;
  unread: boolean;
  local_file_path: string | null;
  transcription_status: 'pending' | 'processing' | 'completed' | 'failed' | 'skipped';
  transcription_text: string | null;
  transcription_language: string | null;
  transcription_confidence: number | null;
  transcribed_at: string | null;
  corrected_text: string | null;
  summary: string | null;
  summary_model: string | null;
  summarized_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface SyncResponse {
  synced: number;
  new: number;
  updated: number;
  downloaded: number;
}

export interface TranscribeResponse {
  transcribed: number;
  failed: number;
  skipped: number;
}

export interface SummarizeResponse {
  summarized: number;
  failed: number;
  skipped: number;
}

export interface HealthResponse {
  status: string;
  database: string;
  voicemails_count: number;
}
