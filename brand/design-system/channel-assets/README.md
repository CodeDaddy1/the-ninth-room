# The Ninth Room — production assets

Vector masters plus PNG and JPG exports, generated from the brand kit. This closes
the open item in the kit: *"the production mark needs redrawing as SVG on the 8×10u
grid, with the figure as a single compound path."*

**153 files** — 37 SVG · 85 PNG · 30 JPG

---

## The mark, as redrawn

The Archway is now true vector on the documented grid. `viewBox="0 0 800 1000"`, so
**u = 100** and the artboard is exactly 8u × 10u.

| Element | Rule | In the file |
|---|---|---|
| Arch radius | 4u — a true semicircle, never a squashed oval | `r = 400` |
| Outline | 0.14u, sitting inside the 8×10u box | `stroke-width="14"` |
| Shadow | Same arch silhouette, offset 2.6u right / 1.1u down | `translate(260,110)` |
| Figure | Body 0.7u × 2u at 1.3u from the left, head 0.5u | one compound path |
| Clear space | 2u every side, from the outer stroke | not baked in — layout's job |

The figure is **a single compound path** (body + head as two subpaths in one `d`), so
the small variants drop it by deleting one node. No other geometry moves.

## Two rules that apply themselves

Both size-ladder rules are baked into the exports, so you cannot ship a broken one:

- **The figure drops below 48px tall.** Every PNG at 32px and under is automatically
  the three-shape version — arch, light, shadow.
- **The outline never renders under 2px.** Below that the cyan breaks up. Large sizes
  keep the 0.14u ratio; small sizes hold the floor.

> One judgement call worth flagging: the source files disagree on outline weight —
> the Construction panel draws it at 1.67% of width, the cover at 2.7%, the small
> knockouts at 4.7%. I took the Construction panel as canonical since it is the
> labelled spec, and added the 2px floor to cover what the heavier small strokes were
> really compensating for. If you would rather the mark read heavier at cover scale,
> it is one number in the generator.

---

## Which file to reach for

### `svg/logo/` — the mark alone, transparent, 8u × 10u

| File | Ground | Notes |
|---|---|---|
| `archway-primary` | navy, dark footage | cyan outline, yellow light, navy shadow |
| `archway-print` | white, paper | light darkens to `#E2A100` so it holds |
| `archway-mono-navy` | cyan or yellow | outline and shadow navy, light drops out — the arch is the shadow |
| `archway-mono-chalk` | photography | single-colour chalk |
| `archway-watermark` | any footage | shadow is **cut out**, not filled — footage shows through |
| `archway-watermark-bright` | bright footage | as above, navy outline |

Each also ships a `-small` version with the figure already removed. Plus
`archway-primary-on-navy` and `archway-print-on-paper` with 2u clear space built in.

### `svg/lockup/` — mark + wordmark
Horizontal and stacked, each on navy, on white, and on transparent. The mark-to-wordmark
gap is 3u, per spec. Wordmark is Newsreader 600, tagline Bricolage Grotesque 800 at .26em.

### `svg/channel/` — the nine YouTube slots, at exact size

`cover-2560x1440` · `profile-800x800` · `watermark-150x150` (+ bright) ·
`thumbnail-1280x720` · `short-1080x1920` · `ad-300x250` · `ad-300x60` · `ad-480x70` ·
`endcard-1920x1080`

Several ship a `-guides` twin with the title-safe box, avatar circle or platform-unsafe
zones drawn on. **Those are for checking — never upload one.** The clean file has no guides.

- **Cover** — everything readable sits inside the 1546 × 423 title-safe box. The
  colonnade of nine bleeds off the right and is dimmed to 42%, so the lit arch in it
  never competes with the yellow moment in the lockup.
- **Thumbnail** — ships as a worked example *and* as `-template`, which is the tint
  ramp, safe box and corner watermark with the copy stripped, ready to drop on footage.
- **Short** — caption clears the 320px bottom UI zone, stamp clears the 180px top zone.

---

## Formats

| | Use for | Alpha |
|---|---|---|
| **SVG** | the masters — everything else is generated from these | yes |
| **PNG** | upload to YouTube, anywhere needing transparency | yes |
| **JPG** | q92, 4:4:4, progressive — where a file must be flat | no |

**The watermark is PNG only.** It has to be transparent; there is no JPG twin, by design.

All text in every SVG is **converted to outlines**, so the files render identically
without Newsreader, Bricolage Grotesque or Manrope installed. Nothing links out.

Cover and thumbnail are both far under YouTube's 2MB ceiling — 0.16MB and 0.06MB as JPG.

---

## Palette

| | Hex | Role |
|---|---|---|
| ■ | `#0B2340` | base |
| □ | `#EAF4FF` | type |
| ■ | `#FFE04D` | look here — one moment per frame |
| ■ | `#38E1F0` | verified |
| ■ | `#E2A100` | light, on paper only |
| ■ | `#8FB3D6` | support copy |
| ■ | `#173456` | footage tint |

The rule the whole kit hangs on: **no filled plates, one yellow moment per frame.**

---

## The end card

The last slot on your sheet, now drawn. It hands off from Beat 3 of the outro — the
arch is the last thing on screen, so the card holds it rather than starting something new.

`endcard-1920x1080` · `endcard-1280x720` · `-guides` · `-overlay` (transparent)

**The footprints are marked, not filled.** Two video slots and the subscribe circle are
drawn as corner brackets and a ring — the same bracket device Beat 3 puts around the arch.
Nothing behind an element is a filled plate, so the rule survives into the end card.

| Element | Footprint at 1920×1080 | Where |
|---|---|---|
| Video slot A — "next room" | 615 × 345 | right, y 170 |
| Video slot B — "or start here" | 615 × 345 | right, y 590 |
| Subscribe | 294 circle | left, centred y 775 |

**You cannot style the subscribe element.** YouTube always draws its own round channel
avatar there — so the artwork gives it a cyan ring to land inside and a label pointing at
it, rather than a button that would end up sitting behind YouTube's. Use `profile-800x800`
as the avatar and the two read as one object.

Everything sits inside a 10% safe margin, and the lowest element clears the bottom of the
frame by 13% — clear of the progress bar and controls. The arch stays the single yellow
moment; every label is cyan.

The `-overlay` file is the same furniture on transparency, to drop straight over footage
in an editor. Tested over dark, bright and mid-tone grounds.

---

## Still open

Nothing on the sheet. If you want the outro itself as motion — the three beats, 8.9s total
— that is an animation brief rather than a static asset, and the geometry is now in place
to key it off.
