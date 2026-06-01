import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { PILLAR_LABELS, PLATFORM_LABELS } from "@/lib/next-action";
import { createVideo } from "./actions";

export default function NewVideoPage() {
  return (
    <div className="p-8 max-w-2xl mx-auto">
      <header className="mb-6">
        <h1 className="text-2xl font-display tracking-wide">New video</h1>
        <p className="text-sm text-muted-foreground">
          Creates a row in <code>videos</code> and starts the workflow.
        </p>
      </header>

      <Card className="bg-card">
        <CardHeader>
          <CardTitle>Topic</CardTitle>
          <CardDescription>
            Slug auto-derives from the topic. Override if you want.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form action={createVideo} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="topic">Topic</Label>
              <Input
                id="topic"
                name="topic"
                required
                placeholder="The 1977 Wow! signal — why we still can't explain it"
                className="bg-background"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="slug">
                Slug{" "}
                <span className="text-muted-foreground font-normal">
                  (optional)
                </span>
              </Label>
              <Input
                id="slug"
                name="slug"
                placeholder="auto-from-topic"
                className="bg-background font-mono"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="pillar">Pillar</Label>
              <select
                id="pillar"
                name="pillar"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                defaultValue=""
              >
                <option value="">— pick a pillar —</option>
                {Object.entries(PILLAR_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label>Platform targets</Label>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(PLATFORM_LABELS).map(([k, v]) => (
                  <label
                    key={k}
                    className="flex items-center gap-2 text-sm rounded-md border border-border bg-background px-3 py-2 cursor-pointer hover:border-primary/60"
                  >
                    <input
                      type="checkbox"
                      name="platform_targets"
                      value={k}
                      className="accent-primary"
                    />
                    {v}
                  </label>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes">
                Notes{" "}
                <span className="text-muted-foreground font-normal">
                  (optional)
                </span>
              </Label>
              <textarea
                id="notes"
                name="notes"
                rows={3}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                placeholder="Anything the scriptwriter should know."
              />
            </div>

            <Button type="submit" className="w-full">
              Create video
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
