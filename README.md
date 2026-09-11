# The Ninth Room

A YouTube channel, and the fully local program that edits its episodes.

The channel: a family explores the world's most interesting places, museums,
parks, ships, anywhere worth wondering about, and every episode finds the one
thing that was not on the map.

The program: raw footage goes into `work/<slug>/footage/`, and one command in
Claude Code runs the pipeline. It transcribes, picks the best takes, cuts dead
space, designs the story, builds the timeline in DaVinci Resolve (cuts,
transitions, brand cards, captions) and renders the finished episode. Every
stage runs on the machine by default. Two paid cloud paths exist and are
opt-in: `ingest --api` sends transcription to the OpenAI Whisper API when
proper nouns matter, and the sound-library pull needs an Epidemic Sound
subscription.

## Why this is public

This repository is a portfolio artifact. It is one person's working tool for
one channel, published so the code can be read, not so it can be reused as a
product. The case study that explains it is at
https://calebpham.com/work/the-ninth-room. It is unsupported: no issue triage
or feature requests are promised.

## What it needs

- macOS. The Resolve bridge and the launchd service are macOS-specific.
- `/usr/bin/python3` (3.9). Third-party packages: `pip3 install faster-whisper Pillow numpy`.
- ffmpeg, Google Chrome (headless rendering of overlay cards).
- DaVinci Resolve 21 (free) with the in-app Lua bridge installed as described
  in `docs/resolve-findings.md`.
- Claude Code. Editorial judgment runs as subagents defined in
  `.claude/agents/`; there are no API calls.

Machine-specific locations (the work directory, the Claude binary, the iCloud
drop folder) come from the environment or a `.env` file; see `.env.example`
and `pipeline/paths.py`.

## Run

```bash
/usr/bin/python3 -m pipeline.cli --help
/usr/bin/python3 -m unittest discover -s tests -t .
bash scripts/install-launchd.sh        # the local engine as a launchd service
```

Start reading at `CLAUDE.md`, then `docs/resolve-findings.md` for the Resolve
ground rules, then `brand/brand-brief.md` and `brand/visual-identity.md` for
the look.

## The look

Cyanotype: navy ground, chalk type, one yellow moment per frame, cyan for
anything structural, and the Archway mark. The source of truth is the design
system project on claude.ai/design; `brand/design-system/` is a synced copy.

## History

- v1 (a stock-footage pipeline with a Supabase dashboard and a worker daemon)
  was retired on 2026-08-18; its proven rendering techniques live on in
  `docs/reference-renderers/`.
- The channel was Curated Curiosities until 2026-08-20. The rebrand changed the
  name, the identity, and the format.
- The repo lives at `~/Projects/the-ninth-room`. A symlink at the old
  `~/Projects/curated-curiosities` path is intentional: Resolve stores absolute
  media paths and the shipped first episode's timeline still uses them.

## Licence

Code is MIT (`LICENSE`). The brand is all rights reserved (`LICENSE-BRAND.md`).
Fonts are under the SIL Open Font License (`brand/fonts/OFL.txt`).

Credits: cecropia moth cocoon photograph by Ryan Hodnett, CC BY-SA 4.0
(creativecommons.org/licenses/by-sa/4.0), cropped. Sound effects and music are
not included in this repository.
