"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import AuthGuard from "@/components/auth/AuthGuard";
import AppLayout from "@/components/layout/AppLayout";
import { api } from "@/api";
import type { Agent } from "@/api";
import {
  ArrowLeft,
  Bot,
  Clock,
  Play,
  Tag,
  DollarSign,
  Star,
  FileText,
} from "lucide-react";

export default function AgentDetailPage() {
  return (
    <AuthGuard>
      <AppLayout>
        <AgentDetail />
      </AppLayout>
    </AuthGuard>
  );
}

function AgentDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError("");
      try {
        const data = await api.getAgent(id);
        if (!cancelled) setAgent(data);
      } catch (err: any) {
        if (!cancelled) setError(err?.message ?? "Failed to load agent details.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [id]);

  const statusColor =
    agent?.status === "published" ? "var(--success)" :
    agent?.status === "draft" ? "var(--text-muted)" :
    agent?.status === "archived" ? "var(--danger)" :
    "var(--text-muted)";

  return (
    <div>
      <button
        onClick={() => router.push("/agents")}
        style={{ display: "inline-flex", alignItems: "center", gap: 6, background: "none", border: "none", color: "var(--text-secondary)", fontSize: "0.875rem", cursor: "pointer", marginBottom: "var(--space-lg)" }}
      >
        <ArrowLeft size={16} /> Back to Agents
      </button>

      {loading && (
        <div style={{ display: "flex", justifyContent: "center", padding: "var(--space-2xl)" }}>
          <div className="spinner spinner-lg" />
        </div>
      )}

      {!loading && error && (
        <div className="card" style={{ textAlign: "center", padding: "var(--space-2xl)", color: "var(--danger)" }}>
          {error}
        </div>
      )}

      {!loading && !error && agent && (
        <>
          {/* Title row */}
          <div style={{ display: "flex", alignItems: "flex-start", gap: "var(--space-md)", marginBottom: "var(--space-xl)" }}>
            <div style={{ width: 56, height: 56, borderRadius: "var(--radius-lg)", background: "var(--accent-light)", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <Bot size={26} />
            </div>
            <div style={{ flex: 1 }}>
              <h2 style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>
                {agent.name}
              </h2>
              <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
                {agent.description || "No description"}
              </p>
            </div>
            <span className="badge" style={{ border: `1px solid ${statusColor}30`, color: statusColor, background: `${statusColor}14`, fontSize: "0.8125rem", padding: "6px 16px" }}>
              {agent.status ?? "draft"}
            </span>
          </div>

          {/* Meta grid */}
          <div className="grid grid-4" style={{ marginBottom: "var(--space-xl)" }}>
            <div className="card" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Agent ID</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis" }}>
                {agent.agent_id}
              </span>
            </div>
            <div className="card" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Type</span>
              <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.875rem", color: "var(--text-primary)" }}>
                <Tag size={14} />{agent.agent_type ?? "chat"}
              </span>
            </div>
            <div className="card" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Pricing</span>
              <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.875rem", color: "var(--text-primary)" }}>
                <DollarSign size={14} />{agent.price_model ?? "free"} {agent.price ? `($${agent.price})` : ""}
              </span>
            </div>
            <div className="card" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Created</span>
              <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.875rem", color: "var(--text-primary)" }}>
                <Clock size={14} />
                {agent.created_at ? new Date(agent.created_at).toLocaleString() : "—"}
              </span>
            </div>
          </div>

          {/* Actions */}
          <div style={{ display: "flex", gap: "var(--space-sm)", marginBottom: "var(--space-xl)" }}>
            <button className="btn btn-sm" disabled title="Agent execution will be available in a future sprint">
              <Play size={14} /> Execute
            </button>
            <button className="btn btn-sm btn-primary" disabled title="Publishing will be available in a future sprint">
              <Star size={14} /> Publish
            </button>
          </div>

          {/* System prompt preview */}
          {agent.system_prompt && (
            <div className="card" style={{ marginBottom: "var(--space-lg)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                <FileText size={16} style={{ color: "var(--text-muted)" }} />
                <span style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--text-secondary)" }}>System Prompt</span>
              </div>
              <pre style={{ fontSize: "0.8125rem", color: "var(--text-primary)", whiteSpace: "pre-wrap", fontFamily: "var(--font-mono)", background: "var(--bg-tertiary)", padding: 12, borderRadius: "var(--radius)", margin: 0 }}>
                {agent.system_prompt}
              </pre>
            </div>
          )}
        </>
      )}
    </div>
  );
}
