"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/auth/AuthGuard";
import AppLayout from "@/components/layout/AppLayout";
import { mockBillingBalance, mockBillingUsage, delay } from "@/services/mock/data";
import { CreditCard, Activity, DollarSign, BarChart3 } from "lucide-react";

export default function BillingPage() {
  return <AuthGuard><AppLayout><BillingContent /></AppLayout></AuthGuard>;
}

function BillingContent() {
  const [loading, setLoading] = useState(true);
  useEffect(() => { delay().then(() => setLoading(false)); }, []);
  if (loading) return <div style={{ display: "flex", justifyContent: "center", padding: "var(--space-2xl)" }}><div className="spinner spinner-lg" /></div>;

  return (
    <div>
      <div style={{ marginBottom: "var(--space-xl)" }}>
        <h2 style={{ fontSize: "1.5rem", fontWeight: 600, color: "var(--text-primary)" }}>Billing & Usage</h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginTop: 4 }}>Credit balance and usage overview.</p>
      </div>
      <div className="grid grid-2" style={{ marginBottom: "var(--space-lg)" }}>
        <div className="card" style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ width: 48, height: 48, borderRadius: "var(--radius-lg)", background: "rgba(34,197,94,0.12)", color: "var(--success)", display: "flex", alignItems: "center", justifyContent: "center" }}><DollarSign size={22} /></div>
          <div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 2 }}>Credit Balance</div>
            <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--success)" }}>${mockBillingBalance.balance.toFixed(2)}</div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{mockBillingBalance.credits} credits</div>
          </div>
        </div>
        <div className="card" style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ width: 48, height: 48, borderRadius: "var(--radius-lg)", background: "var(--accent-light)", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center" }}><Activity size={22} /></div>
          <div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 2 }}>Monthly Usage</div>
            <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--text-primary)" }}>{mockBillingUsage.total_calls.toLocaleString()} calls</div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{mockBillingUsage.total_tokens.toLocaleString()} tokens</div>
          </div>
        </div>
      </div>
      <div className="card">
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <BarChart3 size={16} style={{ color: "var(--text-muted)" }} />
          <span style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--text-secondary)" }}>Usage Breakdown ? {mockBillingUsage.period}</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Total Calls</span><span style={{ fontWeight: 500, color: "var(--text-primary)" }}>{mockBillingUsage.total_calls.toLocaleString()}</span></div>
          <div style={{ display: "flex", justifyContent: "space-between" }}><span>Total Tokens</span><span style={{ fontWeight: 500, color: "var(--text-primary)" }}>{mockBillingUsage.total_tokens.toLocaleString()}</span></div>
          <div style={{ display: "flex", justifyContent: "space-between", borderTop: "1px solid var(--border)", paddingTop: 8 }}><span style={{ fontWeight: 600 }}>Total Cost</span><span style={{ fontWeight: 700, color: "var(--accent)" }}>${mockBillingUsage.total_cost.toFixed(2)}</span></div>
        </div>
      </div>
    </div>
  );
}
