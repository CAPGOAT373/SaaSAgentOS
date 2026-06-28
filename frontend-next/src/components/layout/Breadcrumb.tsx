"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Home } from "lucide-react";
import type { MenuItem } from "@/lib/menu";
import { menuItems } from "@/lib/menu";

/** Build a flat lookup map: href → label */
function buildLabelMap(): Record<string, string> {
  const map: Record<string, string> = {};
  function walk(items: MenuItem[]) {
    for (const item of items) {
      map[item.href] = item.label;
      if ((item as any).children) walk((item as any).children);
    }
  }
  walk(menuItems);
  return map;
}

export default function Breadcrumb() {
  const pathname = usePathname();
  const labelMap = buildLabelMap();

  if (pathname === "/") return null; // no breadcrumb on home

  const segments = pathname.split("/").filter(Boolean);

  return (
    <nav
      aria-label="Breadcrumb"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "10px var(--space-lg)",
        fontSize: "0.8125rem",
        color: "var(--text-muted)",
        background: "var(--bg-tertiary)",
        borderBottom: "1px solid var(--border)",
        flexShrink: 0,
      }}
    >
      <Link
        href="/"
        style={{
          display: "flex",
          alignItems: "center",
          color: "var(--text-muted)",
          textDecoration: "none",
        }}
      >
        <Home size={14} />
      </Link>

      {segments.map((seg, i) => {
        const fullPath = "/" + segments.slice(0, i + 1).join("/");
        const label = labelMap[fullPath] ?? seg.charAt(0).toUpperCase() + seg.slice(1);
        const isLast = i === segments.length - 1;

        return (
          <span key={fullPath} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <ChevronRight size={12} />
            {isLast ? (
              <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>{label}</span>
            ) : (
              <Link
                href={fullPath}
                style={{
                  color: "var(--text-muted)",
                  textDecoration: "none",
                }}
              >
                {label}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
