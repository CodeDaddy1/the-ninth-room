import { NextResponse, type NextRequest } from "next/server";
import { createClient } from "@/lib/supabase-server";

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const code = url.searchParams.get("code");
  const redirect = url.searchParams.get("redirect") ?? "/";

  if (!code) {
    return NextResponse.redirect(new URL(`/login?denied=1`, url.origin));
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) {
    return NextResponse.redirect(new URL(`/login?denied=1`, url.origin));
  }

  return NextResponse.redirect(new URL(redirect, url.origin));
}
