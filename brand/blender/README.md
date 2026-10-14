# Blender templates

One template per kit type that Blender renders instead of Chrome. Template
one (`chapter_3d`, `hook_3d`) builds its `.blend` per card from the kit's
numbers, so its template IS the two bridge scripts
(`pipeline/bridge/blender_frames.py`, `pipeline/bridge/blender_title_build.py`)
plus `blender_title.BLENDER_TEXT_SCALE`; a `.blend` saved here by a later
template joins the same cache key (`blender_kit.template_sha`). Rules for a
template: `docs/blender.md`. The flat kit screen is each 3D kit's canvas
(CLAUDE.md rule six): the render must match the stand-in, not the other
way round.
