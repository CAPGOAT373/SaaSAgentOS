"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/auth/AuthGuard";
import AppLayout from "@/components/layout/AppLayout";
import { useAuth } from "@/lib/auth";
import { api } from "@/api";
import type { HealthResponse, AdminHealthAllResponse } from "@/api";
import {
  Activity,
  Server,
  Users,
  Bot,
  Workflow,
  Shield,
  BrainCircuit,
  Database,
  Cpu,
} from "lucide-react";

export default function HomePage() {
  return (
    <AuthGuard>
      <AppLayout>
        <DashboardContent />
      </AppLayout>
    </AuthGuard>
  );
}

interface ServiceStatus {
  status: string;
  service: string;
  [key: string]: unknown;
}

function DashboardContent() {
  const { user } = useAuth();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [adminHealth, setAdminHealth] = useState<AdminHealthAllResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      const errs: string[] = [];
      let h: HealthResponse | null = null;
      let ah: AdminHealthAllResponse | null = null;

      try {
        h = await api.getHealth();
      } catch (e) {
        errs.push("System health endpoint unreachable");
      }
      try {
        ah = await api.getAdminHealth();
      } catch (e) {
        errs.push("Admin health details unavailable");
      }

      if (!cancelled) {
        setHealth(h);
        setAdminHealth(ah);
        setErrors(errs);
        setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div>
      {/* Page header */}
      <div style={{ marginBottom: "var(--space-xl)" }}>
        <h2 style={{ fontSize: "1.5rem", fontWeight: 600, color: "var(--text-primary)" }}>
          Dashboard
        </h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginTop: 4 }}>
          Welcome back, {user?.username ?? "User"} — AI Agent Economy Platform overview.
        </p>
      </div>

      {/* Loading state */}
      {loading && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "var(--space-2xl)" }}>
          <div className="spinner spinner-lg" />
        </div>
      )}

      {/* Error banner */}
      {!loading && errors.length > 0 && (
        <div style={{
          background: "rgba(245,158,11,0.1)",
          border: "1px solid var(--warning)",
          borderRadius: "var(--radius-lg)",
          padding: "12px 20px",
          marginBottom: "var(--space-lg)",
          display: "flex",
          alignItems: "center",
          gap: 8,
          fontSize: "0.875rem",
          color: "var(--warning)",
        }}>
          <Activity size={18} />
          {errors.join(" · ")}
        </div>
      )}

      {!loading && (
        <>
          {/* Stats row */}
          <StatsRow health={health} adminHealth={adminHealth} />

          {/* Service grid + Activity sidebar */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: "var(--space-lg)", marginTop: "var(--space-lg)" }}>
            <ServiceGrid services={adminHealth?.services} />
            <QuickInfo health={health} adminHealth={adminHealth} />
          </div>
        </>
      )}
    </div>
  );
}

/* ================================================================
   Stats Row — Key metrics cards
   ================================================================ */

