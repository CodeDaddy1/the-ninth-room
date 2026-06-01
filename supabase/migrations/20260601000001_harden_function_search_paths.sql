-- Pin search_path on every function we own so the Supabase security linter
-- (function_search_path_mutable) is satisfied. Schemas referenced inside
-- each function are listed explicitly.

alter function public.set_updated_at() set search_path = '';

alter function public.is_owner() set search_path = 'auth';

-- query() runs arbitrary EXECUTE on behalf of the service role; an empty
-- search_path means the SQL it executes must fully qualify any unqualified
-- identifier. That's the safer posture — the caller (apply-migration.mjs)
-- writes fully-qualified DDL.
alter function public.query(text) set search_path = '';
