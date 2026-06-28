"use client";

import type { ReactNode } from "react";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import Breadcrumb from "./Breadcrumb";

interface Props {
  children: ReactNode;
}

export default function AppLayout({ children }: Props) {
  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <Sidebar />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Topbar />
        <Breadcrumb />
        <main
          style={{
            flex: 1,
            overflow: "auto",
            padding: "var(--space-lg)",
            background: "var(--bg-primary)",
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
