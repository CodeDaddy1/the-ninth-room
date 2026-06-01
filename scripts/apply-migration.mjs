#!/usr/bin/env node
/**
 * apply-migration.mjs — apply a SQL migration to the Supabase project.
 *
 * The Supabase MCP can't always reach a freshly-created free-tier project,
 * so we apply migrations via the REST RPC endpoint using the service-role key.
 *
 * Usage:
 *   node scripts/apply-migration.mjs supabase/migrations/0001_init.sql
 *   node scripts/apply-migration.mjs --all     # apply every file in order
 *
 * Env required (from .env at repo root):
 *   SUPABASE_URL
 *   SUPABASE_SERVICE_KEY
 */
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, basename } from "node:path";

const ENV_PATH = new URL("../.env", import.meta.url);
if (existsSync(ENV_PATH)) {
  for (const line of readFileSync(ENV_PATH, "utf8").split("\n")) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
}

const SUPABASE_URL = process.env.SUPABASE_URL;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;
if (!SUPABASE_URL || !SERVICE_KEY) {
  console.error("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env");
  process.exit(2);
}

const arg = process.argv[2];
if (!arg) {
  console.error("Usage: apply-migration.mjs <file.sql> | --all");
  process.exit(2);
}

const MIGRATIONS_DIR = new URL("../supabase/migrations/", import.meta.url).pathname;

const files = arg === "--all"
  ? readdirSync(MIGRATIONS_DIR).filter((f) => f.endsWith(".sql")).sort().map((f) => join(MIGRATIONS_DIR, f))
  : [arg];

for (const file of files) {
  const sql = readFileSync(file, "utf8");
  console.log(`\n→ applying ${basename(file)} (${sql.length} bytes)`);

  // Use the Postgres REST API via the `query` RPC if installed, otherwise
  // fall back to the Management API SQL endpoint.
  const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/query`, {
    method: "POST",
    headers: {
      "apikey": SERVICE_KEY,
      "Authorization": `Bearer ${SERVICE_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query: sql }),
  });

  if (!res.ok) {
    const body = await res.text();
    console.error(`  ✗ ${res.status} ${res.statusText}\n${body.slice(0, 800)}`);
    console.error(`\n  Hint: install a SQL-runner RPC in your Supabase project (see supabase/migrations/0000_install_query_rpc.sql) or apply this migration manually via the SQL editor.`);
    process.exit(1);
  }

  console.log(`  ✓ applied`);
}

console.log("\nDone.");
