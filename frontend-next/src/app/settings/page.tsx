"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/auth/AuthGuard";
import AppLayout from "@/components/layout/AppLayout";
import { useAuth } from "@/lib/auth";
import { Settings, Save, CheckCircle, XCircle } from "lucide-react";

interface SystemSettings {
  system_name: string;
  default_model: string;
  timezone: string;
  log_level: string;
}

const API = "/api/v1/settings";
const TIMEZONES = ["UTC", "US/Eastern", "US/Pacific", "Europe/London", "Europe/Berlin", "Asia/Shanghai", "Asia/Tokyo"];
const LOG_LEVELS = ["DEBUG", "INFO", "WARN", "ERROR"];

function authHeaders(token: string | null): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

export default function SettingsPage() {
  return (
    <AuthGuard>
      <AppLayout>
        <SettingsContent />
      </AppLayout>
    </AuthGuard>
  );
}

function SettingsContent() {
  const { token } = useAuth();
  const [settings, setSettings] = useState<SystemSettings>({
    system_name: "", default_model: "", timezone: "UTC", log_level: "INFO",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true); setError("");
      try {
        const resp = await fetch(API, { headers: authHeaders(token) });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        if (!cancelled) setSettings(data);
      } catch (err: any) {
        if (!cancelled) setError(err.message ?? "Failed to load settings.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setToast(null);
    try {
      const resp = await fetch(API, {
        method: "PUT",
        headers: authHeaders(token),
        body: JSON.stringify(settings),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      if (data.success) {
        setToast({ type: "success", message: "Settings saved successfully." });
      }
    } catch (err: any) {
      setToast({ type: "error", message: err.message ?? "Failed to save settings." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div style={{ marginBottom: "var(--space-xl)" }}>
        <h2 style={{ fontSize: "1.5rem", fontWeight: 600, color: "var(--text-primary)" }}>System Settings</h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginTop: 4 }}>
          Configure platform-wide parameters.
        </p>
      </div>

      {loading && (
        <div style={{ display: "flex", justifyContent: "center", padding: "var(--space-2xl)" }}>
          <div className="spinner spinner-lg" />
        </div>
      )}

      {!loading && error && (
        <div style={{ background: "rgba(239,68,68,0.1)", border: "1px solid var(--danger)", borderRadius: "var(--radius)", padding: "12px 20px", color: "var(--danger)", fontSize: "0.875rem", marginBottom: "var(--space-lg)" }}>
          {error}
        </div>
      )}

      {toast && (
        <div style={{
          background: toast.type === "success" ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)",
          border: `1px solid ${toast.type === "success" ? "var(--success)" : "var(--danger)"}`,
          borderRadius: "var(--radius)", padding: "12px 20px", marginBottom: "var(--space-lg)",
          color: toast.type === "success" ? "var(--success)" : "var(--danger)",
          fontSize: "0.875rem", display: "flex", alignItems: "center", gap: 8,
        }}>
          {toast.type === "success" ? <CheckCircle size={16} /> : <XCircle size={16} />}
          {toast.message}
        </div>
      )}

      {!loading && !error && (
        <form onSubmit={handleSave} style={{ maxWidth: 520 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
            <Field label="System Name" value={settings.system_name} onChange={v => setSettings(p => ({ ...p, system_name: v }))} />
            <Field label="Default Model" value={settings.default_model} onChange={v => setSettings(p => ({ ...p, default_model: v }))} />
            <SelectField label="Timezone" value={settings.timezone} options={TIMEZONES} onChange={v => setSettings(p => ({ ...p, timezone: v }))} />
            <SelectField label="Log Level" value={settings.log_level} options={LOG_LEVELS} onChange={v => setSettings(p => ({ ...p, log_level: v }))} />
          </div>
          <button type="submit" className="btn btn-primary" disabled={saving} style={{ marginTop: "var(--space-lg)" }}>
            <Save size={16} /> {saving ? "Saving..." : "Save Settings"}
          </button>
        </form>
      )}
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <label style={{ fontSize: "0.8125rem", fontWeight: 500, color: "var(--text-secondary)" }}>{label}</label>
      <input className="input" value={value} onChange={e => onChange(e.target.value)} />
    </div>
  );
}

function SelectField({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <label style={{ fontSize: "0.8125rem", fontWeight: 500, color: "var(--text-secondary)" }}>{label}</label>
      <select className="input" value={value} onChange={e => onChange(e.target.value)} style={{ cursor: "pointer" }}>
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}
