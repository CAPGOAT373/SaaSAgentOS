export default function GlobalLoading() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
        gap: "var(--space-md)",
        color: "var(--text-muted)",
      }}
    >
      <div className="spinner spinner-lg" />
      <span style={{ fontSize: "0.9375rem" }}>Loading Agent OS...</span>
    </div>
  );
}