function StatsRow({ health, adminHealth }: { health: HealthResponse | null; adminHealth: AdminHealthAllResponse | null }) {
  const svc = adminHealth?.services ?? {};
  const cards: { label: string; value: string | number; icon: React.ReactNode; accent?: string }[] = [
    {
      label: "System Status",
      value: health?.status ?? "unknown",
      icon: <Activity size={20} />,
      accent: health?.status === "healthy" ? "var(--success)" : "var(--danger)",
    },
    {
      label: "Version",
      value: health?.version ?? "—",
      icon: <Server size={20} />,
    },
    {
      label: "Tenants",
      value: (svc.tenant_manager as Record<string,unknown>)?.total_tenants ?? "—",
      icon: <Users size={20} />,
    },
    {
      label: "Identities",
      value: (svc.iam as Record<string,unknown>)?.total_identities ?? "—",
      icon: <Shield size={20} />,
    },
  ];

  return (
    <div className="grid grid-4" style={{ marginBottom: 0 }}>
      {cards.map((c, i) => (
        <div key={i} className="card" style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{
            width: 44, height: 44, borderRadius: "var(--radius-lg)",
            background: c.accent ? `${c.accent}18` : "var(--accent-light)",
            color: c.accent ?? "var(--accent)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            {c.icon}
          </div>
          <div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 2 }}>{c.label}</div>
            <div style={{ fontSize: "1.25rem", fontWeight: 700, color: c.accent ?? "var(--text-primary)" }}>
              {c.value}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ================================================================
   Service Grid — 8 service health cards
   ================================================================ */

const SERVICE_META: Record<string, { icon: React.ReactNode; label: string }> = {
  tenant_manager: { icon: <Users size={18} />, label: "Tenant Manager" },
  iam:              { icon: <Shield size={18} />, label: "IAM" },
  billing:          { icon: <Activity size={18} />, label: "Billing" },
  agent_economy:    { icon: <Bot size={18} />, label: "Agent Economy" },
  plugin_runtime:   { icon: <Cpu size={18} />, label: "Plugin Runtime" },
  llm_gateway:      { icon: <BrainCircuit size={18} />, label: "LLM Gateway" },
  agent_runtime:    { icon: <Workflow size={18} />, label: "Agent Runtime" },
  memory:           { icon: <Database size={18} />, label: "Memory System" },
};

function ServiceGrid({ services }: { services?: Record<string, ServiceStatus> }) {
  if (!services) {
    return (
      <div className="card" style={{ textAlign: "center", padding: "var(--space-2xl)", color: "var(--text-muted)" }}>
        <Server size={32} style={{ marginBottom: 8, opacity: 0.4 }} />
        <p>Service health data unavailable</p>
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "var(--space-md)" }}>
      {Object.entries(services).map(([key, svc]) => {
        const meta = SERVICE_META[key] ?? { icon: <Server size={18} />, label: key };
        const healthy = svc.status === "healthy";
        const detailEntries = Object.entries(svc).filter(
          ([k]) => k !== "status" && k !== "service"
        );
        return (
          <div key={key} className="card" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ color: healthy ? "var(--success)" : "var(--danger)" }}>
                  {meta.icon}
                </span>
                <span style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-primary)" }}>
                  {meta.label}
                </span>
              </div>
              <span className={`badge ${healthy ? "badge-success" : "badge-danger"}`}>
                {svc.status}
              </span>
            </div>
            {detailEntries.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "2px 14px", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                {detailEntries.slice(0, 4).map(([k, v]) => (
                  <span key={k}>
                    {k.replace(/_/g, " ")}: {String(v)}
                  </span>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ================================================================
   Quick Info sidebar
   ================================================================ */

function QuickInfo({ health, adminHealth }: { health: HealthResponse | null; adminHealth: AdminHealthAllResponse | null }) {
  const svc = adminHealth?.services ?? {};
  const agents = (svc.agent_economy as Record<string,unknown>)?.total_agents ?? 0;
  const executions = (svc.agent_runtime as Record<string,unknown>)?.total_executions ?? 0;
  const plugins = (svc.plugin_runtime as Record<string,unknown>)?.total_plugins ?? 0;
  const providers = String((svc.llm_gateway as Record<string,unknown>)?.providers ?? "—");
  const uptime = health?.timestamp
    ? Math.floor((Date.now() / 1000 - health.timestamp) / 60) + " min ago"
    : "—";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
      <div className="card">
        <h4 style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 14 }}>
          Platform Overview
        </h4>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <InfoRow label="Agents" value={String(agents)} />
          <InfoRow label="Executions" value={String(executions)} />
          <InfoRow label="Plugins" value={String(plugins)} />
          <InfoRow label="LLM Providers" value={providers} />
          <InfoRow label="Last Check" value={uptime} />
        </div>
      </div>

      <div className="card">
        <h4 style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 14 }}>
          Recent Activity
        </h4>
        <div style={{ color: "var(--text-muted)", fontSize: "0.8125rem", textAlign: "center", padding: "var(--space-md) 0" }}>
          <Activity size={24} style={{ marginBottom: 6, opacity: 0.3 }} />
          <p>No recent activity</p>
          <p style={{ fontSize: "0.72rem", marginTop: 2 }}>Activity feed will appear here in Sprint 8</p>
        </div>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.8125rem" }}>
      <span style={{ color: "var(--text-secondary)" }}>{label}</span>
      <span style={{ fontWeight: 500, color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>{value}</span>
    </div>
  );
}
