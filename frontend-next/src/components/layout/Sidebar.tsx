"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth";

import { menuItems, filterMenuByRole } from "@/lib/menu";

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const visibleItems = filterMenuByRole(menuItems, user?.roles ?? []);

  function isActive(href: string): boolean {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <aside
      style={{
        width: "var(--sidebar-width)",
        height: "100vh",
        background: "var(--bg-secondary)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        flexShrink: 0,
      }}
    >
      {/* Brand */}
      <div
        style={{
          padding: "20px 16px",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <Link href="/" style={{ color: "inherit", textDecoration: "none" }}>
          <h1
            style={{
              fontSize: "1.05rem",
              fontWeight: 700,
              color: "var(--accent)",
              letterSpacing: "-0.02em",
            }}
          >
            Agent OS V6.0
          </h1>
        </Link>
        <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: 2 }}>
          AI Agent Operating System
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: "12px 8px", overflowY: "auto" }}>
        {visibleItems.map((item) => {
          const active = isActive(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "10px 12px",
                borderRadius: "var(--radius)",
                marginBottom: 4,
                fontSize: "0.875rem",
                fontWeight: active ? 500 : 400,
                color: active ? "var(--text-primary)" : "var(--text-secondary)",
                background: active ? "var(--bg-active)" : "transparent",
                transition: "all 0.12s",
                textDecoration: "none",
              }}
              onMouseEnter={(e) => {
                if (!active) e.currentTarget.style.background = "var(--bg-hover)";
              }}
              onMouseLeave={(e) => {
                if (!active) e.currentTarget.style.background = "transparent";
              }}
            >
              <Icon size={18} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* User + Logout */}
      <div
        style={{
          padding: "16px",
          borderTop: "1px solid var(--border)",
        }}
      >
        <div
          style={{
            fontSize: "0.85rem",
            fontWeight: 500,
            marginBottom: 2,
            color: "var(--text-primary)",
          }}
        >
          {user?.username ?? "User"}
        </div>
        <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: 10 }}>
          {user?.tenant_id ?? ""}
        </div>
        <button
          onClick={logout}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            width: "100%",
            padding: "8px 12px",
            borderRadius: "var(--radius)",
            border: "1px solid var(--border)",
            background: "transparent",
            color: "var(--text-secondary)",
            fontSize: "0.8125rem",
            cursor: "pointer",
            transition: "all 0.12s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--bg-hover)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
          }}
        >
          <LogOut size={16} />
          Logout
        </button>
      </div>
    </aside>
  );
}
