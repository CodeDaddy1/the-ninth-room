# Blender in the pipeline

Stamped 2026-09-15. Blender 5.2 LTS at `/Applications/Blender.app`.

Blender is a second frame maker. Chrome turns CSS cards into PNG frames;
Blender turns a `.blend` into PNG frames; both go through
`pipeline.animate.encode_frames` and arrive in Resolve as ProRes 4444 alpha.
Nothing downstream knows which tool drew the pixels.

## Two ways in

**Design: MCP, with Blender open.** The `blender` MCP server is registered
at user scope (`claude mcp list`). Open Blender, press `N` in the 3D
viewport, "MCP for Blender" tab, "Start MCP Server". From then on Claude can
build and adjust the scene while you watch. Close Blender and nothing
listens. The addon can run arbitrary Python inside Blender on Claude's
behalf, so save before a session. Telemetry is disabled by the server's
environment regardless of the addon checkbox. Poly Haven, Sketchfab and
Hyper3D integrations stay off: the first is free but out of policy for a
brand look, the other two need keys or credits.

**Render: headless, from the pipeline.** Save the `.blend` into the repo
(see Templates) and render it with

    /usr/bin/python3 -m pipeline.cli blender-render scene.blend out.mov --fps 24
    /usr/bin/python3 -m pipeline.cli blender-render scene.blend out.mov --start 1 --end 48

or from code, `blender_render.render_blend(blend, out_mov, fps, start, end)`.
The `.blend` owns the look (engine, samples, lights, camera, resolution,
view transform). `pipeline/bridge/blender_frames.py` runs inside Blender
and forces only the contract: RGBA PNG, film transparent, our fps,
`f0000.png` naming from whatever frame the scene starts on. The Python side
refuses a missing app or file, a non-zero exit, a short render, or a gap in
the sequence, before anything is encoded.

Measured 2026-09-15: a 12-frame 1080p Eevee test renders and encodes in
9.4 s including Blender's startup; alpha verified 0 off-subject, 255 on it.

Both Blender commands carry `--python-exit-code 1`. Without it Blender
exits 0 when the bridge script throws, and the seam's exit-code guard is
blind; found the first time the title build failed silently.

## Rules for a template

- View transform **Standard**, not AgX or Filmic. The brand colours come
  from the design tokens and must land in the frame as the tokens say;
  a filmic curve shifts them.
- Resolution is the delivery frame (`1920x1080` or `1080x1920`), or a
  whole multiple of it, as cards do.
- Eevee unless a shot needs what only Cycles does. A template that takes
  minutes a frame is a template that gets skipped on episode day.
- No brand literal in a `.blend` that the tokens already own. Colours
  are set from `pipeline/design_tokens.py` by the script that populates
  the template, not typed into a material.
- One `.blend` per template under `brand/blender/`, versioned like the
  overlay kit. The `.blend` is the cache key; a changed file re-renders.

## Template 1, first cut: `blender-title` (test clip rendered 2026-09-15)

    /usr/bin/python3 -m pipeline.cli blender-title "The Ninth Room" out.mov --kicker "Episode one"

`pipeline/blender_title.py` turns the kit's constants (`overlay_kit`:
chalk, cyan, navy-800, Bricolage, `ease-reveal`, `ease-rule`, the double
shadow, STROKE, the 140px left edge and 1560px inner width) into a spec;
`pipeline/bridge/blender_title_build.py` builds the scene from it under
`--factory-startup`; `render_blend` encodes it. The `.blend` is kept beside
the clip so an MCP session can open and argue with it.

What the 3D adds: 6px extrusion with a 1.5px bevel, front faces on an
emission material (exact chalk, no shading shift), side and bevel faces on
lit navy-800 with a cyan rim light, and a 12 degree tilt that settles flat
during the kit's own 400ms `yUp`. The shadow is the kit's text-shadow
rebuilt in the compositor from the render's alpha.

