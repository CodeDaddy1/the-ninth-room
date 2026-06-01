import Link from "next/link";
import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase-server";
import { NextActionCard } from "@/components/next-action-card";
import {
  PILLAR_LABELS,
  PLATFORM_LABELS,
  STATE_LABELS,
} from "@/lib/next-action";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export const dynamic = "force-dynamic";

export default async function VideoDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const supabase = await createClient();
  const { data: video } = await supabase
    .from("videos")
    .select("*")
    .eq("slug", slug)
    .maybeSingle();
  if (!video) notFound();

  const { data: shots } = video.shot_list_json
    ? { data: (video.shot_list_json as { shots?: unknown[] })?.shots ?? [] }
    : await supabase
        .from("video_assets")
        .select("shot_id, provider, file_path, picked")
        .eq("video_id", video.id)
        .order("shot_id");

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <header className="space-y-2">
        <div className="text-xs font-mono text-muted-foreground">
          <Link href="/" className="hover:text-foreground">
            ← Videos
          </Link>
        </div>
        <div className="flex items-start justify-between gap-6">
          <div>
            <h1 className="text-2xl font-display tracking-wide">
              {video.topic}
            </h1>
            <p className="font-mono text-xs text-muted-foreground mt-1">
              {video.slug}
            </p>
          </div>
          <div className="flex flex-col gap-1 items-end text-xs text-muted-foreground">
            <Badge variant="outline" className="font-mono">
              {STATE_LABELS[video.state] ?? video.state}
            </Badge>
            {video.pillar && (
              <span>{PILLAR_LABELS[video.pillar] ?? video.pillar}</span>
            )}
          </div>
        </div>
        <div className="flex gap-1 flex-wrap pt-2">
          {(video.platform_targets ?? []).map((p: string) => (
            <Badge key={p} variant="secondary" className="text-[10px]">
              {PLATFORM_LABELS[p] ?? p}
            </Badge>
          ))}
        </div>
      </header>

      <NextActionCard state={video.state} slug={video.slug} topic={video.topic} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-card">
          <CardHeader>
            <CardTitle className="text-base">Script</CardTitle>
          </CardHeader>
          <CardContent>
            {video.script_md ? (
              <pre className="text-xs whitespace-pre-wrap font-mono leading-relaxed max-h-96 overflow-y-auto">
                {video.script_md}
              </pre>
            ) : (
              <p className="text-sm text-muted-foreground">
                Not written yet. The scriptwriter agent will populate this.
              </p>
            )}
          </CardContent>
        </Card>

        <Card className="bg-card">
          <CardHeader>
            <CardTitle className="text-base">Shot list</CardTitle>
          </CardHeader>
          <CardContent>
            {Array.isArray(shots) && shots.length > 0 ? (
              <ul className="space-y-2 text-sm max-h-96 overflow-y-auto">
                {shots.map((s, i) => (
                  <li
                    key={i}
                    className="border-b border-border/40 pb-2 last:border-b-0"
                  >
                    <div className="font-mono text-xs text-muted-foreground">
                      {(s as { shot_id?: string }).shot_id ?? `#${i + 1}`}
                    </div>
                    <div className="text-foreground">
                      {(s as { visual?: string; script_line?: string }).visual ??
                        (s as { script_line?: string }).script_line ??
                        "—"}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">
                No shot list yet. The asset-scout agent will populate this.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {video.notes && (
        <Card className="bg-card">
          <CardHeader>
            <CardTitle className="text-base">Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">
              {video.notes}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
