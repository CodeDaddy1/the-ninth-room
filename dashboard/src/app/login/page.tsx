"use client";

import { Suspense, useState, useTransition } from "react";
import { useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase-browser";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
  return (
    <div className="min-h-dvh grid place-items-center bg-background p-6">
      <Card className="w-full max-w-md bg-card">
        <CardHeader className="space-y-2">
          <CardTitle className="text-3xl font-display tracking-wide">
            Curated Curiosities
          </CardTitle>
          <CardDescription>
            Private studio. Sign in to continue.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Suspense fallback={<LoginForm denied={false} />}>
            <LoginFormWithSearch />
          </Suspense>
        </CardContent>
      </Card>
    </div>
  );
}

function LoginFormWithSearch() {
  const search = useSearchParams();
  return <LoginForm denied={search.get("denied") === "1"} />;
}

function LoginForm({ denied }: { denied: boolean }) {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    startTransition(async () => {
      const supabase = createClient();
      // No emailRedirectTo — our custom email template uses {{ .SiteURL }},
      // which is the canonical Vercel URL pinned via Management API. Passing
      // a per-deployment origin here would be rejected by Supabase's allow-list.
      const { error } = await supabase.auth.signInWithOtp({ email });
      if (error) {
        setError(error.message);
        return;
      }
      setSent(true);
    });
  };

  if (sent) {
    return (
      <p className="text-sm text-muted-foreground">
        Check <span className="text-foreground">{email}</span> for a sign-in link.
      </p>
    );
  }

  return (
    <>
      {denied && (
        <div className="mb-4 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive-foreground">
          That email isn&apos;t on the allow-list.
        </div>
      )}
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            required
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="bg-background"
          />
        </div>
        {error && <p className="text-sm text-destructive-foreground">{error}</p>}
        <Button type="submit" disabled={pending} className="w-full">
          {pending ? "Sending link…" : "Email me a sign-in link"}
        </Button>
      </form>
    </>
  );
}
