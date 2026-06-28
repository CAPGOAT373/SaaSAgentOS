"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AuthGuard from "@/components/auth/AuthGuard";
import AppLayout from "@/components/layout/AppLayout";
import { useAuth } from "@/lib/auth";
import { api } from "@/api";
import type { Workflow } from "@/api";
import { GitBranch, Plus, Clock, ArrowRight } from "lucide-react";

export default function WorkflowsPage() {
  return (
    <AuthGuard>
      <AppLayout>
        <WorkflowsContent />
      </AppLayout>
    </AuthGuard>
  );
}

function WorkflowsContent() {
  const { user } = useAuth();
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function fetchWorkflows() {
    setLoading(true);
    setError("");
    try {
      const data = await api.listWorkflows(user?.tenant_id ?? "");
      setWorkflows(data);
    } catch (err: any) {
      setError(err?.message ?? "Failed to load workflows.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchWorkflows(); }, [user?.tenant_id]);

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-xl)" }}>
        <div>
          <h2 style={{ fontSize: "1.5rem", fontWeight: 600, color: "var(--text-primary)" }}>Workflow Studio</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginTop: 4 }}>
            {workflows.length} workflow{workflows.length !== 1 ? "s" : ""}
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => { /* placeholder for create modal — Sprint 4 */ }} disabled>
          <Plus size={16} /> New Workflow
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ display: "flex", justifyContent: "center", padding: "var(--space-2xl)" }}>
          <div className="spinner spinner-lg" />
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div style={{ background: "rgba(239,68,68,0.1)", border: "1px solid var(--danger)", borderRadius: "var(--radius)", padding: "12px 20px", color: "var(--danger)", fontSize: "0.875rem", marginBottom: "var(--space-lg)" }}>
          {error}
          <button onClick={fetchWorkflows} className="btn btn-sm" style={{ marginLeft: 12 }}>Retry</button>
        </div>
      )}

      {/* List */}
      {!loading && !error && (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
          {workflows.length === 0 ? (
            <div className="card" style={{ textAlign: "center", padding: "var(--space-2xl)", color: "var(--text-muted)" }}>
              <GitBranch size={36} style={{ marginBottom: 8, opacity: 0.4 }} />
              <p>No workflows yet</p>
            </div>
          ) : (
            workflows.map((wf) => (
              <WorkflowCard key={wf.workflow_id} workflow={wf} />
            ))
          )}
        </div>
      )}
    </div>
  );
}

function WorkflowCard({ workflow }: { workflow: Workflow }) {
  const statusColor =
    workflow.status === "active" ? "var(--success)" :
    workflow.status === "draft" ? "var(--text-muted)" :
    workflow.status === "paused" ? "var(--warning)" :
    "var(--text-muted)";

  return (
    <Link
      href={`/workflows/${workflow.workflow_id}`}
      style={{ textDecoration: "none", color: "inherit" }}
    >
      <div className="card card-hover" style={{ display: "flex", alignItems: "center", gap: "var(--space-md)", cursor: "pointer" }}>
        <div style={{
          width: 44, height: 44, borderRadius: "var(--radius-lg)",
          background: "var(--accent-light)", color: "var(--accent)",
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}>
          <GitBranch size={20} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: "0.9375rem", color: "var(--text-primary)", marginBottom: 2 }}>
            {workflow.name}
          </div>
          <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 480 }}>
            {workflow.description || "No description"}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: "0.75rem", color: "var(--text-muted)" }}>
            <Clock size={13} />
            {workflow.created_at ? new Date(workflow.created_at).toLocaleDateString() : "—"}
          </span>
          <span className="badge" style={{ border: `1px solid ${statusColor}20`, color: statusColor, background: `${statusColor}10` }}>
            {workflow.status ?? "draft"}
          </span>
          <ArrowRight size={16} style={{ color: "var(--text-muted)", opacity: 0.4 }} />
        </div>
      </div>
    </Link>
  );
}
