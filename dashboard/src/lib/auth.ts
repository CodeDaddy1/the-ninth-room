import { redirect } from "next/navigation";
import { createClient } from "./supabase-server";

/**
 * Server-side helper: require an authenticated owner for the calling RSC.
 * Throws via `redirect("/login")` if not signed in. (The middleware also
 * guards routes, but RSC/server-action code paths sometimes bypass it.)
 */
export async function requireOwner() {
  const supabase = await createClient();
  const { data } = await supabase.auth.getUser();
  if (!data.user) redirect("/login");

  const allowed = process.env.ALLOWED_EMAIL?.toLowerCase();
  if (allowed && data.user.email?.toLowerCase() !== allowed) {
    redirect("/login?denied=1");
  }
  return data.user;
}
