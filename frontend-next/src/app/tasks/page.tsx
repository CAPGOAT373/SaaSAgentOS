"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AuthGuard from "@/components/auth/AuthGuard";
import AppLayout from "@/components/layout/AppLayout";
import { axiosInstance } from "@/api";
import { ListTodo, Clock, ArrowRight, CheckCircle, XCircle, Loader2, Circle } from "lucide-react";

interface TaskRecord { id: string; name: string; status: string; created_at: string; duration: number; }

export default function TasksPage() {
  return <AuthGuard><AppLayout><TasksContent /></AppLayout></AuthGuard>;
}

function TasksContent() {
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true); setError("");
      try {
        const res = await axiosInstance.get("/tasks");
        if (!cancelled) setTasks(res.data);
      } catch (err: any) {
        if (!cancelled) setError(err.message ?? "Failed to load tasks.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const fmtDuration = (ms: number) => { if (!ms || ms <= 0) return "\u2014"; if (ms < 1000) return `${ms}ms`; const s = Math.floor(ms / 1000); if (s < 60) return `${s}s`; const m = Math.floor(s / 60); return `${m}m ${s % 60}s`; };
  const statusIcon = (s: string) => { if (s === "completed") return <CheckCircle size={14} />; if (s === "failed") return <XCircle size={14} />; if (s === "running") return <Loader2 size={14} style={{ animation: "spin 0.7s linear infinite" }} />; return <Circle size={14} />; };
  const statusColor = (s: string) => s === "completed" ? "var(--success)" : s === "failed" ? "var(--danger)" : s === "running" ? "var(--info)" : "var(--text-muted)";

  return (
    <div>
      <div style={{ marginBottom: "var(--space-xl)" }}><h2 style={{ fontSize: "1.5rem", fontWeight: 600, color: "var(--text-primary)" }}>Task Center</h2><p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginTop: 4 }}>{tasks.length} task{tasks.length !== 1 ? "s" : ""}</p></div>
      {loading && <div style={{ display: "flex", justifyContent: "center", padding: "var(--space-2xl)" }}><div className="spinner spinner-lg" /></div>}
      {!loading && error && <div style={{ background: "rgba(239,68,68,0.1)", border: "1px solid var(--danger)", borderRadius: "var(--radius)", padding: "12px 20px", color: "var(--danger)", fontSize: "0.875rem", marginBottom: "var(--space-lg)" }}>{error}</div>}
      {!loading && !error && (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
          {tasks.map((t) => (
            <Link key={t.id} href={`/tasks/${t.id}`} style={{ textDecoration: "none", color: "inherit" }}>
              <div className="card card-hover" style={{ display: "flex", alignItems: "center", gap: "var(--space-md)", cursor: "pointer" }}>
                <div style={{ width: 44, height: 44, borderRadius: "var(--radius-lg)", background: "var(--accent-light)", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><ListTodo size={20} /></div>
                <div style={{ flex: 1, minWidth: 0 }}><div style={{ fontWeight: 600, fontSize: "0.9375rem", color: "var(--text-primary)", marginBottom: 2 }}>{t.name}</div><div style={{ display: "flex", gap: 16, fontSize: "0.75rem", color: "var(--text-muted)" }}><span style={{ display: "flex", alignItems: "center", gap: 4 }}><Clock size={12} />{new Date(t.created_at).toLocaleString()}</span><span>Duration: {fmtDuration(t.duration)}</span></div></div>
                <span className="badge" style={{ color: statusColor(t.status), background: `${statusColor(t.status)}14`, border: `1px solid ${statusColor(t.status)}30`, fontSize: "0.75rem", display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>{statusIcon(t.status)}{t.status}</span>
                <ArrowRight size={16} style={{ color: "var(--text-muted)", opacity: 0.4 }} />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
