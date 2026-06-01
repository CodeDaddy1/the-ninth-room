# Curated Curiosities Pipeline (CCP)

The auto-assembly program. Takes a topic, an approved script, and a shot list
and produces a **rough cut** video — voiceover, normalized clips, watermark
overlay — ready for you to polish in your NLE.

Built to remove the boring parts (searching, normalizing, syncing, watermarking)
and leave you with the parts that need taste (editing rhythm, music, final mix).

## Pipeline

```
   script.md  +  shot_list.json
        │            │
        │            ▼
        │     fetch_assets.py ──► assets/ (candidate clips per shot)
        │                                  │
        ▼                                  │
   voiceover.py ──► voiceover.mp3          │
                                           │
                       ┌───────────────────┘
                       ▼
                  assemble.py ──► rough_cut.mp4  (your starting point)
```

Each stage runs independently and writes its output to the video's work dir, so
you can re-run any one stage without redoing the others.

## Install

```bash
# Required
brew install ffmpeg            # or: apt install ffmpeg

# Python deps
pip install requests

# API keys (set what you'll use)
export PEXELS_API_KEY=...
export PIXABAY_API_KEY=...       # optional
export ELEVENLABS_API_KEY=...    # for TTS (recommended)
export ELEVENLABS_VOICE_ID=...   # the voice you want
export OPENAI_API_KEY=...        # fallback TTS provider
```

## Per-video work dir

Everything for one video lives in one folder:

```
program/work/<slug>/
├── script.md            # in: your finished narration script
├── voiceover.txt        # in: the narration text alone (or auto-derived)
├── shot_list.json       # in: the asset-scout's machine-readable plan
├── selections.json      # in (optional): which candidate to use per shot
├── watermark.png        # in (optional): your brand watermark overlay
├── assets/              # out: candidate clips per shot
├── voiceover.mp3        # out: generated narration
└── rough_cut.mp4        # out: the rough cut
```

## Usage

```bash
# 1. Scaffold a new video
python program/cli.py init aglet-short

# 2. Drop your script.md + shot_list.json into program/work/aglet-short/
#    (produced by the youtube-scriptwriter / asset-scout agents)

# 3. Fetch stock candidates
python program/cli.py fetch aglet-short

# 4. Generate the voiceover
python program/cli.py voiceover aglet-short

# 5. Pick favorites (optional — defaults to candidate 1 per shot)
#    Edit program/work/aglet-short/selections.json

# 6. Assemble the rough cut
python program/cli.py assemble aglet-short

# Or chain everything after script + shot_list are in place:
python program/cli.py run aglet-short
```

## What ships here vs. what's next

**Now**
- `cli.py` — one entry point with stage subcommands
- `config.py` — env + defaults
- `voiceover.py` — TTS via ElevenLabs (primary) / OpenAI (fallback) / manual
- `assemble.py` — FFmpeg-based normalize → concat → mux VO → watermark

**Next pass**
- `script_gen.py` — call the Anthropic API with the youtube-scriptwriter and
  asset-scout system prompts so script.md + shot_list.json are produced
  end-to-end from a topic
- `aigen.py` — generate clips for non-stock shots via Veo / Kling / Runway
  (likely through fal.ai)
- `captions.py` — burn-in captions via Whisper transcription of the voiceover
- Background music: ducked under VO

## Design notes

- Stages are independent and idempotent — re-run any one without redoing others.
- Non-stock shots get a brand-navy placeholder slate in the rough cut so
  duration/pacing is right; you swap in the AI-gen later.
- The watermark overlay is optional — drop a PNG into the work dir and it gets
  burned bottom-right with the standard margin.
- FFmpeg work happens in discrete commands (not one mega-filtergraph) so
  failures are debuggable.
