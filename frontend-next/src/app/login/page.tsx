"use client";

import { useState, useEffect, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Bot } from "lucide-react";
import { api } from "@/api";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/components/layout/ThemeProvider";
import { Sun, Moon } from "lucide-react";

export default function LoginPage() {
  const { isAuthenticated, isLoading, login } = useAuth();
  const router = useRouter();
  const { theme, toggle } = useTheme();

  const [tenantId, setTenantId] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Redirect if already authenticated
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace("/");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
        <div className="spinner spinner-lg" />
      </div>
    );
  }

  if (isAuthenticated) return null;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");

    if (!tenantId.trim() || !email.trim() || !password.trim()) {
      setError("All fields are required.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await api.login({
        tenant_id: tenantId.trim(),
        email: email.trim(),
        password,
      });

      // res is typed as AuthLoginResponse from the curated types
      if (!res?.access_token) {
        setError("Login failed: no token returned.");
        return;
      }

      login(res.access_token, {
        user_id: res.user?.user_id ?? "",
        tenant_id: res.user?.tenant_id ?? "",
        username: res.user?.username ?? email,
        roles: res.user?.roles ?? [],
      });

      router.replace("/");
    } catch (err: any) {
      const msg =
        err?.message ?? err?.statusText ?? "Unable to reach the server.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        background: "var(--bg-secondary)",
        padding: "var(--space-lg)",
      }}
    >
      {/* Theme toggle floating button */}
      <button
        onClick={toggle}
        aria-label="Toggle theme"
        style={{
          position: "fixed",
          top: 20,
          right: 20,
          width: 40,
          height: 40,
          borderRadius: "var(--radius)",
          border: "1px solid var(--border)",
          background: "var(--bg-primary)",
          color: "var(--text-secondary)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
      </button>

      <div
        style={{
          width: "100%",
          maxWidth: 420,
          background: "var(--bg-primary)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          padding: "var(--space-2xl)",
          boxShadow: "var(--shadow-md)",
        }}
      >
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: "var(--space-xl)" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 48,
              height: 48,
              borderRadius: "var(--radius-lg)",
              background: "var(--accent-light)",
              color: "var(--accent)",
              marginBottom: 12,
            }}
          >
            <Bot size={26} />
          </div>
          <h1
            style={{
              fontSize: "1.35rem",
              fontWeight: 700,
              color: "var(--text-primary)",
              letterSpacing: "-0.02em",
            }}
          >
            Agent OS V6.0
          </h1>
          <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginTop: 4 }}>
            Sign in to the AI Agent Economy Platform
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {error && (
            <div
              style={{
                background: "rgba(239,68,68,0.1)",
                border: "1px solid var(--danger)",
                borderRadius: "var(--radius)",
                padding: "10px 14px",
                marginBottom: "var(--space-md)",
                fontSize: "0.8125rem",
                color: "var(--danger)",
              }}
            >
              {error}
            </div>
          )}

          <div style={{ marginBottom: "var(--space-md)" }}>
            <label
              style={{
                display: "block",
                fontSize: "0.8125rem",
                fontWeight: 500,
                color: "var(--text-secondary)",
                marginBottom: 4,
              }}
            >
              Tenant ID
            </label>
            <input
              className="input"
              type="text"
              placeholder="e.g. acme-corp"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              autoFocus
            />
          </div>

          <div style={{ marginBottom: "var(--space-md)" }}>
            <label
              style={{
                display: "block",
                fontSize: "0.8125rem",
                fontWeight: 500,
                color: "var(--text-secondary)",
                marginBottom: 4,
              }}
            >
              Email
            </label>
            <input
              className="input"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div style={{ marginBottom: "var(--space-lg)" }}>
            <label
              style={{
                display: "block",
                fontSize: "0.8125rem",
                fontWeight: 500,
                color: "var(--text-secondary)",
                marginBottom: 4,
              }}
            >
              Password
            </label>
            <input
              className="input"
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-lg w-full"
            disabled={submitting}
            style={{ width: "100%" }}
          >
            {submitting ? (
              <>
                <div className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
                Signing in...
              </>
            ) : (
              "Sign In"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
