-- ============================================================================
-- Curated Curiosities — initial schema (Phase 1)
-- ============================================================================
-- Tables: videos, video_assets, ready_tray, metrics, music_tracks,
--         analyst_briefs, events, jobs, reminders.
-- RLS:    single-owner model. Service role bypasses RLS for the local worker.
-- ============================================================================

-- ---- helpers --------------------------------------------------------------

-- A SQL-executing RPC so scripts/apply-migration.mjs can apply future
-- migrations via the REST endpoint with the service key.
-- Service-role-only. Never grant to anon/authenticated.
create or replace function public.query(query text)
returns void
language plpgsql
security definer
as $$
begin
    execute query;
end;
$$;
revoke all on function public.query(text) from public, anon, authenticated;
grant execute on function public.query(text) to service_role;

-- updated_at trigger helper
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

-- Single-owner helper: true when the calling user's JWT email matches.
-- Wrapped in (select ...) so Postgres caches the result per query.
create or replace function public.is_owner()
returns boolean
language sql
stable
as $$
    select (select coalesce(auth.jwt() ->> 'email', '')) = 'phamfinance@icloud.com'
$$;

-- ============================================================================
-- videos — one row per video in flight or shipped
-- ============================================================================

create table public.videos (
    id uuid primary key default gen_random_uuid(),
    slug text not null unique,
    topic text not null,
    pillar text,
    platform_targets text[] not null default array[]::text[],
    state text not null default 'queued',
    script_md text,
    shot_list_json jsonb,
    selections_json jsonb,
    rough_cut_path text,
    rough_cut_url text,
    thumbnail_storage_path text,
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint videos_pillar_check check (
        pillar is null or pillar in (
            'hidden_in_plain_sight','unsolved','how_it_works',
            'lost_forgotten','scales_of_wonder','human_strange'
        )
    ),
    constraint videos_state_check check (state in (
        'queued','scripting','shots','fetching','awaiting_vo',
        'assembling','ready','tray','pushed','published',
        'failed_scripting','failed_shots','failed_fetching',
        'failed_assembling','failed_tray'
    ))
);
create index videos_state_idx on public.videos (state);
create index videos_updated_at_idx on public.videos (updated_at desc);

create trigger videos_set_updated_at
before update on public.videos
for each row execute function public.set_updated_at();

-- ============================================================================
-- video_assets — per-shot stock candidates; files live on the local Mac
-- ============================================================================

create table public.video_assets (
    id uuid primary key default gen_random_uuid(),
    video_id uuid not null references public.videos(id) on delete cascade,
    shot_id text not null,
    candidate_idx int not null,
    provider text not null,
    file_path text not null,
    width int,
    height int,
    duration_sec numeric,
    license text,
    source_page text,
    picked boolean not null default false,
    needs_rights_check boolean not null default false,
    created_at timestamptz not null default now(),
    constraint video_assets_provider_check check (
        provider in ('pexels','pixabay','manual','ai_gen','slate')
    )
);
create index video_assets_video_id_idx on public.video_assets (video_id);
-- Exactly one picked candidate per shot.
create unique index video_assets_picked_one_per_shot_idx
    on public.video_assets (video_id, shot_id)
    where picked = true;

-- ============================================================================
-- ready_tray — one row per (video, platform) when the post-ready package exists
-- ============================================================================

create table public.ready_tray (
    id uuid primary key default gen_random_uuid(),
    video_id uuid not null references public.videos(id) on delete cascade,
    platform text not null,
    title text,
    caption text,
    hashtags text[] not null default array[]::text[],
    description text,
    timestamps text,
    thumbnail_brief text,
    on_screen_text text[],
    music_credit text,
    deliverable_path text,
    exported_at timestamptz,
    pushed_at timestamptz,
    posted_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint ready_tray_platform_check check (platform in (
        'youtube_long','youtube_short',
        'instagram_reel','instagram_carousel','instagram_story'
    )),
    unique (video_id, platform)
);
create trigger ready_tray_set_updated_at
before update on public.ready_tray
for each row execute function public.set_updated_at();

-- ============================================================================
-- metrics — manually entered, one row per (video, platform, time_window)
-- ============================================================================

create table public.metrics (
    id uuid primary key default gen_random_uuid(),
    video_id uuid not null references public.videos(id) on delete cascade,
    platform text not null,
    time_window text not null,
    views int,
    likes int,
    comments int,
    saves int,
    shares int,
    watch_time_seconds int,
    retention_pct numeric,
    captured_at timestamptz not null default now(),
    constraint metrics_time_window_check check (time_window in ('48h','7d','28d')),
    unique (video_id, platform, time_window)
);
create index metrics_video_id_idx on public.metrics (video_id);

