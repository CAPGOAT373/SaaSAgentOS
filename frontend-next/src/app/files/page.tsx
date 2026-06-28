"use client";

import { useEffect, useState, useCallback } from "react";
import AuthGuard from "@/components/auth/AuthGuard";
import AppLayout from "@/components/layout/AppLayout";
import { useAuth } from "@/lib/auth";
import {
  FolderOpen,
  File,
  Upload,
  Trash2,
  HardDrive,
  Clock,
} from "lucide-react";

interface FileRecord {
  id: string;
  filename: string;
  size: number;
  uploaded_at: string;
}

const API = "/api/v1/files";

function authHeaders(token: string | null): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

function fmtSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1)} ${sizes[i]}`;
}

export default function FilesPage() {
  return (
    <AuthGuard>
      <AppLayout>
        <FilesContent />
      </AppLayout>
    </AuthGuard>
  );
}

function FilesContent() {
  const { token } = useAuth();
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // upload form
  const [filename, setFilename] = useState("");
  const [fileSize, setFileSize] = useState(0);
  const [uploading, setUploading] = useState(false);

  const fetchFiles = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const resp = await fetch(API, { headers: authHeaders(token) });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setFiles(await resp.json());
    } catch (err: any) {
      setError(err.message ?? "Failed to load files.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchFiles(); }, [fetchFiles]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!filename.trim()) return;
    setUploading(true);
    try {
      const params = new URLSearchParams({ filename: filename.trim(), size: String(fileSize) });
      const resp = await fetch(`${API}/upload?${params}`, { method: "POST", headers: authHeaders(token) });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setFilename("");
      setFileSize(0);
      await fetchFiles();
    } catch (err: any) {
      setError(err.message ?? "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      const resp = await fetch(`${API}/${id}`, { method: "DELETE", headers: authHeaders(token) });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      await fetchFiles();
    } catch (err: any) {
      setError(err.message ?? "Delete failed.");
    }
  }

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-xl)" }}>
        <div>
          <h2 style={{ fontSize: "1.5rem", fontWeight: 600, color: "var(--text-primary)" }}>Knowledge Base Files</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginTop: 4 }}>
            {files.length} file{files.length !== 1 ? "s" : ""}
          </p>
        </div>
      </div>

      {/* Upload form */}
      <form onSubmit={handleUpload} style={{ display: "flex", gap: "var(--space-sm)", marginBottom: "var(--space-lg)", alignItems: "flex-end", flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Filename</label>
          <input className="input" value={filename} onChange={e => setFilename(e.target.value)} placeholder="e.g. knowledge-base.pdf" style={{ width: 260 }} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Size (bytes)</label>
          <input className="input" type="number" value={fileSize} onChange={e => setFileSize(Number(e.target.value))} placeholder="1024" style={{ width: 130 }} />
        </div>
        <button type="submit" className="btn btn-primary btn-sm" disabled={uploading || !filename.trim()}>
          <Upload size={14} /> {uploading ? "Uploading..." : "Upload"}
        </button>
      </form>

      {/* Loading */}
      {loading && (
        <div style={{ display: "flex", justifyContent: "center", padding: "var(--space-2xl)" }}>
          <div className="spinner spinner-lg" />
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div style={{ background: "rgba(239,68,68,0.1)", border: "1px solid var(--danger)", borderRadius: "var(--radius)", padding: "12px 20px", color: "var(--danger)", fontSize: "0.875rem", marginBottom: "var(--space-lg)" }}>
          {error}
          <button onClick={fetchFiles} className="btn btn-sm" style={{ marginLeft: 12 }}>Retry</button>
        </div>
      )}

      {/* File list */}
      {!loading && !error && (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
          {files.length === 0 ? (
            <div className="card" style={{ textAlign: "center", padding: "var(--space-2xl)", color: "var(--text-muted)" }}>
              <FolderOpen size={40} style={{ marginBottom: 8, opacity: 0.35 }} />
              <p>No files uploaded yet</p>
            </div>
          ) : (
            files.map((f) => (
              <div key={f.id} className="card" style={{ display: "flex", alignItems: "center", gap: "var(--space-md)" }}>
                <div style={{ width: 40, height: 40, borderRadius: "var(--radius)", background: "var(--accent-light)", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <File size={18} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 500, fontSize: "0.875rem", color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.filename}</div>
                  <div style={{ display: "flex", gap: 16, fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 2 }}>
                    <span style={{ display: "flex", alignItems: "center", gap: 4 }}><HardDrive size={12} />{fmtSize(f.size)}</span>
                    <span style={{ display: "flex", alignItems: "center", gap: 4 }}><Clock size={12} />{new Date(f.uploaded_at).toLocaleString()}</span>
                  </div>
                </div>
                <button onClick={() => handleDelete(f.id)} className="btn btn-sm btn-danger" style={{ flexShrink: 0 }}>
                  <Trash2 size={14} /> Delete
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
