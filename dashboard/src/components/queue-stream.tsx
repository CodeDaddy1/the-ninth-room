"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase-browser";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type EventRow = {
  id: string;
  video_id: string | null;
  stage: string;
  level: string; // 'info' | 'warn' | 'error' — db check constraint enforces
  message: string | null;
  created_at: string;
};

export function QueueStream({ initial }: { initial: EventRow[] }) {
  const [events, setEvents] = useState<EventRow[]>(initial);

  useEffect(() => {
    const supabase = createClient();
    const channel = supabase
      .channel("events:public")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "events" },
        (payload) => {
          setEvents((prev) => [payload.new as EventRow, ...prev].slice(0, 200));
        },
      )
      .subscribe();
    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  if (events.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No events yet. Worker telemetry will stream in here as jobs run.
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {events.map((e) => (
        <li
          key={e.id}
          className="rounded-md border border-border bg-card px-3 py-2 text-sm flex items-start gap-3"
        >
          <Badge
            variant={e.level === "error" ? "destructive" : "outline"}
            className={cn(
              "shrink-0 mt-0.5 text-[10px] uppercase font-mono",
              e.level === "warn" && "border-primary/60 text-primary",
            )}
          >
            {e.level}
          </Badge>
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-xs text-muted-foreground">
                {e.stage}
              </span>
              <span className="text-xs text-muted-foreground/60">
                {new Date(e.created_at).toLocaleTimeString()}
              </span>
            </div>
            {e.message && (
              <div className="text-foreground/90 mt-0.5">{e.message}</div>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
