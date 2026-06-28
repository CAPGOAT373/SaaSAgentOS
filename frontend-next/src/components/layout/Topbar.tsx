"use client";

import { Sun, Moon, Activity } from "lucide-react";
import { useTheme } from "./ThemeProvider";
import { useAuth } from "@/lib/auth";

export default function Topbar() {
  const { theme, toggle } = useTheme();
  const { user } = useAuth();

  return (
    <header
      style={{
        height: "var(--topbar-height)",
        background: "var(--bg-primary)",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 var(--space-lg)",
        flexShrink: 0,
      }}
    >
      {/* Left: system status indicator */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.8125rem", color: "var(--text-muted)" }}>
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: "var(--success)",
            display: "inline-block",
          }}
        />
        System Online
      </div>

      {/* Right: user avatar + theme toggle */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {user && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: "50%",
                background: "var(--accent-light)",
                color: "var(--accent)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "0.85rem",
                fontWeight: 600,
              }}
            >
              {(user.username ?? "U")[0].toUpperCase()}
            </div>
            <span style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
              {user.username}
            </span>
          </div>
        )}

        <button
          onClick={toggle}
          aria-label="Toggle theme"
          style={{
            width: 36,
            height: 36,
            borderRadius: "var(--radius)",
            border: "1px solid var(--border)",
            background: "transparent",
            color: "var(--text-secondary)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
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
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </div>
    </header>
  );
}
