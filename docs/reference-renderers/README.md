# Reference renderers — v1 ARCHIVE

**These scripts do not run in the pipeline and must not be imported by it.**
They are the surviving v1 (stock-footage) renderers, kept for one reason: the
whisper / Pillow / ffmpeg *techniques* in them were proven on real renders and
are expensive to rediscover.

| File | Kept for |
|---|---|
| `_build.py` | Card composition in Pillow, ffmpeg concat and overlay expressions |
| `_build_synced.py` | The same, driven by word-level whisper timings |
| `_transcribe.py` | Whisper invocation and word-timing extraction |

## What is historical and must NOT be copied

These files predate two rebrands. Everything about how they *look* is wrong now:

- The strings `Curated Curiosities` and `@CuratedCuriosities` — the channel is
  **The Ninth Room**.
- `CREAM`, `AMBER`, navy/amber/cream generally, Playfair Display and Work Sans
  — all retired. The palette is Cyanotype (navy `#0B2340`, chalk `#EAF4FF`,
  yellow `#FFE04D`, cyan `#38E1F0`) and the faces are Bricolage Grotesque,
  Newsreader and Manrope.
- Filled rounded cards behind type. The current rule is **no filled plates,
  one yellow moment per frame**.

Copy the *mechanism*, never the styling. If you find yourself pasting a hex
value out of this folder, stop.

## Where the current renderers live

| Concern | Module |
|---|---|
| Card spec → PNG → alpha .mov | `pipeline/graphics.py` |
| CSS animation baked frame by frame in headless Chrome | `pipeline/animate.py` |
| The overlay kit itself (every on-screen screen) | `pipeline/overlay_kit.py` |
| Burned captions (Pillow, word timing, emoji in-line) | `pipeline/captions.py` |
| Brand tokens, read from the synced design system | `pipeline/design_tokens.py` |

Brand rules: `brand/visual-identity.md`. Kit source of truth: the Cyanotype
canvas at `brand/design-system/canvases/`.
