"use client";

import { useEffect } from "react";

interface Props {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ error, reset }: Props) {
  useEffect(() => {
    console.error("Global error boundary caught:", error);
  }, [error]);

  return (
    <div className="error-page">
      <div className="error-code">500</div>
      <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "var(--text-primary)" }}>
        Something went wrong
      </h2>
      <p style={{ maxWidth: 420, color: "var(--text-secondary)" }}>
        An unexpected error occurred. Please try again, or contact support if the
        problem persists.
      </p>
      <button onClick={reset} className="btn btn-primary" style={{ marginTop: "var(--space-md)" }}>
        Try Again
      </button>
    </div>
  );
}
