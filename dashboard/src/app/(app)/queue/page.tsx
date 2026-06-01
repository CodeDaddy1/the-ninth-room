import { createClient } from "@/lib/supabase-server";
import { QueueStream } from "@/components/queue-stream";

export const dynamic = "force-dynamic";

export default async function QueuePage() {
  const supabase = await createClient();
  const { data: initial } = await supabase
    .from("events")
    .select("id, video_id, stage, level, message, created_at")
    .order("created_at", { ascending: false })
    .limit(50);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <header className="mb-6">
        <h1 className="text-2xl font-display tracking-wide">Queue</h1>
        <p className="text-sm text-muted-foreground">
          Live worker telemetry. New events appear at the top.
        </p>
      </header>
      <QueueStream initial={initial ?? []} />
    </div>
  );
}
