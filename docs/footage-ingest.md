# Footage and ingest — the contract

*Written 2026-08-27, after an audit found the behavioural contract for the
most destructive surface in the pipeline existed only in module docstrings
and three test files.*

Footage is the one thing here that cannot be rebuilt. A cut, a catalog, a
set of proxies — all of it regenerates from the media. The media does not
regenerate from anything. Every rule below follows from that.

---

## 1. Two passes, and why

```
drop / link  ──▶  survey  ──▶  triage  ──▶  ingest  ──▶  takes ▸ b-roll
                  (pass 1)     (human)     (pass 2)
```

Until 2026-08-27 there was one pass. It probed, screened, **transcribed**,
classified, cut takes and built contact sheets — and whisper ran on every
clip with an audio stream before a human had looked at one. Worse, the
desk's own thumbnails were a side effect of a GET that shelled `ffprobe`
and `ffmpeg` per file *while the browser waited* (measured: ~0.79s per
clip, so a 148-clip drop blocked a request for about two minutes).

So the cheap, decision-enabling work was hidden inside a page load, and
the expensive, unattended work was the thing with a progress bar. Caleb
could not reject a clip before it had already cost him the whisper
minutes, because he could not see it until they were spent.

**Pass 1 — `pipeline/survey.py`, job kind `survey`.** One `ffprobe`, the
existing pre-screen, a poster frame, a 1080p H.264 preview. No
transcription. Writes `analysis/survey.json`.

Two phases inside it, and the order is the point: **every poster first**,
then the previews. Posters are one frame; previews are a full decode and
re-encode. Interleaved, clip 40's poster waits behind clip 39's encode and
the desk shows nothing for most of an hour. Split, the grid fills with
real frames in about a minute and gains playback progressively — the
survey rewrites `survey.json` every 8 seconds during phase B.

**Pass 2 — `pipeline/ingest.py`, job kind `ingest`.** Unchanged in shape.
It reads `survey.json` for probe data when present, **skips every rejected
clip**, transcribes the survivors, then takes and b-roll exactly as
before. `catalog.json` keeps its shape, so `timeline.py`, `proxy.py`,
`produce.py`, `build_api.py` and `snap_cuts.py` are untouched.

**A drop auto-starts pass 1 only** (`jobs.AUTOINGEST_KIND`, 20s debounce).
Pass 2 is a human gate, because triage is the thing that happens between
them.

**Existing projects stay on the old path.** A project with a catalog and
no survey renders from `catalog.json` as it always did. No migration, no
backfill, no unasked-for encoding of a 62 GB shoot.

---

## 2. On disk

```
work/<slug>/
  footage/                    THE source of truth — files or symlinks
    <clip>.MP4
    <name>_still.mp4          6s UHD clip baked from a dropped photo
    vo_<SEC>_r<N>_t<N>.webm    teleprompter VO (the vo_ prefix is load-bearing)
    stills/                   the original photos behind *_still.mp4
    .thumbs/<name>.jpg        poster frames          [derived, disposable]
    .proxies/<name>.mp4       1080p H.264 previews   [derived, disposable]
    .trash/                   deleted clips — NO restore route, use Finder
  analysis/
    survey.json               pass 1's record
    catalog.json              pass 2's record — THE media redirection point
    <name>.words.json         whisper word timings
    takes.json, broll.json, sheets/, take_thumbs/
  footage_sources.json        filename -> card label      [sidecar]
  footage_verdicts.json       filename -> stars/rejected  [sidecar]
  footage_sessions.json       filename -> session label   [sidecar]
  ingest_progress.json        live heartbeat
```

**The directory is what EXISTS; the JSON is what has been read.** A file
dropped since the last survey appears on the desk immediately, with no
poster, rather than waiting for a job to become visible. That is what
makes the tiles fill in progressively instead of arriving all at once.

### The allowlist

`pipeline/ingest.py` owns it and says so:

```python
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".mts", ".avi", ".mkv", ".webm")
AUDIO_EXT = (".wav", ".m4a", ".mp3", ".aiff", ".aif")
```

`editroom` imports it by value. The Studio keeps a mirror in
`src/lib/footage-formats.ts` — it has to, because the empty state must
name the formats when the engine is offline — and `footage-formats.test.ts`
reads this Python file and fails if the two disagree. That test exists
because a third copy had already drifted: it was missing `.webm`, the one
extension the comment above was written about, so the teleprompter's own
recordings were refused client-side by a server that accepts them.

### Sidecars, and why nothing hand-authored goes in the catalog

Ingest **rebuilds `catalog.json` from scratch** on every run. Anything
written into it by hand is destroyed by the next analysis. That is why
card labels, b-roll tags, promotions, take verdicts, footage verdicts and
session labels all live beside it.

Every sidecar is written under a lock, atomically (`facts._write_atomic`).
This is not theoretical: 12 concurrent `record_source` calls once kept 2
labels of 12, and a browser folder-drop fires uploads in parallel.

Session labels are keyed **per clip**, not per session, for a sharper
reason: a session is a run of capture times, so dropping one more clip
into the middle of a shoot can move every boundary. A name keyed to
"session 3" would drift onto footage it was never about.

---

## 3. What is extracted from a file

`ingest.probe_file` — one `ffprobe` call:

| Field | Source |
|---|---|
| `duration`, `width`, `height`, `fps`, `vcodec` | streams |
| `has_audio` | a boolean only — no channel count, no layout |
| `created_at` | `format.tags.creation_time`, UTC ISO-8601 |
| `sig` | `screen.content_sig` — sha1 of the first + last MB, 64 bits |

`created_at` was fetched and thrown away until 2026-08-27; `-show_format`
was always requested and only `duration` read. It is what makes shot order
and session clustering possible, and a container that carries no tag
simply has none — the desk omits the fact rather than inventing one.