Measured on the first clip (72 frames, 1080p, Eevee): 28.6 s build plus
render; chalk lands at (233,244,255) against the token's (234,244,255),
one step of ProRes rounding; alpha 0 off the type.

Known residuals, for the real build:
- `BLENDER_TEXT_SCALE = 1.40` calibrates Blender's text size to CSS px by
  cap height. Blender draws Bricolage ~6% wider for its height than
  FreeType/Chrome, and its `space_character` multiplies advances where CSS
  tracking subtracts an em fraction, so a line runs ~25% wider than the
  flat card. Line fitting (`_fit`) must be re-done by measuring in Blender.
- The bevel adds ~3px to the silhouette; the cap reads 92px where CSS
  reads 86px.
- Blender 5.2 API: `action.fcurves` is gone (use
  `layers[0].strips[0].channelbag(slot)`), the compositor output is a
  group output socket, `SetAlpha` mode is a menu socket, Blur takes a
  vector Size in px. Each cost one probe; the bridge notes them.

## Template 1 as kit types (2026-09-16, plan P6)

`chapter_3d` and `hook_3d` are `kit_type`s in `overlay_kit.RENDERERS`
(`pipeline/blender_kit.py`), aliased to the flat `chapter` and `hook`
screens as their stand-ins, so the validator, the picker ("3D titles"), the
hover preview and the Studio all work; `graphics.render_card` routes them to
`blender_title.build_title` and everything downstream is unchanged. The
cache key folds `blender_kit.template_sha` (the two bridge scripts, the
text scale, any `.blend` here) for Blender kits only, so a template edit
re-bakes exactly the 3D cards. Both Blender calls carry a 600 s timeout.

Measured 2026-09-16 on a 2160x3840 canvas, 72 frames: a `chapter_3d` card
bakes in 86 s against 8.6 s for its flat twin (the fifteen second target is
not met; Eevee at 4K, samples untouched); the cache answers a second bake
at once. Against the flat card: left edge identical, two lines each, the
block 28 px lower, the 3D line 8 percent wider (Blender's `space_character`
multiplies advances where CSS tracking subtracts an em fraction), the line
gap larger. Two findings fixed the same day: Blender's `ortho_scale` spans
the frame's LONGER side (a portrait canvas showed a 1.78x zoom of the
middle; the camera is pinned `sensor_fit HORIZONTAL`), and the layout is
in the kit's CSS px at a device pixel ratio, not in device px. Line fit
is measured in Blender (`fit_lines` in the bridge). Not built: the door
meter on `chapter_3d`, the yellow second line on `hook_3d`.

## Templates (each is its own build; 1 has a first cut, the rest not started)

| # | Template | Feeds | DoD |
|---|---|---|---|
| 1 | 3D title and chapter cards in Cyanotype | the card slot in `graphics.build_cards` | one title, one chapter, one lower third; matches the flat kit side by side (line fit, tracking); under 15 s a card; wired into `build_cards` behind a `kit_type` |
| 2 | Turntable of a Higgsfield GLB | b-roll for objects from the place visited | GLB import, brand lighting rig, 4 s orbit, mid-shot framing that hides AI mesh roughness |
| 3 | Location establishing flyover | the episode open | Blender GIS terrain for a lat/long, one camera path reused per episode, Cyanotype grade |
| 4 | 2.5D parallax over a still | rescue for static b-roll | photo plus depth or hand-cut layers, push-in and drift presets, compared against Higgsfield image-to-video on cost |

Template 1 first: it is the biggest visible upgrade and it reuses the most
of what exists (tokens, card ids, the same slot in the timeline).

## Paid-path note

Blender is free and local, inside the `$0/mo` rule. Higgsfield is a paid
plan and is the README's third opt-in paid path since 2026-09-15, when the
first illustrations (hmns, monarch life cycle) entered
`work/hmns/assets/`.
