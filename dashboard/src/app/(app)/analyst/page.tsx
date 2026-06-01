import { createClient } from "@/lib/supabase-server";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const dynamic = "force-dynamic";

export default async function AnalystPage() {
  const supabase = await createClient();
  const { data: briefs } = await supabase
    .from("analyst_briefs")
    .select("id, week_start, summary_md, scout_brief_md, created_at")
    .order("week_start", { ascending: false })
    .limit(20);

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-display tracking-wide">Analyst</h1>
        <p className="text-sm text-muted-foreground">
          Weekly performance digests. The Monday job adds a new one each week.
        </p>
      </header>

      {!briefs || briefs.length === 0 ? (
        <Card className="bg-card border-dashed">
          <CardContent className="py-10 text-center">
            <p className="font-display text-lg mb-1">No briefs yet.</p>
            <p className="text-sm text-muted-foreground">
              Once metrics roll in, the Monday-morning analyst job lands its
              first brief here.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {briefs.map((b) => (
            <Card key={b.id} className="bg-card">
              <CardHeader>
                <CardTitle className="text-base font-mono">
                  Week of {b.week_start}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <section>
                  <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
                    Summary
                  </h3>
                  <pre className="text-xs whitespace-pre-wrap font-mono leading-relaxed">
                    {b.summary_md}
                  </pre>
                </section>
                <section>
                  <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
                    Next scout brief
                  </h3>
                  <pre className="text-xs whitespace-pre-wrap font-mono leading-relaxed">
                    {b.scout_brief_md}
                  </pre>
                </section>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