**Deliberately NOT extracted:** timecode, camera make/model, audio channel
count, rotation flags, per-clip LUFS. Portrait is inferred from
`height > width`, so a rotation-flagged clip is treated as landscape.

**There is no checksum.** `content_sig` reads the first and last megabyte
only, truncated to 64 bits, and is compared only between files of
identical byte size. A file corrupted in the MIDDLE passes as identical.
This is a known, accepted limit (Caleb, 2026-08-27): footage integrity is
not the risk being managed here. Do not describe it as a checksum.

---

## 4. Deletion — the law

Footage deletion is the only irreversible action in the Studio.

**`_delete_footage(slug, name, force)`**

1. Not a file and not a symlink → `IngestError("no clip named ...")`.
2. A beat's TAKE comes from this file → **refuse always, even under
   force**, code `take_in_cut`. Losing a beat's take is a re-cut decision,
   and nothing here is entitled to make it.
3. Covers point at this file and not `force` → refuse, code `in_the_cut`,
   naming each `clip_id covers beat_id`.
4. Under `force`: `_broll_detach` runs FIRST, per cover, so an interrupted
   delete leaves an undo entry rather than a plan pointing at a binned file.
5. `os.replace` into `footage/.trash/`. For a symlink this moves the LINK,
   never the library original. A `*_still.mp4` takes its source photo along.
6. `facts.forget_source` / `forget_verdicts` / `forget_session_labels` —
   `_uniquify` only guards names currently present, so re-dropping the same
   card gives the same filename back, and it must not inherit the label,
   rating or rejection of a clip it never was.

**`_clear_footage(slug, force)`** obeys the same law. It did not until
2026-08-27: it walked the directory knowing nothing about the cut, so ONE
clip was protected and all 368 were not — the blunt verb could do exactly
what the precise one refuses. It now refuses with `in_the_cut` when the cut
is using anything, naming the beats and counting the covers. `force` is
allowed to take the cut with it, because "remove all" means start over; it
cannot do that a beat at a time (`_beat_remove` refuses the last beat), so
the whole plan moves to `.trash` — **before any media does**.

`footage/.trash` has **no restore route**. Recovery is Finder. Say so in
any UI that offers a delete.

---

## 5. Failure

| Failure | Behaviour |
|---|---|
| Corrupt / unreadable | named in `skipped`, run continues. One bad clip never sinks 368 |
| Zero duration | same — "interrupted recording?" |
| Empty footage dir | `IngestError(code="no_media")` — hard stop |
| No speech at all | `IngestError(code="no_speech")` from `takes.analyze` |
| Everything rejected | `IngestError(code="all_rejected")` |
| Duplicate in one run | `screened_out` with a reason. Never moved, never deleted |
| Duplicate on upload | dropped silently — re-dropping a whole card must be safe |
| Upload in flight | `_tmp.` prefix, skipped by every walker |
| Truncated `.words.json` | deleted and re-transcribed. It used to raise on every later run of that project, forever |
| Engine restart mid-job | job → `failed: "engine restarted mid-job"` |

**A coded refusal reaches the desk.** `IngestError` has carried a stable
`code` since the P3 error band, and both request handlers built
`{"error": str(e)}` and dropped it — so codes only ever arrived through the
JOB record, and every synchronous refusal reached the UI as prose. Desks
were forced to match on message text, the one thing `job-failure.ts`
forbids. `_err_body` sends the code now. **Match on `error_code`, never on
the message.**

### Atomicity

`catalog.json`, `takes.json`, `broll.json`, `survey.json`,
`ingest_progress.json` and every sidecar are written tmp + `os.replace`,
with a tmp name carrying pid and thread. A FIXED `.tmp` sibling is worse
than no atomicity once two writers exist — one's replace moves the file
out from under the other.

There is still **no journal and no rollback**. A re-run rebuilds from
probe. `broll.catalog_broll` merges rather than rebuilds, to preserve ids
and descriptions; `catalog.json` and `takes.json` do not, which is why
`_stamp_takes` re-applies verdicts after every ingest.

---

## 6. The tests are the contract

| File | What it pins |
|---|---|
| `test_footage_state.py` | the inventory arithmetic — count the INTERSECTION, never the catalog; a half-written catalog must not take the desk down |
| `test_footage_linking.py` | symlinks, and the destructive case: same filename + different content must NOT relink |
| `test_footage_delete_guard.py` | the deletion law above, single and bulk |
| `test_survey.py` | pass 1: resumability, one bad clip, posters BEFORE previews, and that the poster seeks into the clip |
| `test_footage_verdicts.py` | triage, and that pass 2 honours it |
| `test_ingest_durability.py` | atomic writes, and the truncated-cache recovery |

Two of these pin something invisible to ordinary assertions. The poster
test checks `-ss` is present **and sits before `-i`**: the first cut of
the refactor dropped it, so every poster was frame 0 — routinely a
fade-in — and every test still passed, because a file was written. If you
change how ffmpeg is invoked, run those.

---

## 7. Rules for anyone changing this

1. **The engine owns the catalog.** Anything a human authored goes in a
   sidecar.
2. **Never widen a delete without widening its guard.** The bulk verb and
   the single verb obey one law.
3. **A refusal a desk can act on earns an `error_code`.** Most failures
   should not have one — they get the engine's own words and no door.
4. **Derived files are disposable and must be namespaced with a dot** so
   every walker skips them.
5. **A GET does not write.** `_footage_state` shelled ffmpeg during a page
   load for months; that is most of why the desk felt slow.
6. **Anything touching footage, Resolve, or a destructive delete is
   Needs-Caleb.** Append it to `.claude/reminders.md` rather than doing it.
