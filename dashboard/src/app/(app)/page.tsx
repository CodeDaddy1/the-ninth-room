import Link from "next/link";
import { createClient } from "@/lib/supabase-server";
import {
  PILLAR_LABELS,
  PLATFORM_LABELS,
  STATE_LABELS,
} from "@/lib/next-action";
import { Badge } from "@/components/ui/badge";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const supabase = await createClient();
  const { data: videos } = await supabase
    .from("videos")
    .select("slug, topic, pillar, platform_targets, state, updated_at")
    .order("updated_at", { ascending: false });

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <header className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-display tracking-wide">Videos</h1>
          <p className="text-sm text-muted-foreground">
            {videos?.length ?? 0} in flight or shipped.
          </p>
        </div>
        <Link
          href="/videos/new"
          className="text-sm rounded-md bg-primary text-primary-foreground px-4 py-2 hover:bg-primary/90 transition-colors"
        >
          New video
        </Link>
      </header>

      {!videos || videos.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-background/50">
              <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-3 font-medium">Slug</th>
                <th className="px-4 py-3 font-medium">Topic</th>
                <th className="px-4 py-3 font-medium">Pillar</th>
                <th className="px-4 py-3 font-medium">Targets</th>
                <th className="px-4 py-3 font-medium">State</th>
                <th className="px-4 py-3 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {videos.map((v) => (
                <tr
                  key={v.slug}
                  className="border-t border-border hover:bg-background/30 transition-colors"
                >
                  <td className="px-4 py-3 font-mono text-xs">
                    <Link
                      href={`/videos/${v.slug}`}
                      className="text-primary hover:underline"
                    >
                      {v.slug}
                    </Link>
                  </td>
                  <td className="px-4 py-3 max-w-md truncate">{v.topic}</td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {v.pillar ? PILLAR_LABELS[v.pillar] ?? v.pillar : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1 flex-wrap">
                      {(v.platform_targets ?? []).slice(0, 3).map((p) => (
                        <Badge key={p} variant="secondary" className="text-[10px]">
                          {PLATFORM_LABELS[p] ?? p}
                        </Badge>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {STATE_LABELS[v.state] ?? v.state}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">
                    {new Date(v.updated_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-dashed border-border p-12 text-center bg-card/50">
      <p className="font-display text-xl mb-2">Nothing in flight yet.</p>
      <p className="text-sm text-muted-foreground mb-6">
        Run the curiosity-scout to find a topic, or create one directly.
      </p>
      <Link
        href="/videos/new"
        className="inline-block text-sm rounded-md bg-primary text-primary-foreground px-4 py-2 hover:bg-primary/90 transition-colors"
      >
        New video
      </Link>
    </div>
  );
}
