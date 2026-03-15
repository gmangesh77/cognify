"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Compass,
  FileText,
  Search,
  Send,
  Settings,
} from "lucide-react";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Topics", href: "/topics", icon: Compass },
  { label: "Articles", href: "/articles", icon: FileText },
  { label: "Research", href: "/research", icon: Search },
  { label: "Publishing", href: "/publishing", icon: Send },
  { label: "Settings", href: "/settings", icon: Settings },
] as const;

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-60 flex-col border-r border-border bg-neutral-50 px-6 py-8">
      <div className="mb-8">
        <Link href="/" className="font-heading text-xl font-bold text-neutral-900">
          Cognify
        </Link>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ label, href, icon: Icon }) => {
          const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary-light text-primary"
                  : "text-neutral-500 hover:bg-neutral-50 hover:text-neutral-900"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
