-- ============================================================================
-- Phase 5 — dashboard editing
--
-- What this adds and why:
--   1. A private `media` Storage bucket. Two kinds of small derived files live
--      here so the Vercel-hosted dashboard can show them:
--        thumbs/<slug>/<shot_id>/<filename>.jpg  — one thumbnail per fetched
--                                                  stock candidate (asset picker)
--        previews/<slug>.mp4                     — low-res rough-cut preview
--      The full-resolution masters (candidate mp4s, rough_cut.mp4) never leave
--      the local Mac; only these derived files are uploaded, keeping us inside
--      the free tier. No storage RLS policies on purpose: the worker writes
--      with the service key, and the dashboard signs URLs server-side with the
--      service key too, so the anon/authenticated roles never touch storage.
--   2. video_assets.thumb_storage_path — where a candidate's thumbnail lives
--      in the bucket. Null means "no thumbnail uploaded (yet)".
--   3. videos.preview_storage_path — where the rough-cut preview lives.
--      Null until the first assemble completes.
--
-- What breaks if this is wrong: the asset picker renders empty tiles and the
-- rough-cut player has nothing to play — but nothing in the pipeline itself
-- fails, because disk paths (video_assets.file_path, videos.rough_cut_path)
-- remain the worker's source of truth.
-- ============================================================================

insert into storage.buckets (id, name, public, file_size_limit)
values ('media', 'media', false, 52428800);

alter table public.video_assets
    add column thumb_storage_path text;
comment on column public.video_assets.thumb_storage_path is
    'Object path in the media bucket for this candidate''s thumbnail jpg; dashboard signs it at render.';

alter table public.videos
    add column preview_storage_path text;
comment on column public.videos.preview_storage_path is
    'Object path in the media bucket for the low-res rough-cut preview mp4; the full-res master stays on the local Mac.';
