"""Exports the web assets from blender/book.blend.

Run through `npm run asset:export` with book.blend open. Writes:
  public/models/book.glb       geometry, materials, lights
  src/stage/bookMeta.json      camera views and tab label quads
  public/posters/book-*.webp   still renders, one per camera view

Flags after `--`:
  --no-posters   skip the renders
  --preview      render small, fast previews into blender/preview instead
"""

import json
import math
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PREVIEW = "--preview" in ARGV
POSTERS = "--no-posters" not in ARGV

GLB_PATH = os.path.join(ROOT, "public", "models", "book.glb")
META_PATH = os.path.join(ROOT, "src", "stage", "bookMeta.json")
POSTER_DIR = os.path.join(HERE, "preview") if PREVIEW else os.path.join(ROOT, "public", "posters")
EXPORT_COLLECTIONS = ("Book", "Room", "Tabs", "Props", "Lights")
TAB_ORDER = ("about", "projects", "skills")

# Blender is Z up, three.js is Y up: (x, y, z) -> (x, z, -y)
TO_THREE = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))

scene = bpy.context.scene


def three_point(v):
    return [round(v.x, 5), round(v.z, 5), round(-v.y, 5)]


def vertical_fov(camera, aspect):
    data = camera.data
    fit = data.sensor_fit
    if fit == "VERTICAL":
        return 2 * math.atan(data.sensor_height / (2 * data.lens))
    if fit == "HORIZONTAL" or aspect >= 1:
        horizontal = 2 * math.atan(data.sensor_width / (2 * data.lens))
        return 2 * math.atan(math.tan(horizontal / 2) / aspect)
    return 2 * math.atan(data.sensor_width / (2 * data.lens))


