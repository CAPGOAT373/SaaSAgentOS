/**
 * Agent OS V6.0 - Shared menu configuration
 */

import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard, Bot, GitBranch, Store, CreditCard,
  FolderOpen, Cpu, ListTodo, Settings,
} from "lucide-react";

export interface MenuItem {
  id: string;
  label: string;
  icon: LucideIcon;
  href: string;
  requiredRoles?: string[];
}

export const menuItems: MenuItem[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, href: "/" },
  { id: "agents", label: "Agent Studio", icon: Bot, href: "/agents" },
  { id: "workflows", label: "Workflow Studio", icon: GitBranch, href: "/workflows" },
  { id: "marketplace", label: "Marketplace", icon: Store, href: "/marketplace" },
  { id: "billing", label: "Billing", icon: CreditCard, href: "/billing" },
  { id: "files", label: "Files", icon: FolderOpen, href: "/files" },
  { id: "models", label: "Models", icon: Cpu, href: "/models" },
  { id: "tasks", label: "Tasks", icon: ListTodo, href: "/tasks" },
  { id: "settings", label: "Settings", icon: Settings, href: "/settings" },
];

export function filterMenuByRole(items: MenuItem[], roles: string[]): MenuItem[] {
  const has = new Set(roles);
  return items.filter((item) => {
    if (!item.requiredRoles || item.requiredRoles.length === 0) return true;
    return item.requiredRoles.some((r) => has.has(r));
  });
}

export function findMenuItem(href: string): MenuItem | undefined {
  return menuItems.find((m) => m.href === href);
}
