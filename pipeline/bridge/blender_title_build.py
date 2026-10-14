# -*- coding: utf-8 -*-
"""Runs INSIDE Blender: builds the 3D title card scene from a spec and saves it.

`Blender --background --factory-startup --python this.py -- spec.json`

The spec (written by `pipeline/blender_title.py`) carries the flat kit's
numbers: linear colours, the font file, sizes in CSS px, the easing curves,
the shadow list. This script only turns them into objects. Layout maths is
the kit's (left edge, eyebrow above title, 16px block gap) at 100 px per
Blender unit under an orthographic camera, so a px in the spec is a px in
the frame.

Depth is the one addition: the title is extruded and bevelled, converted
to a mesh so its FRONT faces take an emission material (exact chalk, no
shading to shift it) while its side and bevel faces take a lit navy-800
material that a cyan rim light catches. The eyebrow stays flat, as in the
kit. The shadow is the kit's double text-shadow, rebuilt in the compositor
from the render's own alpha so it follows the letters through the motion.

Blender 5.2 API notes that cost a probe each: `action.fcurves` is gone
(layered actions: layers[0].strips[0].channelbag(slot)), the compositor
output is a group output socket, Blur takes a vector Size in px.
"""
import json
import math
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) != 1:
    print("blender_title_build: expected <spec.json>", file=sys.stderr)
    sys.exit(2)
with open(argv[0]) as fh:
    SPEC = json.load(fh)

U = float(SPEC["px_per_unit"])
W, H = SPEC["w"], SPEC["h"]                       # device px, the render size
DW = SPEC.get("design_w", W)                      # CSS px, the layout's frame
DH = SPEC.get("design_h", H)
FPS = SPEC["fps"]
COL = SPEC["colors"]
T, E, M = SPEC["title"], SPEC["eyebrow"], SPEC["motion"]


def px(v):
    return float(v) / U


def frame_at(ms):
    return 1.0 + (float(ms) / 1000.0) * FPS


# ---- scene ------------------------------------------------------------
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.resolution_percentage = 100
sc.render.fps, sc.render.fps_base = FPS, 1.0
sc.frame_start, sc.frame_end = 1, SPEC["frames"]
sc.render.film_transparent = True
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"
if sc.view_settings.view_transform != "Standard":
    print("blender_title_build: view transform refused", file=sys.stderr)
    sys.exit(3)

cam_data = bpy.data.cameras.new("TitleCam")
cam_data.type = "ORTHO"
# ortho_scale spans the frame's LONGER side by default; on a portrait
# canvas that showed a 1.78x zoom of the middle with the eyebrow off the
# left edge (2026-09-16). Pin it to the width, in CSS px, so one unit is
# 100 CSS px whatever the device size.
cam_data.sensor_fit = "HORIZONTAL"
cam_data.ortho_scale = DW / U
cam = bpy.data.objects.new("TitleCam", cam_data)
sc.collection.objects.link(cam)
cam.location = (0.0, 0.0, 10.0)
sc.camera = cam


def area_light(name, rgb, energy, loc, size):
    d = bpy.data.lights.new(name, "AREA")
    d.color = rgb
    d.energy = energy
    d.size = size
    ob = bpy.data.objects.new(name, d)
    sc.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return ob


area_light("Key", (1.0, 1.0, 1.0), 900.0, (-6.0, 5.0, 9.0), 6.0)
area_light("Rim", tuple(COL["cyan"]), 1400.0, (9.0, -3.0, 4.0), 4.0)

FONT = bpy.data.fonts.load(SPEC["font"])