-- ============================================================================
-- music_tracks — licensed library registered on the worker
-- ============================================================================

create table public.music_tracks (
    id uuid primary key default gen_random_uuid(),
    label text not null,
    file_path text not null unique,
    license_source text,
    license_credit text,
    bpm int,
    mood text,
    duration_sec numeric,
    created_at timestamptz not null default now()
);

-- ============================================================================
-- analyst_briefs — weekly performance digest + next scout brief
-- ============================================================================

create table public.analyst_briefs (
    id uuid primary key default gen_random_uuid(),
    week_start date not null unique,
    summary_md text not null,
    scout_brief_md text not null,
    metrics_snapshot jsonb,
    created_at timestamptz not null default now()
);

-- ============================================================================
-- events — worker telemetry for the dashboard's live queue
-- ============================================================================

create table public.events (
    id uuid primary key default gen_random_uuid(),
    video_id uuid references public.videos(id) on delete cascade,
    stage text not null,
    level text not null default 'info',
    message text,
    payload jsonb,
    created_at timestamptz not null default now(),
    constraint events_level_check check (level in ('info','warn','error'))
);
create index events_video_id_idx on public.events (video_id);
create index events_created_at_idx on public.events (created_at desc);

-- ============================================================================
-- jobs — work queue for the local worker daemon
-- ============================================================================

create table public.jobs (
    id uuid primary key default gen_random_uuid(),
    type text not null,
    video_id uuid references public.videos(id) on delete cascade,
    payload jsonb,
    status text not null default 'queued',
    error text,
    attempts int not null default 0,
    started_at timestamptz,
    ended_at timestamptz,
    created_at timestamptz not null default now(),
    constraint jobs_type_check check (type in (
        'fetch','assemble','music_duck','ready_tray','analyst_weekly','register_music'
    )),
    constraint jobs_status_check check (status in ('queued','running','succeeded','failed'))
);
create index jobs_status_idx on public.jobs (status) where status in ('queued','running');
create index jobs_created_at_idx on public.jobs (created_at);

-- ============================================================================
-- reminders — metrics-capture nudges (48h IG, 7d/28d YT)
-- ============================================================================

create table public.reminders (
    id uuid primary key default gen_random_uuid(),
    video_id uuid not null references public.videos(id) on delete cascade,
    platform text not null,
    time_window text not null,
    fire_at timestamptz not null,
    fired_at timestamptz,
    dismissed_at timestamptz,
    created_at timestamptz not null default now(),
    constraint reminders_time_window_check check (time_window in ('48h','7d','28d')),
    unique (video_id, platform, time_window)
);
create index reminders_pending_idx
    on public.reminders (fire_at)
    where fired_at is null and dismissed_at is null;

-- ============================================================================
-- RLS — single-owner model
-- ============================================================================
-- service_role bypasses RLS automatically (used by the worker).
-- authenticated owner gets full CRUD via the dashboard.
-- anon and non-owner authenticated get nothing (no policy = deny).

alter table public.videos          enable row level security;
alter table public.video_assets    enable row level security;
alter table public.ready_tray      enable row level security;
alter table public.metrics         enable row level security;
alter table public.music_tracks    enable row level security;
alter table public.analyst_briefs  enable row level security;
alter table public.events          enable row level security;
alter table public.jobs            enable row level security;
alter table public.reminders       enable row level security;

create policy "owner all" on public.videos
    for all to authenticated using (public.is_owner()) with check (public.is_owner());
create policy "owner all" on public.video_assets
    for all to authenticated using (public.is_owner()) with check (public.is_owner());
create policy "owner all" on public.ready_tray
    for all to authenticated using (public.is_owner()) with check (public.is_owner());
create policy "owner all" on public.metrics
    for all to authenticated using (public.is_owner()) with check (public.is_owner());
create policy "owner all" on public.music_tracks
    for all to authenticated using (public.is_owner()) with check (public.is_owner());
create policy "owner all" on public.analyst_briefs
    for all to authenticated using (public.is_owner()) with check (public.is_owner());
create policy "owner all" on public.events
    for all to authenticated using (public.is_owner()) with check (public.is_owner());
create policy "owner all" on public.jobs
    for all to authenticated using (public.is_owner()) with check (public.is_owner());
create policy "owner all" on public.reminders
    for all to authenticated using (public.is_owner()) with check (public.is_owner());

-- ============================================================================
-- Realtime — publish events + jobs for live dashboard updates
-- ============================================================================

alter publication supabase_realtime add table public.events;
alter publication supabase_realtime add table public.jobs;
alter publication supabase_realtime add table public.videos;
