import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CopyButton } from "@/components/copy-button";
import { Terminal, Wrench, Hand } from "lucide-react";
import { getNextAction, STATE_LABELS } from "@/lib/next-action";

export function NextActionCard({
  state,
  slug,
  topic,
}: {
  state: string;
  slug: string;
  topic: string;
}) {
  const action = getNextAction(state, slug, topic);
  if (!action) {
    return (
      <Card className="bg-card">
        <CardHeader>
          <CardTitle className="text-base">No pending action</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          State <code className="rounded bg-muted px-1.5 py-0.5">{state}</code>{" "}
          ({STATE_LABELS[state] ?? state}) has no follow-up action.
        </CardContent>
      </Card>
    );
  }

  const Icon =
    action.kind === "agent" ? Terminal : action.kind === "worker_job" ? Wrench : Hand;

  return (
    <Card className="bg-card border-primary/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon className="size-4 text-primary" />
          Next action — {STATE_LABELS[state] ?? state}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {action.kind === "agent" && action.slash && (
          <>
            <p className="text-sm text-muted-foreground">
              Paste this slash command in Claude Code (project root). The
              worker watches for{" "}
              <code className="rounded bg-muted px-1.5 py-0.5">
                {action.expectFile}
              </code>{" "}
              and advances state to{" "}
              <code className="rounded bg-muted px-1.5 py-0.5">
                {action.advancesTo}
              </code>
              .
            </p>
            <div className="flex items-center gap-2 rounded-md border border-border bg-background p-3 font-mono text-sm">
              <code className="flex-1 whitespace-pre-wrap break-all">
                {action.slash}
              </code>
              <CopyButton text={action.slash} />
            </div>
          </>
        )}
        {action.kind === "worker_job" && (
          <p className="text-sm text-muted-foreground">
            Worker job: <code className="rounded bg-muted px-1.5 py-0.5">{action.jobType}</code>.
            Trigger from the queue page (Phase 4 wires the daemon).
          </p>
        )}
        {action.kind === "manual" && (
          <p className="text-sm">{action.instruction}</p>
        )}
      </CardContent>
    </Card>
  );
}