# ---- materials --------------------------------------------------------
def mat_flat(name, rgb):
    """Emission mixed with transparent: exact colour, alpha on the mix."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    emit = nt.nodes.new("ShaderNodeEmission")
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    emit.inputs["Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    emit.inputs["Strength"].default_value = 1.0
    nt.links.new(clear.outputs[0], mix.inputs[1])
    nt.links.new(emit.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    mix.inputs["Fac"].default_value = 1.0
    m.surface_render_method = "DITHERED"
    return m, mix.inputs["Fac"]


def mat_side(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    bsdf.inputs["Roughness"].default_value = 0.35
    bsdf.inputs["Alpha"].default_value = 1.0
    m.surface_render_method = "DITHERED"
    return m, bsdf.inputs["Alpha"]


# ---- keyframes with the kit's curve -----------------------------------
def _channelbag(idblock):
    act = idblock.animation_data.action
    return act.layers[0].strips[0].channelbag(act.slots[0])


def ease_keys(idblock, holder, attr, index, ms0, v0, ms1, v1, bez):
    """Two keys, Bezier, handles set to the CSS cubic-bezier control points."""
    f0, f1 = frame_at(ms0), frame_at(ms1)
    if index is None:
        setattr(holder, attr, v0)
        holder.keyframe_insert(attr, frame=f0)
        setattr(holder, attr, v1)
        holder.keyframe_insert(attr, frame=f1)
        path = holder.path_from_id(attr) if holder is not idblock else attr
        fc = _channelbag(idblock).fcurves.find(path)
    else:
        vec = getattr(holder, attr)
        vec[index] = v0
        holder.keyframe_insert(attr, index=index, frame=f0)
        vec = getattr(holder, attr)
        vec[index] = v1
        holder.keyframe_insert(attr, index=index, frame=f1)
        fc = _channelbag(idblock).fcurves.find(attr, index=index)
    if fc is None:
        print("blender_title_build: fcurve missing for %s" % attr, file=sys.stderr)
        sys.exit(4)
    k0, k1 = fc.keyframe_points[0], fc.keyframe_points[1]
    dt, dv = f1 - f0, v1 - v0
    k0.interpolation = "BEZIER"
    k0.handle_right_type = "FREE"
    k1.handle_left_type = "FREE"
    k0.handle_right = (f0 + bez[0] * dt, v0 + bez[1] * dv)
    k1.handle_left = (f0 + bez[2] * dt, v0 + bez[3] * dv)


# ---- text objects -----------------------------------------------------
def make_text(name, body, size_px, spacing, box_w_px=None, extrude_px=0.0,
              bevel_px=0.0, align_y="TOP"):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.font = FONT
    cu.size = px(size_px) * SPEC["text_scale"]   # see BLENDER_TEXT_SCALE
    cu.space_character = spacing
    cu.space_line = 1.0
    cu.align_x = "LEFT"
    cu.align_y = align_y
    if extrude_px:
        cu.extrude = px(extrude_px) / 2.0     # Blender extrudes both ways
    if bevel_px:
        cu.bevel_depth = px(bevel_px)
        cu.bevel_resolution = 2
    if box_w_px:
        cu.text_boxes[0].width = px(box_w_px)
    ob = bpy.data.objects.new(name, cu)
    sc.collection.objects.link(ob)
    return ob


def to_mesh_with_faces(ob, front_mat, side_mat):
    with bpy.context.temp_override(active_object=ob, selected_objects=[ob],
                                   selected_editable_objects=[ob]):
        bpy.ops.object.convert(target="MESH")
    me = ob.data
    me.materials.append(front_mat)
    me.materials.append(side_mat)
    for poly in me.polygons:
        poly.material_index = 0 if abs(poly.normal.z) > 0.9 else 1
    return ob


left_x = -DW / (2.0 * U) + px(T["left_px"])

title = make_text("Title", T["text"], T["size_px"], T["spacing"],
                  box_w_px=T["inner_px"], extrude_px=T["extrude_px"],
                  bevel_px=T["bevel_px"])


def fit_lines(ob, max_lines):
    """The kit's `_fit`, measured in Blender rather than with Pillow: the
    text box wraps at the inner width, and the size comes down until the
    block holds `max_lines` lines. A one-line block measures about 0.55
    em tall (cap plus descender) and each further line adds one em, so
    lines = round(height / size - 0.55) + 1 (measured 2026-09-15)."""
    for _ in range(14):
        bpy.context.view_layer.update()
        size = ob.data.size
        lines = int(round(ob.dimensions.y / size - 0.55)) + 1
        if lines <= max_lines:
            return lines
        ob.data.size = size * 0.94
    return lines


fit_lines(title, T.get("max_lines", 2))
title_front, title_alpha = mat_flat("TitleFront", COL["chalk"])
title_side, title_side_alpha = mat_side("TitleSide", COL["side"])
to_mesh_with_faces(title, title_front, title_side)
title_h = title.dimensions.y

eyebrow_h = px(E["size_px"])
block_h = eyebrow_h + px(E["block_gap_px"]) + title_h
block_top = block_h / 2.0
eyebrow_mid = block_top - eyebrow_h / 2.0
title_top = block_top - eyebrow_h - px(E["block_gap_px"])

title.location = (left_x, title_top, 0.0)

label = make_text("Eyebrow", E["text"], E["size_px"], E["spacing"], align_y="CENTER")
label_mat, label_alpha = mat_flat("EyebrowInk", COL["cyan"])
label.data.materials.append(label_mat)
label.location = (left_x + px(E["rule_px"] + E["gap_px"]), eyebrow_mid, 0.0)

# the rule: a plane whose origin is its left edge so scale_x grows rightward
rule_me = bpy.data.meshes.new("RuleMesh")
rw, rh = px(E["rule_px"]), px(E["rule_thick_px"])
rule_me.from_pydata([(0, -rh / 2, 0), (rw, -rh / 2, 0), (rw, rh / 2, 0), (0, rh / 2, 0)],
                    [], [(0, 1, 2, 3)])
rule_me.update()
rule = bpy.data.objects.new("Rule", rule_me)
sc.collection.objects.link(rule)
rule_mat, _rule_alpha = mat_flat("RuleInk", COL["cyan"])
rule_me.materials.append(rule_mat)
rule.location = (left_x, eyebrow_mid, 0.0)

# ---- motion: the kit's yFade / yGrow / yUp, plus the tilt only 3D can do --
e0, e1 = M["eyebrow_ms"]
ease_keys(label_mat.node_tree, label_alpha, "default_value", None, e0, 0.0, e1, 1.0, M["ease_reveal"])
r0, r1 = M["rule_ms"]
ease_keys(rule, rule, "scale", 0, r0, 0.0, r1, 1.0, M["ease_rule"])
t0, t1 = M["title_ms"]
ease_keys(title, title, "location", 1, t0, title_top - px(M["rise_px"]), t1, title_top, M["ease_reveal"])
ease_keys(title, title, "rotation_euler", 0, t0, -math.radians(M["tilt_deg"]), t1, 0.0, M["ease_reveal"])
ease_keys(title_front.node_tree, title_alpha, "default_value", None, t0, 0.0, t1, 1.0, M["ease_reveal"])
ease_keys(title_side.node_tree, title_side_alpha, "default_value", None, t0, 0.0, t1, 1.0, M["ease_reveal"])

# ---- shadow: the kit's text-shadow, from the render's own alpha ---------
if SPEC.get("shadows"):
    ng = bpy.data.node_groups.new("TitleComp", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers")
    sep = ng.nodes.new("CompositorNodeSeparateColor")
    ng.links.new(rl.outputs["Image"], sep.inputs["Image"])
    under = None
    # farthest shadow first so nearer ones composite over it
    for i, sh in enumerate(sorted(SPEC["shadows"], key=lambda s: -s["blur"])):
        blur = ng.nodes.new("CompositorNodeBlur")
        blur.inputs["Size"].default_value = (sh["blur"], sh["blur"])
        ng.links.new(sep.outputs["Alpha"], blur.inputs["Image"])
        move = ng.nodes.new("CompositorNodeTranslate")
        move.inputs["X"].default_value = sh["dx"]
        move.inputs["Y"].default_value = sh["dy"]
        ng.links.new(blur.outputs["Image"], move.inputs["Image"])
        scale = ng.nodes.new("ShaderNodeMath")
        scale.operation = "MULTIPLY"
        scale.inputs[1].default_value = sh["alpha"]
        ng.links.new(move.outputs["Image"], scale.inputs[0])
        ink = ng.nodes.new("CompositorNodeRGB")
        ink.outputs[0].default_value = (sh["rgb"][0], sh["rgb"][1], sh["rgb"][2], 1.0)
        seta = ng.nodes.new("CompositorNodeSetAlpha")
        seta.inputs["Type"].default_value = "Replace Alpha"
        ng.links.new(ink.outputs[0], seta.inputs["Image"])
        ng.links.new(scale.outputs[0], seta.inputs["Alpha"])
        if under is None:
            under = seta.outputs["Image"]
        else:
            over = ng.nodes.new("CompositorNodeAlphaOver")
            over.inputs["Straight Alpha"].default_value = True
            ng.links.new(under, over.inputs["Background"])
            ng.links.new(seta.outputs["Image"], over.inputs["Foreground"])
            under = over.outputs["Image"]
    final = ng.nodes.new("CompositorNodeAlphaOver")
    ng.links.new(under, final.inputs["Background"])
    ng.links.new(rl.outputs["Image"], final.inputs["Foreground"])
    out = ng.nodes.new("NodeGroupOutput")
    ng.links.new(final.outputs["Image"], out.inputs[0])
    sc.compositing_node_group = ng
    sc.render.use_compositing = True

bpy.ops.wm.save_as_mainfile(filepath=SPEC["blend"])
print("blender_title_build: saved %s (title %.2f units tall)" % (SPEC["blend"], title_h))
