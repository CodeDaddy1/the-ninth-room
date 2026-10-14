# -*- coding: utf-8 -*-
"""Runs INSIDE Blender (`Blender --background scene.blend --python this.py`).

Renders a frame range to RGBA PNGs named the way the pipeline's card baker
names them (f0000.png upward, whatever the scene's own frame numbers are)
so `pipeline.animate.encode_frames` can turn them into ProRes 4444 alpha
without knowing which tool drew them.

The .blend owns the look — engine, samples, lights, camera, resolution,
view transform. This script forces only the contract: PNG, RGBA, film
transparent, the pipeline's fps, the pipeline's naming. Everything else it
leaves alone on purpose, because a template designed in the Blender UI must
render the same headless.

Args after `--`: <frames_dir> <fps> [<start> <end>]. Frame numbers are the
scene's; when omitted the scene's own range is used.

What breaks if this is wrong: frames come out with a black background (film
not transparent), the clip encodes but Resolve shows a hard black plate
behind the graphic; or frame names start at the scene's first frame number
and the encoder silently drops the leading ones.
"""
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) not in (2, 4):
    print("blender_frames: expected <frames_dir> <fps> [<start> <end>]",
          file=sys.stderr)
    sys.exit(2)

frames_dir, fps = argv[0], int(argv[1])
scene = bpy.context.scene
start = int(argv[2]) if len(argv) == 4 else scene.frame_start
end = int(argv[3]) if len(argv) == 4 else scene.frame_end
if end < start:
    print("blender_frames: end %d before start %d" % (end, start),
          file=sys.stderr)
    sys.exit(2)

scene.render.fps = fps
scene.render.fps_base = 1.0
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.image_settings.color_depth = "8"
scene.render.use_file_extension = True

for i, frame in enumerate(range(start, end + 1)):
    scene.frame_set(frame)
    scene.render.filepath = "%s/f%04d" % (frames_dir, i)
    bpy.ops.render.render(write_still=True)

print("blender_frames: wrote %d frames" % (end - start + 1))
