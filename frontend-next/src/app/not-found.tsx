import Link from "next/link";

export default function NotFoundPage() {
  return (
    <div className="error-page">
      <div className="error-code">404</div>
      <h2 style={{ fontSize: "1.25rem", fontWeight: 600, color: "var(--text-primary)" }}>
        Page not found
      </h2>
      <p style={{ maxWidth: 420, color: "var(--text-secondary)" }}>
        The page you are looking for does not exist or has been moved.
      </p>
      <Link href="/" className="btn btn-primary" style={{ marginTop: "var(--space-md)", textDecoration: "none" }}>
        Back to Dashboard
      </Link>
    </div>
  );
}
