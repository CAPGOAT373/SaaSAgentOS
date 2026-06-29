"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/auth/AuthGuard";
import AppLayout from "@/components/layout/AppLayout";
import { mockMarketplaceAgents, delay } from "@/services/mock/data";
import { Store, Star, DollarSign } from "lucide-react";

export default function MarketplacePage() {
  return <AuthGuard><AppLayout><MarketplaceContent /></AppLayout></AuthGuard>;
}

function MarketplaceContent() {
  const [agents, setAgents] = useState<typeof mockMarketplaceAgents>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await delay();
      if (!cancelled) { setAgents(mockMarketplaceAgents); setLoading(false); }
    })();
    return () => { cancelled = true; };
  }, []);

  if (loading) return <div style={{ display: "flex", justifyContent: "center", padding: "var(--space-2xl)" }}><div className="spinner spinner-lg" /></div>;

  return (
    <div>
      <div style={{ marginBottom: "var(--space-xl)" }}>
        <h2 style={{ fontSize: "1.5rem", fontWeight: 600, color: "var(--text-primary)" }}>Marketplace</h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginTop: 4 }}>Browse and deploy AI agents from the community.</p>
      </div>
      <div className="grid grid-3">
        {agents.map(a => (
          <div key={a.agent_id} className="card card-hover" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="badge badge-info">{a.category}</span>
              <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                <Star size={13} style={{ color: "var(--warning)" }} />{a.rating}
              </span>
            </div>
            <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-primary)" }}>{a.name}</h3>
            <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", flex: 1 }}>{a.description}</p>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid var(--border)", paddingTop: 10 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: "0.8125rem", fontWeight: 600, color: "var(--accent)" }}>
                <DollarSign size={13} />{a.price_model === "free" ? "Free" : `$${a.price}`}
              </span>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{a.creator}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
