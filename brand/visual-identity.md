# Visual Identity — The Ninth Room (Cyanotype)

**Source of truth:** the *The Ninth Room Design System* project on
claude.ai/design (project `4b8bb4a4-b234-45ed-aa84-b35ce761648b`). Its
`uploads/The Ninth Room - Cyanotype Kit.dc.html` is ground truth for
everything on video; `uploads/The Ninth Room - Archway Logo.dc.html` is
ground truth for the mark. Where two files disagree, those two win.

Tokens are synced into `brand/design-system/tokens/*.css` and read at render
time by `pipeline/design_tokens.py`. **Never hardcode a brand value in the
pipeline** — change it in the design system, re-pull, re-bake.

---

## The one rule

> **No filled plates, and one yellow moment per frame.**

If two things are yellow, neither is the thing to look at. When bright footage
threatens legibility the answer is always a gradient scrim, never a box — the
box is what makes a kit look like a template.

Both halves are enforced in code (`pipeline/overlay_kit.py`): no text
container in the kit carries a background, and `emphasize()` marks only the
first emphasis term it finds.

## Colour

| | Hex | Role |
|---|---|---|
| ■ | `#0B2340` | navy — base. Scrims, washes, type on either accent |
| □ | `#EAF4FF` | chalk — all type on video |
| ■ | `#FFE04D` | yellow — the one thing to look at |
| ■ | `#38E1F0` | cyan — verified. Speaker rules, eyebrows, crop marks |
| ■ | `#E2A100` | the light, darkened so it holds on white. Paper only |
| ■ | `#7C9BBC` | slate — secondary and losing values. **Never an accent** |
| ■ | `#173456` | footage tint |

Cyan is *structural*: it means "this is real, this is a label, this is the
system talking". Yellow is *attention*: it means "look here". They are not
interchangeable and a card never uses both as accents.

## Type

| Face | Used for |
|---|---|
| **Bricolage Grotesque 800** | everything on video, tracking −.04em (−.055em at chapter and stat size) |
| **Newsreader** | the wordmark, quotes, takeaways and specimen names — 600 upright, 400 italic. Nothing else |
| **Manrope** | documents and UI chrome. **Never on video** |

On-video ramp at 1920 wide: stat 230 · chapter 150 · hook 104 · keyword 86 ·
headline 80 · quote 78 · lower third 70 · caption 64 · option 46 · eyebrow
26–28 at .22–.24em.

All three faces are installed in `~/Library/Fonts` and vendored for Pillow in
`brand/fonts/`. The renderer runs offline; it resolves them by family name.

## Protection, instead of plates

Type on footage carries a double text-shadow —
`0 0 4px rgba(4,16,32,.95), 0 4px 18px rgba(4,16,32,.9)` — which is precisely
what removes the need for a plate. Burned captions use the *strong* variant,
because a burned caption cannot know what is behind it.

Where footage must be suppressed further, use one of three scrims (lower,
side, tall) or a flat navy wash at 86% (chapter) / 72% (teaser).

**The system's protection method is shadow and scrim, never capsule.**

## The mark — the Archway

An arch seen straight on, warm light in the passage, the wall's thickness
thrown as shadow, one figure at the threshold. It is about a person walking
into somewhere; everything else exists to protect that.

| Element | Rule |
|---|---|
| Grid | 8u wide × 10u tall |
| Arch radius | exactly 4u — a true semicircle, never a squashed oval |
| Outline | 0.14u, never rendering under 2px |
| Shadow | the same arch, offset 2.6u right / 1.1u down |
| Figure | body 0.7u × 2u at 1.3u from the left, head 0.5u |
| Clear space | 2u every side, from the outer stroke |

The figure **drops below 48px tall** — the small variants are arch, light,
shadow only. Vector masters and every export live in
`brand/design-system/channel-assets/`.

## Shadows, borders, radii

- No box shadows, no glows, no drop shadow on the mark. The shadow inside the
  arch is the only shadow the brand owns.
- Outlines are 3px minimum on video so they survive compression; 4px on the
  mark and callout frames; 6px for poll rules.
- Corners are nearly square — 4/6px chips, 8/10px frames, 11px document cards.
  **The arch is the only real curve in the system**, and its radius is always
  exactly half its width.
- No blur anywhere. Gradients and flat alpha only.

## Cards

There are **no filled cards on video.** An option is an outline; the answer is
that outline flooding with yellow, and its type turns navy as the fill lands.

## Layout

Insets are fixed and never nudged.

| | Landscape 1920×1080 | Vertical 1080×1920 |
|---|---|---|
| Caption from bottom | 150 | 320 |
| Sides | 120 | 64 |
| Top | — | 180 |
| Watermark | 72 right / 64 top, and it never moves | 48 / 120 |

## Motion

Two curves only: `cubic-bezier(.16,1,.3,1)` for anything arriving,
`cubic-bezier(.22,.61,.36,1)` for rules, bars and wipes. Reveals 220–420ms,
figure walk 520ms, mark build 1.4s. Staggers: 100ms for caption words and card
options, 80ms for rooms.

Everything is one-shot and seekable — which is what lets
`pipeline/animate.py` bake it frame by frame. Motion is directional and
physical: things slide in, light floods up a passage, rules wipe across.
**Nothing bounces, spins, or eases in place.**

## Iconography

The brand has no icon set and does not want one. Four drawn primitives do all
the work, all made of borders and rectangles:

1. **The rule** — a 3px cyan or yellow bar growing from one end. Heads every
   eyebrow, underlines every speaker tag, and is the house transition.
2. **The crop mark** — an L of two 3px strokes. Callout frames, the end plate,
   the room badge, the iris cut.
3. **The grid** — six cyan columns, for the sweep cut.
4. **The dimension bracket** — a rule with two end caps, for the push cut and
   the measurement ticks under a stat.

If a genuine icon is ever needed, draw it from these at 3px in cyan or chalk.
**No icon library** — the primitives above are the system's own drawing
vocabulary, and an imported icon set would sit outside it.

**Emoji are a separate thing and they are encouraged.** They are not icons
standing in for the system; they are the family's voice, closer to a
reaction than to a symbol. Treated as pictures rather than type: they carry a
`drop-shadow` matching the chalk text-shadow so they anchor on footage, and
they do **not** consume the frame's yellow moment — a yellow word still wins
the eye. `pipeline/overlay_kit.py` applies this automatically to every string,
and the `emoji` kit screen exists for moments where emoji *are* the content.

## What this supersedes

- The Curated Curiosities navy/amber/cream system with Playfair Display and
  Work Sans — retired. Its token files are kept at
  `brand/design-system/_retired-curated-curiosities/` for reference only.
- The **Midnight / "Cutout" chip kit** (design handoff 2026-08-19) — retired
  by the Cyanotype kit, which says so itself. Chips, 5px ice outlines, hard
  offset shadows and ±1–2° tilts are all gone. The previous runtime is kept
  at `pipeline/.overlay_kit_midnight_v3.py.bak`.

Anything still describing amber, cream, chips or tilts is out of date.