def book_centre():
    points = []
    for obj in bpy.data.collections["Book"].objects:
        points += [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    lo = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    hi = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return (lo + hi) / 2


def tab_objects():
    tabs = {}
    for obj in bpy.data.collections["Tabs"].objects:
        section = obj.get("section")
        if section:
            tabs[section] = obj
    missing = [s for s in TAB_ORDER if s not in tabs]
    if missing:
        raise RuntimeError("Tabs collection is missing sections: " + ", ".join(missing))
    return tabs


def tab_quad(obj, camera):
    """Label face corners (TL, TR, BR, BL) in normalised frame coords, y down."""
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    face_y = min(ys)
    corners = (
        (min(xs), face_y, max(zs)), (max(xs), face_y, max(zs)),
        (max(xs), face_y, 0.0), (min(xs), face_y, 0.0),
    )
    quad = []
    for corner in corners:
        view = world_to_camera_view(scene, camera, obj.matrix_world @ Vector(corner))
        quad.append([round(view.x, 5), round(1 - view.y, 5)])
    return quad


def set_frame(camera, height):
    aspect = float(camera.get("frame_aspect", 1.5))
    scene.camera = camera
    scene.render.resolution_y = int(height)
    scene.render.resolution_x = int(round(height * aspect))
    scene.render.resolution_percentage = 100
    bpy.context.view_layer.update()
    return aspect


def view_meta(camera, view_id, tabs, centre):
    aspect = set_frame(camera, 1000)
    world = camera.matrix_world
    position = world.translation
    forward = (world.to_3x3() @ Vector((0, 0, -1))).normalized()
    pivot = position + forward * (centre - position).dot(forward)
    quaternion = (TO_THREE @ world.to_3x3().normalized()).to_quaternion()
    return {
        "aspect": round(aspect, 5),
        "safeAspect": round(float(camera.get("safe_aspect", aspect)), 5),
        "fovY": round(math.degrees(vertical_fov(camera, aspect)), 4),
        "position": three_point(position),
        "quaternion": [round(quaternion.x, 6), round(quaternion.y, 6), round(quaternion.z, 6), round(quaternion.w, 6)],
        "pivot": three_point(pivot),
        "poster": "posters/book-%s.webp" % view_id,
        "tabs": {section: tab_quad(tabs[section], camera) for section in TAB_ORDER},
    }


def cameras():
    found = {}
    for obj in bpy.data.collections["Cameras"].objects:
        if obj.type == "CAMERA" and obj.name.startswith("Camera_"):
            found[obj.name[len("Camera_"):].lower()] = obj
    for required in ("desktop", "mobile"):
        if required not in found:
            raise RuntimeError("Cameras collection needs Camera_%s" % required.capitalize())
    return found


def write_meta(views, tabs):
    centre = book_centre()
    meta = {"tabOrder": list(TAB_ORDER), "views": {vid: view_meta(cam, vid, tabs, centre) for vid, cam in views.items()}}
    os.makedirs(os.path.dirname(META_PATH), exist_ok=True)
    with open(META_PATH, "w") as handle:
        json.dump(meta, handle, indent=2)
        handle.write("\n")
    print("[export_book] wrote", META_PATH)


def tag_lights():
    """The glTF exporter does not carry sun strength reliably, so pass it as node extras.
    These properties are set in memory only; book.blend is never saved from here."""
    for obj in bpy.data.collections["Lights"].objects:
        if obj.type != "LIGHT":
            continue
        obj["strength"] = float(obj.data.energy) * (2.0 ** float(getattr(obj.data, "exposure", 0.0)))
        obj["shadow"] = bool(getattr(obj.data, "use_shadow", True))


def export_glb():
    tag_lights()
    for obj in bpy.data.objects:
        obj.select_set(False)
    for name in EXPORT_COLLECTIONS:
        for obj in bpy.data.collections[name].objects:
            obj.hide_set(False)
            obj.select_set(True)
    os.makedirs(os.path.dirname(GLB_PATH), exist_ok=True)
    wanted = dict(
        filepath=GLB_PATH, export_format="GLB", use_selection=True, export_apply=True,
        export_yup=True, export_cameras=False, export_lights=True,
        export_import_convert_lighting_mode="RAW", export_extras=True,
        export_texcoords=False, export_tangents=False, export_animations=False,
        export_skins=False, export_morph=False,
    )
    known = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    bpy.ops.export_scene.gltf(**{k: v for k, v in wanted.items() if k in known})
    print("[export_book] wrote", GLB_PATH, "%.0f KB" % (os.path.getsize(GLB_PATH) / 1024))


def use_gpu():
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL" if sys.platform == "darwin" else "NONE"
        prefs.get_devices()
        for device in prefs.devices:
            device.use = True
        if prefs.compute_device_type != "NONE":
            scene.cycles.device = "GPU"
    except Exception as error:
        print("[export_book] GPU not available, rendering on CPU:", error)


def feather_poster(source, target, band=0.10):
    """Fade the soft ground shadow to nothing at the frame edges so the poster has no
    visible rectangle on the page. Opaque pixels (the book itself) are left alone."""
    import numpy as np

    image = bpy.data.images.load(source)
    width, height = image.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    pixels = pixels.reshape(height, width, 4)
    alpha = pixels[..., 3]
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)[None, :]
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
    edge = np.clip(np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y)) / band, 0.0, 1.0)
    edge = edge * edge * (3 - 2 * edge)
    solid = np.clip((alpha - 0.9) / 0.1, 0.0, 1.0)
    pixels[..., 3] = alpha * (edge + (1 - edge) * solid)
    image.pixels.foreach_set(pixels.ravel())
    image.filepath_raw = target
    image.file_format = "WEBP"
    image.save(quality=86)
    bpy.data.images.remove(image)


def render_posters(views):
    os.makedirs(POSTER_DIR, exist_ok=True)
    scene.render.engine = "CYCLES"
    scene.render.film_transparent = True
    use_gpu()
    if PREVIEW:
        scene.cycles.samples = 24
    settings = scene.render.image_settings
    settings.file_format = "PNG"
    settings.color_mode = "RGBA"
    # Posters show the book alone; the side props only appear in the live view.
    for obj in bpy.data.collections["Props"].objects:
        obj.hide_render = True
    for view_id, camera in views.items():
        height = int(camera.get("poster_height", 1000))
        set_frame(camera, 520 if PREVIEW else height)
        extension = "png" if PREVIEW else "webp"
        target = os.path.join(POSTER_DIR, "book-%s.%s" % (view_id, extension))
        if PREVIEW:
            scene.render.filepath = target
            bpy.ops.render.render(write_still=True)
        else:
            scratch = os.path.join(HERE, "preview", "poster-%s.png" % view_id)
            os.makedirs(os.path.dirname(scratch), exist_ok=True)
            scene.render.filepath = scratch
            bpy.ops.render.render(write_still=True)
            feather_poster(scratch, target)
        print("[export_book] rendered", target)


views = cameras()
tabs = tab_objects()
if not PREVIEW:
    write_meta(views, tabs)
    export_glb()
if POSTERS:
    render_posters(views)
