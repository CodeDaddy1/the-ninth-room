import { createBrowserClient } from "@supabase/ssr";
import type { Database } from "./db.types";

/**
 * Browser-side Supabase client. Uses the publishable (anon) key — safe to
 * ship in the bundle. RLS guards everything; only the signed-in owner sees
 * data. See `db.types.ts` for the typed schema.
 */
export function createClient() {
  return createBrowserClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
