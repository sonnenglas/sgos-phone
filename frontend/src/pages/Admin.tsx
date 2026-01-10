import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import type { HealthResponse } from '../types';

interface Settings {
  sync_interval_minutes: string;
  auto_transcribe: string;
  auto_summarize: string;
  auto_email: string;
  notification_email: string;
  email_only_after: string;
  last_sync_at: string;
}

function formatDateTimeLocal(isoString: string): string {
  if (!isoString) return '';
  const date = new Date(isoString);
  // Format as YYYY-MM-DDTHH:MM for datetime-local input
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

export default function Admin() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [healthData, settingsData] = await Promise.all([
        api.health(),
        api.getSettings(),
      ]);
      setHealth(healthData);
      setSettings(settingsData.settings as unknown as Settings);
    } catch (error) {
      console.error('Failed to load data:', error);
    }
  };

  const updateSetting = async (key: string, value: string) => {
    setSaving(true);
    try {
      await api.updateSetting(key, value);
      setSettings(prev => prev ? { ...prev, [key]: value } : null);
    } catch (error) {
      console.error('Failed to update setting:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleSyncNow = async () => {
    setSyncing(true);
    try {
      await api.syncNow();
      await loadData();
    } catch (error) {
      console.error('Failed to sync:', error);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="animate-fade-in">
      <Link to="/" className="inline-block text-secondary hover:text-black transition-colors duration-150 mb-8">
        &larr; Back to messages
      </Link>

      <h1 className="text-3xl font-semibold tracking-tight mb-8">Settings</h1>

      {/* System Status */}
      <section className="mb-12">
        <h2 className="text-xs font-medium text-secondary uppercase tracking-wide mb-4">System Status</h2>
        <div className="border border-border p-4">
          {health ? (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-6 text-sm">
              <div>
                <span className="text-secondary">Status</span>
                <p className="mt-1 font-medium">{health.status}</p>
              </div>
              <div>
                <span className="text-secondary">Database</span>
                <p className="mt-1 font-medium">{health.database}</p>
              </div>
              <div>
                <span className="text-secondary">Scheduler</span>
                <p className="mt-1 font-medium">{health.scheduler}</p>
              </div>
              <div>
                <span className="text-secondary">Voicemails</span>
                <p className="mt-1 font-medium">{health.voicemails_count}</p>
              </div>
              <div>
                <span className="text-secondary">Last Sync</span>
                <p className="mt-1 font-medium">
                  {health.last_sync_at ? new Date(health.last_sync_at).toLocaleString() : 'Never'}
                </p>
              </div>
            </div>
          ) : (
            <p className="text-secondary">Loading...</p>
          )}
        </div>
      </section>

      {/* Settings */}
      <section className="mb-12">
        <h2 className="text-xs font-medium text-secondary uppercase tracking-wide mb-4">Processing Settings</h2>
        <div className="border border-border divide-y divide-border">
          {/* Sync Interval */}
          <div className="p-4 flex items-center justify-between">
            <div>
              <p className="font-medium">Sync Interval</p>
              <p className="text-sm text-secondary">How often to fetch new voicemails from Placetel</p>
            </div>
            <select
              value={settings?.sync_interval_minutes || '15'}
              onChange={(e) => updateSetting('sync_interval_minutes', e.target.value)}
              disabled={saving}
              className="border border-border px-3 py-2 text-sm"
            >
              <option value="5">Every 5 minutes</option>
              <option value="10">Every 10 minutes</option>
              <option value="15">Every 15 minutes</option>
              <option value="30">Every 30 minutes</option>
              <option value="60">Every hour</option>
            </select>
          </div>

          {/* Auto Transcribe */}
          <div className="p-4 flex items-center justify-between">
            <div>
              <p className="font-medium">Auto Transcribe</p>
              <p className="text-sm text-secondary">Automatically transcribe new voicemails</p>
            </div>
            <ToggleSwitch
              enabled={settings?.auto_transcribe === 'true'}
              onChange={(enabled) => updateSetting('auto_transcribe', enabled ? 'true' : 'false')}
              disabled={saving}
            />
          </div>

          {/* Auto Summarize */}
          <div className="p-4 flex items-center justify-between">
            <div>
              <p className="font-medium">Auto Summarize</p>
              <p className="text-sm text-secondary">Automatically generate summaries after transcription</p>
            </div>
            <ToggleSwitch
              enabled={settings?.auto_summarize === 'true'}
              onChange={(enabled) => updateSetting('auto_summarize', enabled ? 'true' : 'false')}
              disabled={saving}
            />
          </div>

        </div>
      </section>

      {/* Email Settings */}
      <section className="mb-12">
        <h2 className="text-xs font-medium text-secondary uppercase tracking-wide mb-4">Email Notifications</h2>
        <div className="border border-border divide-y divide-border">
          {/* Auto Email */}
          <div className="p-4 flex items-center justify-between">
            <div>
              <p className="font-medium">Auto Send Emails</p>
              <p className="text-sm text-secondary">Automatically email new voicemails after processing</p>
            </div>
            <ToggleSwitch
              enabled={settings?.auto_email === 'true'}
              onChange={(enabled) => updateSetting('auto_email', enabled ? 'true' : 'false')}
              disabled={saving}
            />
          </div>

          {/* Notification Email */}
          <div className="p-4">
            <p className="font-medium mb-2">Notification Email</p>
            <p className="text-sm text-secondary mb-2">Where to send voicemail notifications</p>
            <input
              type="email"
              value={settings?.notification_email || ''}
              onChange={(e) => updateSetting('notification_email', e.target.value)}
              placeholder="helpdesk@example.com"
              disabled={saving}
              className="w-full border border-border px-3 py-2 text-sm"
            />
          </div>

          {/* Email Cutoff Date */}
          <div className="p-4">
            <p className="font-medium mb-2">Email Cutoff Date</p>
            <p className="text-sm text-secondary mb-2">
              Only voicemails received <strong>after</strong> this date will be emailed.
              Leave empty to email all pending voicemails.
            </p>
            <input
              type="datetime-local"
              value={settings?.email_only_after ? formatDateTimeLocal(settings.email_only_after) : ''}
              onChange={(e) => {
                const value = e.target.value ? new Date(e.target.value).toISOString() : '';
                updateSetting('email_only_after', value);
              }}
              disabled={saving}
              className="border border-border px-3 py-2 text-sm"
            />
            {settings?.email_only_after && (
              <button
                onClick={() => updateSetting('email_only_after', '')}
                className="ml-2 text-sm text-secondary hover:text-black"
              >
                Clear
              </button>
            )}
          </div>
        </div>
      </section>

      {/* Manual Actions */}
      <section className="mb-12">
        <h2 className="text-xs font-medium text-secondary uppercase tracking-wide mb-4">Manual Actions</h2>
        <div className="border border-border p-4">
          <button
            onClick={handleSyncNow}
            disabled={syncing}
            className="px-4 py-2 bg-black text-white text-sm hover:bg-gray-800 disabled:opacity-50"
          >
            {syncing ? 'Syncing...' : 'Sync Now'}
          </button>
          <p className="mt-2 text-sm text-secondary">
            Manually trigger sync, transcription, and summarization
          </p>
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
          <EndpointRow method="GET" path="/settings" description="Get all settings" />
          <EndpointRow method="PUT" path="/settings/{key}" description="Update a setting" />
          <EndpointRow method="POST" path="/settings/sync-now" description="Trigger manual sync" />
          <EndpointRow method="GET" path="/health" description="System health check" />
        </div>
      </section>
    </div>
  );
}

function ToggleSwitch({ enabled, onChange, disabled }: { enabled: boolean; onChange: (enabled: boolean) => void; disabled: boolean }) {
  return (
    <button
      onClick={() => onChange(!enabled)}
      disabled={disabled}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
        enabled ? 'bg-black' : 'bg-gray-300'
      } ${disabled ? 'opacity-50' : ''}`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
          enabled ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
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
