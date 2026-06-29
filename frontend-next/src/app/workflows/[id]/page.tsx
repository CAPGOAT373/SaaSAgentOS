"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import AuthGuard from "@/components/auth/AuthGuard";
import AppLayout from "@/components/layout/AppLayout";
import { getMockWorkflowDetail, delay } from "@/services/mock/data";

import {
  ArrowLeft,
  GitBranch,
  Clock,
  Play,
  Pause,
  Square,
  Circle,
  Layers,
} from "lucide-react";

export default function WorkflowDetailPage() {
  return (
    <AuthGuard>
      <AppLayout>
        <WorkflowDetail />
      </AppLayout>
    </AuthGuard>
  );
}

function WorkflowDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError("");
      try {
        await delay();
        const data = getMockWorkflowDetail(id);
        if (!cancelled) setWorkflow(data);
      } catch (err: any) {
        if (!cancelled) setError(err?.message ?? "Failed to load workflow details.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [id]);

  const statusColor =
    workflow?.status === "active" ? "var(--success)" :
    workflow?.status === "draft" ? "var(--text-muted)" :
    workflow?.status === "paused" ? "var(--warning)" :
    "var(--text-muted)";

  return (
    <div>
      {/* Back */}
      <button
        onClick={() => router.push("/workflows")}
        style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          background: "none", border: "none", color: "var(--text-secondary)",
          fontSize: "0.875rem", cursor: "pointer", marginBottom: "var(--space-lg)",
        }}
      >
        <ArrowLeft size={16} /> Back to Workflows
      </button>

      {/* Loading */}
      {loading && (
        <div style={{ display: "flex", justifyContent: "center", padding: "var(--space-2xl)" }}>
          <div className="spinner spinner-lg" />
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="card" style={{ textAlign: "center", padding: "var(--space-2xl)", color: "var(--danger)" }}>
          {error}
        </div>
      )}

      {/* Content */}
      {!loading && !error && workflow && (
        <>
          {/* Title row */}
          <div style={{ display: "flex", alignItems: "flex-start", gap: "var(--space-md)", marginBottom: "var(--space-xl)" }}>
            <div style={{
              width: 56, height: 56, borderRadius: "var(--radius-lg)",
              background: "var(--accent-light)", color: "var(--accent)",
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            }}>
              <GitBranch size={26} />
            </div>
            <div style={{ flex: 1 }}>
              <h2 style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>
                {workflow.name}
              </h2>
              <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
                {workflow.description || "No description"}
              </p>
            </div>
            <span className="badge" style={{ border: `1px solid ${statusColor}30`, color: statusColor, background: `${statusColor}14`, fontSize: "0.8125rem", padding: "6px 16px" }}>
              <Circle size={8} style={{ fill: statusColor, marginRight: 6 }} />
              {workflow.status ?? "draft"}
            </span>
          </div>

          {/* Meta grid */}
          <div className="grid grid-2" style={{ marginBottom: "var(--space-xl)" }}>
            <div className="card" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Workflow ID</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.8125rem", color: "var(--text-primary)" }}>
                {workflow.workflow_id}
              </span>
            </div>
            <div className="card" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Created</span>
              <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.875rem", color: "var(--text-primary)" }}>
                <Clock size={14} />
                {workflow.created_at ? new Date(workflow.created_at).toLocaleString() : "—"}
              </span>
            </div>
          </div>

          {/* Actions bar */}
          <div style={{ display: "flex", gap: "var(--space-sm)", marginBottom: "var(--space-xl)" }}>
            <button className="btn btn-sm" disabled title="Workflow execution will be available in a future sprint">
              <Play size={14} /> Run
            </button>
            <button className="btn btn-sm" disabled title="Workflow execution will be available in a future sprint">
              <Pause size={14} /> Pause
            </button>
            <button className="btn btn-sm" disabled title="Workflow execution will be available in a future sprint">
              <Square size={14} /> Cancel
            </button>
          </div>

          {/* DAG placeholder */}
          <div className="card" style={{ textAlign: "center", padding: "var(--space-2xl)", color: "var(--text-muted)" }}>
            <Layers size={40} style={{ marginBottom: 12, opacity: 0.35 }} />
            <p style={{ fontWeight: 500, marginBottom: 4 }}>Visual Workflow Designer</p>
            <p style={{ fontSize: "0.8125rem" }}>The drag-and-drop DAG editor will be available in a future sprint.</p>
          </div>
        </>
      )}
    </div>
  );
}
