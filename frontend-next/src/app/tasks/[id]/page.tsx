"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import AuthGuard from "@/components/auth/AuthGuard";
import AppLayout from "@/components/layout/AppLayout";
import { axiosInstance } from "@/api";
import { ArrowLeft, ListTodo, Clock, CheckCircle, XCircle, Loader2, Circle, FileText } from "lucide-react";

interface TaskDetail {
  id: string;
  name: string;
  status: string;
  created_at: string;
  duration: number;
  logs?: string[];
}




export default function TaskDetailPage() {
  return (
    <AuthGuard>
      <AppLayout>
        <TaskDetailContent />
      </AppLayout>
    </AuthGuard>
  );
}

function TaskDetailContent() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    (async () => {
      setLoading(true); setError("");
      try {
        const res = await axiosInstance.get(`/tasks/${id}`);
        if (!cancelled) setTask(res.data);
      } catch (err: any) {
        if (!cancelled) setError(err.message ?? "Failed to load task.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [id]);

  const statusIcon = (s: string) => {
    if (s === "completed") return <CheckCircle size={16} />;
    if (s === "failed") return <XCircle size={16} />;
    if (s === "running") return <Loader2 size={16} style={{ animation: "spin 0.7s linear infinite" }} />;
    return <Circle size={16} />;
  };
  const statusColor = (s: string) =>
    s === "completed" ? "var(--success)" : s === "failed" ? "var(--danger)" : s === "running" ? "var(--info)" : "var(--text-muted)";
  const fmtDuration = (ms: number) => {
    if (!ms || ms <= 0) return "—";
    if (ms < 1000) return `${ms}ms`;
    const s = Math.floor(ms / 1000);
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    return `${m}m ${s % 60}s`;
  };

  return (
    <div>
      <button onClick={() => router.push("/tasks")} style={{ display: "inline-flex", alignItems: "center", gap: 6, background: "none", border: "none", color: "var(--text-secondary)", fontSize: "0.875rem", cursor: "pointer", marginBottom: "var(--space-lg)" }}>
        <ArrowLeft size={16} /> Back to Tasks
      </button>
      {loading && <div style={{ display: "flex", justifyContent: "center", padding: "var(--space-2xl)" }}><div className="spinner spinner-lg" /></div>}
      {!loading && error && <div className="card" style={{ textAlign: "center", padding: "var(--space-2xl)", color: "var(--danger)" }}>{error}</div>}
      {!loading && !error && task && (
        <>
          <div style={{ display: "flex", alignItems: "flex-start", gap: "var(--space-md)", marginBottom: "var(--space-xl)" }}>
            <div style={{ width: 56, height: 56, borderRadius: "var(--radius-lg)", background: "var(--accent-light)", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <ListTodo size={26} />
            </div>
            <div style={{ flex: 1 }}>
              <h2 style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>{task.name}</h2>
              <div style={{ display: "flex", gap: 16, fontSize: "0.8125rem", color: "var(--text-muted)" }}>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}><Clock size={13} />{new Date(task.created_at).toLocaleString()}</span>
                <span>Duration: {fmtDuration(task.duration)}</span>
              </div>
            </div>
            <span className="badge" style={{ color: statusColor(task.status), background: `${statusColor(task.status)}14`, border: `1px solid ${statusColor(task.status)}30`, fontSize: "0.8125rem", padding: "6px 16px", display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
              {statusIcon(task.status)}{task.status}
            </span>
          </div>
          <div className="grid grid-2" style={{ marginBottom: "var(--space-xl)" }}>
            <div className="card" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Task ID</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.8125rem", color: "var(--text-primary)" }}>{task.id}</span>
            </div>
            <div className="card" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Status</span>
              <span style={{ display: "flex", alignItems: "center", gap: 6, color: statusColor(task.status), fontWeight: 500 }}>{statusIcon(task.status)}{task.status}</span>
            </div>
          </div>
          {task.logs && task.logs.length > 0 && (
            <div className="card">
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                <FileText size={16} style={{ color: "var(--text-muted)" }} />
                <span style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--text-secondary)" }}>Execution Logs</span>
              </div>
              <pre style={{ fontSize: "0.8125rem", color: "var(--text-primary)", whiteSpace: "pre-wrap", fontFamily: "var(--font-mono)", background: "var(--bg-tertiary)", padding: 12, borderRadius: "var(--radius)", margin: 0, maxHeight: 400, overflow: "auto" }}>
                {task.logs.join("\n")}
              </pre>
            </div>
          )}
        </>
      )}
    </div>
  );
}
