"use client";

import AuthGuard from "@/components/auth/AuthGuard";
import AppLayout from "@/components/layout/AppLayout";
import { Store } from "lucide-react";

export default function MarketplacePage() {
  return (
    <AuthGuard>
      <AppLayout>
        <Placeholder
          icon={<Store size={48} />}
          title="Marketplace"
          description="Browse, purchase, and deploy AI agents and plugins from the community. This page will be implemented in Sprint 1."
        />
      </AppLayout>
    </AuthGuard>
  );
}

function Placeholder({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "calc(100vh - 120px)", gap: "var(--space-md)", color: "var(--text-muted)", textAlign: "center", padding: "var(--space-2xl)" }}>
      <div style={{ color: "var(--accent)", opacity: 0.6, marginBottom: 8 }}>{icon}</div>
      <h2 style={{ fontSize: "1.5rem", fontWeight: 600, color: "var(--text-primary)" }}>{title}</h2>
      <p style={{ maxWidth: 400, fontSize: "0.9375rem", color: "var(--text-secondary)" }}>{description}</p>
    </div>
  );
}
