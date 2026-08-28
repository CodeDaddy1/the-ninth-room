# Engine

The Python pipeline that turns a visit into an episode. It owns every file
under `work/<slug>/` and is authoritative on the domain — the Studio renders
what this decides.

## Language

### The work

**Project**:
One visit, one `work/<slug>/`. Identified everywhere by its slug.
_Avoid_: video, shoot, folder

**Origin**:
Whether an episode is filmed first and written from what came back
(`footage`) or written first and shot to the script (`script`). Chosen at
creation; the phase order derives from it.
_Avoid_: type, mode, documentary flag

**Delivery**:
Whether an episode ships long (16:9) or short (9:16). Chosen at creation
alongside origin; orientation and format derive from it.
_Avoid_: format, aspect

### Speech

**Take**:
A continuous stretch of speech bounded by silence of 1.4s or more. Takes are
measured at ingest and grouped with their retakes; the story designer picks
one per group, or none.
_Avoid_: clip, recording, segment

**Section**:
A unit of the written script, identified `CH2.S3`. Section ids are
**identity, not ordering** — recordings match to sections by filename.
_Avoid_: line, paragraph, block

**Kind**:
What a take or section IS, and therefore which rules apply to it. Four
values. `oncamera` quotes a take that already exists, so its text is a
transcript and editing it would lie. `vo` is written to be performed later
as a teleprompter recording, and its picture is hard-blocked — a vo line
owes a visual. `desk` is a real-camera performance where the face is the
shot, so it inherits none of the vo exemptions. `picture` is a beat with no
speech under it at all.
_Avoid_: type, flag, prefix, voiceover

### The cut

**Beat**:
One unit of the cut. A beat carries at most one take — **a beat may have no
take**, in which case it is a `picture` beat and is pure coverage.
_Avoid_: shot, slot, entry

**Chapter**:
A named span of the cut that beats belong to. Chapter ids are unique and
validated.
_Avoid_: act, part, scene

**Cover**:
B-roll attached over a beat, with its own in-point and duration. Coverage
supports a beat; it is not itself a beat.
_Avoid_: b-roll beat, overlay, insert

**Edit plan**:
The document that IS the cut — theme, hook, beat order, take picks, kill
list, coverage placement, transition policy. Ten artifacts key on its beat
ids.
_Avoid_: timeline, EDL, sequence

**Conform**:
An edit applied to a built cut after assembly, recorded as an op rather than
by rebuilding.
_Avoid_: fix, patch, surgery

### Running work

**Job**:
A unit of engine work with a kind, a slug, a lane and a lifecycle the Studio
can watch. Not every job dispatches a session.
_Avoid_: task, run

**Session**:
A dispatched headless Claude Code run. A session is billed in minutes, which
is why any gate a file check can answer must answer **before** the dispatch,
not after.
_Avoid_: agent run, subprocess

**Precondition**:
A named, declared condition a job requires before it may run, carrying its
own message and the surface that satisfies it. The runner guards on it and
the Studio renders it; both read the same declaration.
_Avoid_: guard, check, validation

**Retryable**:
Whether running a job a second time is safe. A job that appends, imports
into Resolve, or touches the outside world is not retryable and says so.
_Avoid_: idempotent (the property), rerunnable

### Output

**Preview**:
A low-cost proxy of a beat or take, used for review. Never what ships.
_Avoid_: proxy (in user-facing text), thumbnail

**Master**:
The rendered deliverable, pinned to the timeline's own resolution.
_Avoid_: export, final, render

**Verdict**:
A decision recorded against a take or a beat — approved, reworked, cut. A
verdict belongs to the **shot**, not the position it sat in.
_Avoid_: status, review state, rating
