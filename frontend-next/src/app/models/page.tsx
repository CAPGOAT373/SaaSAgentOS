"use client";

import { useEffect, useState, useCallback } from "react";
import AuthGuard from "@/components/auth/AuthGuard";
import AppLayout from "@/components/layout/AppLayout";
import { mockModels, delay, runMockModelTest } from "@/services/mock/data";
import { Cpu, CheckCircle, XCircle, Loader2, Globe, Key } from "lucide-react";

interface ModelRecord {
  id: string;
  name: string;
  provider: string;
  base_url: string;
  api_key_status: string;
  created_at: string;
}

interface TestResult {
  success: boolean;
  message: string;
  latency_ms?: number;
}




export default function ModelsPage() {
  return (
    <AuthGuard>
      <AppLayout>
        <ModelsContent />
      </AppLayout>
    </AuthGuard>
  );
}

function ModelsContent() {
  const [models, setModels] = useState<ModelRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [testing, setTesting] = useState<Record<string, boolean>>({});
  const [results, setResults] = useState<Record<string, TestResult>>({});

  const fetchModels = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      await delay();
      setModels([...mockModels]);
    } catch (err: any) {
      setError(err.message ?? "Failed to load models.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchModels(); }, []);

  async function handleTest(modelId: string) {
    setTesting((p) => ({ ...p, [modelId]: true }));
    setResults((p) => { const n = { ...p }; delete n[modelId]; return n; });
    try {
      await delay();
      const data = runMockModelTest(modelId);
      setResults((p) => ({ ...p, [modelId]: data }));
    } catch (err: any) {
      setResults((p) => ({ ...p, [modelId]: { success: false, message: err.message ?? "Test failed" } }));
    } finally {
      setTesting((p) => ({ ...p, [modelId]: false }));
    }
  }

  const statusColor = (s: string) =>
    s === "configured" ? "var(--success)" : s === "missing" ? "var(--warning)" : "var(--danger)";
  const statusLabel = (s: string) =>
    s === "configured" ? "Configured" : s === "missing" ? "Missing" : "Error";

  return (
    <div>
      <div style={{ marginBottom: "var(--space-xl)" }}>
        <h2 style={{ fontSize: "1.5rem", fontWeight: 600, color: "var(--text-primary)" }}>Model Management</h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginTop: 4 }}>
          {models.length} model{models.length !== 1 ? "s" : ""} configured
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
          <button onClick={fetchModels} className="btn btn-sm" style={{ marginLeft: 12 }}>Retry</button>
        </div>
      )}

      {!loading && !error && (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
          {models.map((m) => {
            const r = results[m.id];
            const t = testing[m.id];
            return (
              <div key={m.id} className="card" style={{ display: "flex", alignItems: "center", gap: "var(--space-md)", flexWrap: "wrap" }}>
                <div style={{ width: 44, height: 44, borderRadius: "var(--radius-lg)", background: "var(--accent-light)", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <Cpu size={20} />
                </div>
                <div style={{ flex: 1, minWidth: 180 }}>
                  <div style={{ fontWeight: 600, fontSize: "0.9375rem", color: "var(--text-primary)" }}>{m.name}</div>
                  <div style={{ display: "flex", gap: 16, fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 3, flexWrap: "wrap" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: 4 }}><Globe size={12} />{m.provider}</span>
                    <span style={{ display: "flex", alignItems: "center", gap: 4 }}><Key size={12} />{m.base_url}</span>
                  </div>
                </div>
                <span className="badge" style={{ color: statusColor(m.api_key_status), background: `${statusColor(m.api_key_status)}14`, border: `1px solid ${statusColor(m.api_key_status)}30`, fontSize: "0.75rem" }}>
                  {statusLabel(m.api_key_status)}
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
                  <button onClick={() => handleTest(m.id)} className="btn btn-sm btn-primary" disabled={t} style={{ minWidth: 130 }}>
                    {t ? <><Loader2 size={14} style={{ animation: "spin 0.7s linear infinite" }} /> Testing...</> : "Test Connection"}
                  </button>
                </div>
                {r && (
                  <div style={{ width: "100%", marginTop: "var(--space-sm)", padding: "8px 14px", borderRadius: "var(--radius)", fontSize: "0.8125rem", background: r.success ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)", color: r.success ? "var(--success)" : "var(--danger)", display: "flex", alignItems: "center", gap: 6 }}>
                    {r.success ? <CheckCircle size={14} /> : <XCircle size={14} />}
                    {r.message}{r.latency_ms ? ` (${r.latency_ms} ms)` : ""}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
