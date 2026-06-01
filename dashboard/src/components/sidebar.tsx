"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Home, Plus, ListTodo, BarChart3, LogOut } from "lucide-react";

const NAV = [
  { href: "/", label: "Videos", icon: Home },
  { href: "/videos/new", label: "New video", icon: Plus },
  { href: "/queue", label: "Queue", icon: ListTodo },
  { href: "/analyst", label: "Analyst", icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-60 shrink-0 border-r border-border bg-card flex flex-col">
      <div className="px-6 py-6 border-b border-border">
        <div className="font-display text-lg tracking-wide leading-none">
          Curated
        </div>
        <div className="font-display text-lg tracking-wide leading-none text-primary">
          Curiosities
        </div>
        <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mt-3">
          Studio
        </div>
      </div>
      <nav className="flex-1 py-4">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-6 py-2 text-sm transition-colors",
                active
                  ? "text-primary bg-background"
                  : "text-muted-foreground hover:text-foreground hover:bg-background/40",
              )}
            >
              <Icon className="size-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <form action="/auth/signout" method="post" className="border-t border-border p-4">
        <button
          type="submit"
          className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <LogOut className="size-3.5" />
          Sign out
        </button>
      </form>
    </aside>
  );
}
