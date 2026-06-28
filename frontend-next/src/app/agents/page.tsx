"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AuthGuard from "@/components/auth/AuthGuard";
import AppLayout from "@/components/layout/AppLayout";
import { useAuth } from "@/lib/auth";
import { api } from "@/api";
import type { Agent } from "@/api";
import { Bot, Clock, ArrowRight } from "lucide-react";

export default function AgentsPage() {
  return (
    <AuthGuard>
      <AppLayout>
        <AgentsContent />
      </AppLayout>
    </AuthGuard>
  );
}

function AgentsContent() {
  const { user } = useAuth();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function fetchAgents() {
    setLoading(true);
    setError("");
    try {
      const data = await api.listAgents({ tenantId: user?.tenant_id ?? "", limit: 50 });
      setAgents(data);
    } catch (err: any) {
      setError(err?.message ?? "Failed to load agents.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchAgents(); }, [user?.tenant_id]);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-xl)" }}>
        <div>
          <h2 style={{ fontSize: "1.5rem", fontWeight: 600, color: "var(--text-primary)" }}>Agent Studio</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginTop: 4 }}>
            {agents.length} agent{agents.length !== 1 ? "s" : ""}
          </p>
        </div>
        <button className="btn btn-primary" disabled>
          <Bot size={16} /> New Agent
        </button>
      </div>

      {loading && (
        <div style={{ display: "flex", justifyContent: "center", padding: "var(--space-2xl)" }}>
          <div className="spinner spinner-lg" />
        </div>
      )}

      {!loading && error && (
        <div style={{ background: "rgba(239,68,68,0.1)", border: "1px solid var(--danger)", borderRadius: "var(--radius)", padding: "12px 20px", color: "var(--danger)", fontSize: "0.875rem", marginBottom: "var(--space-lg)" }}>
          {error}
          <button onClick={fetchAgents} className="btn btn-sm" style={{ marginLeft: 12 }}>Retry</button>
        </div>
      )}

      {!loading && !error && (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
          {agents.length === 0 ? (
            <div className="card" style={{ textAlign: "center", padding: "var(--space-2xl)", color: "var(--text-muted)" }}>
              <Bot size={36} style={{ marginBottom: 8, opacity: 0.4 }} />
              <p>No agents yet</p>
            </div>
          ) : (
            agents.map((a) => <AgentCard key={a.agent_id} agent={a} />)
          )}
        </div>
      )}
    </div>
  );
}

function AgentCard({ agent }: { agent: Agent }) {
  const statusColor =
    agent.status === "published" ? "var(--success)" :
    agent.status === "draft" ? "var(--text-muted)" :
    agent.status === "archived" ? "var(--danger)" :
    "var(--text-muted)";

  return (
    <Link href={`/agents/${agent.agent_id}`} style={{ textDecoration: "none", color: "inherit" }}>
      <div className="card card-hover" style={{ display: "flex", alignItems: "center", gap: "var(--space-md)", cursor: "pointer" }}>
        <div style={{ width: 44, height: 44, borderRadius: "var(--radius-lg)", background: "var(--accent-light)", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <Bot size={20} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: "0.9375rem", color: "var(--text-primary)", marginBottom: 2 }}>
            {agent.name}
          </div>
          <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 480 }}>
            {agent.description || "No description"}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          <span className="badge badge-info" style={{ fontSize: "0.75rem" }}>{agent.agent_type ?? "chat"}</span>
          <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: "0.75rem", color: "var(--text-muted)" }}>
            <Clock size={13} />
            {agent.created_at ? new Date(agent.created_at).toLocaleDateString() : "—"}
          </span>
          <span className="badge" style={{ border: `1px solid ${statusColor}20`, color: statusColor, background: `${statusColor}10` }}>
            {agent.status ?? "draft"}
          </span>
          <ArrowRight size={16} style={{ color: "var(--text-muted)", opacity: 0.4 }} />
        </div>
      </div>
    </Link>
  );
}
