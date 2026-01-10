export interface Call {
  id: number;
  external_id: string;
  provider: string;

  // Call basics
  direction: 'in' | 'out';
  status: 'answered' | 'missed' | 'voicemail' | 'busy';
  from_number: string | null;
  from_name: string | null;
  to_number: string | null;
  to_number_name: string | null;
  duration: number | null;

  // Timing
  started_at: string | null;
  answered_at: string | null;
  ended_at: string | null;

  // Audio (voicemail)
  local_file_path: string | null;
  unread: boolean;

  // Transcription
  transcription_status: 'pending' | 'processing' | 'completed' | 'failed' | 'skipped';
  transcription_text: string | null;
  transcription_language: string | null;
  transcription_confidence: number | null;
  transcription_model: string | null;
  transcribed_at: string | null;

  // AI Processing
  corrected_text: string | null;
  summary: string | null;
  summary_en: string | null;
  summary_model: string | null;
  summarized_at: string | null;

  // Classification
  sentiment: 'positive' | 'negative' | 'neutral' | null;
  emotion: 'angry' | 'frustrated' | 'happy' | 'confused' | 'calm' | 'urgent' | null;
  category: 'sales_inquiry' | 'existing_order' | 'new_inquiry' | 'complaint' | 'general' | null;
  priority: 'low' | 'default' | 'high' | null;

  // Helpdesk
  email_status: 'pending' | 'sent' | 'failed' | 'skipped';
  email_sent_at: string | null;

  // Metadata
  created_at: string | null;
  updated_at: string | null;

  // Computed
  listen_url: string | null;
}

// Backwards compatibility
export type Voicemail = Call;

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
  calls_count: number;
  voicemails_count: number;
  scheduler: string;
  last_sync_at: string | null;
}

export interface PhoneNumber {
  id: string;
  number: string;
  name: string | null;
  type: string | null;
}

export interface NumbersResponse {
  numbers: PhoneNumber[];
  cached_at: string | null;
}
