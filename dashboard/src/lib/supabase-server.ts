import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import type { Database } from "./db.types";

/**
 * Server-side Supabase client for App Router (RSCs, route handlers, server
 * actions). Reads/writes the session cookie so RLS sees the signed-in user.
 */
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            for (const { name, value, options } of cookiesToSet) {
              cookieStore.set(name, value, options);
            }
          } catch {
            // Called from a Server Component — cookie mutations land in a
            // middleware response instead.
          }
        },
      },
    },
  );
}

/**
 * Admin client using the service-role key. **Server-only** — never import
 * from a client component. Bypasses RLS; use for worker-style writes from
 * server actions or route handlers.
 */
export function createAdminClient() {
  // Lazy import to avoid pulling cookies() when admin is all we need.
  const { createClient } = require("@supabase/supabase-js") as typeof import("@supabase/supabase-js");
  return createClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_KEY!,
    { auth: { persistSession: false, autoRefreshToken: false } },
  );
}
