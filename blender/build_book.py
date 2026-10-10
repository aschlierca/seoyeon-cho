"""Bootstrap generator for blender/book.blend.

Run through `npm run asset:build`. It writes the first version of the book
scene from code. After that, book.blend is the source of truth and is meant to
be edited by hand in Blender; `npm run asset:export` turns it into the web
assets. This script refuses to overwrite an existing book.blend unless it is
called with --force (the npm wrapper backs the old file up first).

Scene contract (read by export_book.py and src/stage/BookStage.ts):
  Collections  Book, Room, Tabs, Props, Lights, Cameras, RenderOnly
  Tabs         Tab_About, Tab_Projects, Tab_Skills
               origin sits on the page top edge, local X = label reading
               direction, local -Y = label face, custom prop "section"
  Lights       Light_Key casts shadows, every other light is fill
  Cameras      Camera_Desktop, Camera_Mobile with custom props
               "frame_aspect" (poster shape), "safe_aspect" (the part that must
               always stay on screen), "poster_height" (pixels)
  Props        side pieces, shown live only when the viewport has room for them
  RenderOnly   objects used by poster renders only, never exported
"""

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "book.blend")
ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

if os.path.exists(OUT) and "--force" not in ARGV:
    print("[build_book] book.blend already exists; not overwriting. Pass --force to regenerate.")
    sys.exit(2)

random.seed(11)

# Start from an empty file before any data is created.
bpy.ops.wm.read_factory_settings(use_empty=True)

# ---------------------------------------------------------------- dimensions

W = 3.4      # page width, spine to fore-edge
H = 2.7      # page height
PZ = 0.06    # page bottom above the ground (cover overhang)
PT = PZ + H  # page top
TC = 0.07    # cover board thickness
OV = 0.06    # cover overhang past the pages
TPL = 0.14   # left page block thickness
TPR = 0.46   # right page block thickness
FL = 0.155   # finished floor height inside the room

TAB_W, TAB_H, TAB_R, TAB_T, TAB_DEPTH = 1.0, 0.44, 0.10, 0.028, 0.36

# ----------------------------------------------------------------- materials


def hex_to_linear(value):
    value = value.lstrip("#")
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]

    def to_linear(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return (*[to_linear(c) for c in channels], 1.0)


def set_input(node, names, value):
    for name in names:
        socket = node.inputs.get(name)
        if socket is not None:
            socket.default_value = value
            return True
    return False


MATERIALS = {}


def mat(name, color, rough=0.82, metal=0.0, emit=0.0, coat=0.0, film=0.0):
    if name in MATERIALS:
        return MATERIALS[name]
    material = bpy.data.materials.new(name)
    if material.node_tree is None:
        material.use_nodes = True
    bsdf = next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    linear = hex_to_linear(color)
    bsdf.inputs["Base Color"].default_value = linear
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emit > 0:
        set_input(bsdf, ("Emission Color", "Emission"), linear)
        set_input(bsdf, ("Emission Strength",), emit)
    if coat > 0:
        set_input(bsdf, ("Coat Weight", "Clearcoat"), coat)
        set_input(bsdf, ("Coat Roughness", "Clearcoat Roughness"), 0.25)
    if film > 0:
        set_input(bsdf, ("Thin Film Thickness",), film)
        set_input(bsdf, ("Thin Film IOR",), 1.45)
    material.diffuse_color = linear
    MATERIALS[name] = material
    return material


PAPER = mat("Paper", "#F4EDE0", 0.9)
PAPER_EDGE = mat("Paper_Edge", "#E9DFCD", 0.9)
CLOTH = mat("Cover_Sage", "#9AAA8D", 0.92)
WOOD_DARK = mat("Wood_Dark", "#BC8A5B", 0.75)
WOODS = [mat("Wood_A", "#DDB083", 0.7), mat("Wood_B", "#D5A576", 0.7), mat("Wood_C", "#E3BA90", 0.7)]
WOOD = mat("Wood_Furniture", "#D7AC7E", 0.68)
WOOD_PALE = mat("Wood_Pale", "#E6C8A2", 0.7)
SAGE_PAINT = mat("Paint_Sage", "#93A694", 0.6)
OFF_WHITE = mat("Off_White", "#F3F0EA", 0.55)
HANDLE = mat("Handle", "#EFE8DC", 0.5)
METAL = mat("Metal", "#BABEC4", 0.38, metal=0.7)
SILVER = mat("Laptop_Silver", "#CCD0D5", 0.35, metal=0.75)
SCREEN = mat("Screen", "#1E2A44", 0.25, emit=0.35)
RUG = mat("Rug_Blue", "#94ACCD", 0.95)
RUG_PANEL = mat("Rug_Panel", "#BCCBE3", 0.95)
RUG_LINE = mat("Rug_Line", "#EFE7D8", 0.95)
SKY = mat("Window_Sky", "#D6E8F6", 0.3, emit=0.5)
SKYLINE = mat("Window_Skyline", "#B7CFE8", 0.4, emit=0.3)
PEGBOARD = mat("Pegboard", "#EBDCC3", 0.85)
LEAF = [mat("Leaf_A", "#86A774", 0.6), mat("Leaf_B", "#A3BF8E", 0.6), mat("Leaf_C", "#6F9463", 0.6)]
TERRACOTTA = mat("Terracotta", "#D99C7A", 0.8)
SOIL = mat("Soil", "#6B5140", 0.95)
COFFEE = mat("Coffee", "#7B4A2D", 0.3)
MILK = mat("Coffee_Milk", "#E6D3B8", 0.3)
INK = mat("Ink", "#3B3F4A", 0.5)
SLATE = mat("Book_Slate", "#7F95B8", 0.8)
PASTELS = [
    mat("Pastel_Rose", "#E8B4B8", 0.8),
    mat("Pastel_Gold", "#F1D39A", 0.8),
    mat("Pastel_Blue", "#A9C1EC", 0.8),
    mat("Pastel_Lilac", "#C9B8E0", 0.8),
    mat("Pastel_Coral", "#E9A583", 0.8),
    mat("Pastel_Mint", "#A9D2BC", 0.8),
    CLOTH,
    SLATE,
    PAPER,
]
CODE_LINES = [
    mat("Code_Blue", "#A9C1EC", 0.4, emit=1.2),
    mat("Code_Gold", "#F1D39A", 0.4, emit=1.2),
    mat("Code_Rose", "#E8B4B8", 0.4, emit=1.2),
    mat("Code_Mint", "#A9D2BC", 0.4, emit=1.2),
]
TAB_MATERIALS = {
    "about": mat("Tab_Rose", "#F0B5BE", 0.36, coat=0.5, film=420.0),
    "projects": mat("Tab_Gold", "#F3D595", 0.36, coat=0.5, film=380.0),
    "skills": mat("Tab_Blue", "#A8C0EC", 0.36, coat=0.5, film=460.0),
}

# ------------------------------------------------------------- mesh builder


class Builder:
    """Accumulates primitives into one mesh so each prop is a single object."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.materials = []
        self.xf = Matrix.Identity(4)

    def place(self, location=(0, 0, 0), rz=0.0):
        self.xf = Matrix.Translation(location) @ Matrix.Rotation(rz, 4, "Z")
        return self

    def _paint(self, verts, material, smooth):
        if material not in self.materials:
            self.materials.append(material)
        index = self.materials.index(material)
        faces = set()
        for vert in verts:
            faces.update(vert.link_faces)
        for face in faces:
            face.material_index = index
            face.smooth = smooth(face) if callable(smooth) else smooth

    def cbox(self, center, size, material, rot=None, rz=0.0):
        rotation = Euler(rot).to_matrix().to_4x4() if rot else Matrix.Rotation(rz, 4, "Z")
        matrix = self.xf @ Matrix.Translation(center) @ rotation @ Matrix.Diagonal((*size, 1.0))
        result = bmesh.ops.create_cube(self.bm, size=1.0, matrix=matrix)
        self._paint(result["verts"], material, False)

    def box(self, lo, hi, material):
        lo, hi = Vector(lo), Vector(hi)
        self.cbox((lo + hi) / 2, hi - lo, material)

    def cyl(self, base, radius, height, material, top_radius=None, segments=20, rot=None):
        top_radius = radius if top_radius is None else top_radius
        rotation = Euler(rot).to_matrix().to_4x4() if rot else Matrix.Identity(4)
        matrix = self.xf @ Matrix.Translation(base) @ rotation @ Matrix.Translation((0, 0, height / 2))
        result = bmesh.ops.create_cone(
            self.bm, cap_ends=True, cap_tris=False, segments=segments,
            radius1=radius, radius2=top_radius, depth=height, matrix=matrix,
        )
        self._paint(result["verts"], material, lambda face: len(face.verts) <= 4)

    def blob(self, center, radius, material, scale=(1, 1, 1), rot=None, detail=2):
        rotation = Euler(rot).to_matrix().to_4x4() if rot else Matrix.Identity(4)
        matrix = self.xf @ Matrix.Translation(center) @ rotation @ Matrix.Diagonal((*scale, 1.0))
        result = bmesh.ops.create_icosphere(self.bm, subdivisions=detail, radius=radius, matrix=matrix)
        self._paint(result["verts"], material, True)

    def finish(self, collection, bevel=0.0, origin=None):
        mesh = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(mesh)
        self.bm.free()
        for material in self.materials:
            mesh.materials.append(material)
        obj = bpy.data.objects.new(self.name, mesh)
        collection.objects.link(obj)

        # Put the origin at the bottom centre so the piece is easy to move by hand.
        if origin is None:
            xs = [v.co.x for v in mesh.vertices]
            ys = [v.co.y for v in mesh.vertices]
            zs = [v.co.z for v in mesh.vertices]
            origin = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs)))
        origin = Vector(origin)
        mesh.transform(Matrix.Translation(-origin))
        obj.location = origin

        if bevel > 0:
            for polygon in mesh.polygons:
                polygon.use_smooth = True
            modifier = obj.modifiers.new("Bevel", "BEVEL")
            modifier.width = bevel
            modifier.segments = 2
            modifier.limit_method = "ANGLE"
            modifier.angle_limit = math.radians(40)
            normals = obj.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
            normals.keep_sharp = True
            normals.weight = 100
        return obj


def collection(name):
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll


def book_row(builder, start, length, depth, max_height, along="x"):
    """A shelf row of upright books. start is the row's low corner at shelf height."""
    cursor = 0.0
    x0, y0, z0 = start
    while cursor < length - 0.03:
        thickness = random.uniform(0.035, 0.075)
        if cursor + thickness > length:
            break
        height = random.uniform(0.62, 1.0) * max_height
        book_depth = depth * random.uniform(0.8, 1.0)
        material = random.choice(PASTELS)
        if along == "x":   # spines face -Y, books sit against a wall at y0
            builder.box((x0 + cursor, y0 - book_depth, z0), (x0 + cursor + thickness, y0, z0 + height), material)
        else:              # spines face +X, books sit against a wall at x0
            builder.box((x0, y0 + cursor, z0), (x0 + book_depth, y0 + cursor + thickness, z0 + height), material)
        cursor += thickness + random.choice((0.0, 0.0, 0.004, 0.03))


def foliage(builder, center, spread, count, size=0.08):
    cx, cy, cz = center
    for _ in range(count):
        offset = Vector((random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(0, 1.2)))
        radius = size * random.uniform(0.7, 1.15)
        builder.blob(
            (cx + offset.x * spread, cy + offset.y * spread, cz + offset.z * spread),
            radius, random.choice(LEAF), scale=(1, 1, 0.8), detail=1,
        )


# --------------------------------------------------------------------- scene

scene = bpy.context.scene
scene.name = "Book"

BOOK = collection("Book")
ROOM = collection("Room")
TABS = collection("Tabs")
PROPS = collection("Props")
LIGHTS = collection("Lights")
CAMERAS = collection("Cameras")
RENDER_ONLY = collection("RenderOnly")

# ---- book: cloth covers

b = Builder("Book_Cover")
b.box((-TPL - TC, -W - OV, 0), (-TPL, TPR, PT + OV), CLOTH)            # left board
b.box((-TPL - TC, TPR, 0), (W + OV, TPR + TC, PT + OV), CLOTH)         # right board and spine
b.finish(BOOK, bevel=0.014)

# ---- book: page blocks, built in layers so the fore-edges read as paper

b = Builder("Book_Pages")
layers = 8
step = TPR / layers
for i in range(layers):
    inset = 0.0 if i == 0 else random.uniform(0.004, 0.03)
    jitter = 0.0 if i == 0 else random.uniform(0.0, 0.012)
    b.box((0, i * step, PZ + jitter), (W - inset, (i + 1) * step, PT - jitter), PAPER if i % 2 == 0 else PAPER_EDGE)
layers = 3
step = TPL / layers
for i in range(layers):
    inset = 0.0 if i == 0 else random.uniform(0.004, 0.025)
    jitter = 0.0 if i == 0 else random.uniform(0.0, 0.01)
    b.box((-(i + 1) * step, -W + inset, PZ + jitter), (-i * step, 0, PT - jitter), PAPER if i % 2 == 0 else PAPER_EDGE)
b.box((-TPL, 0, PZ), (0, TPR, PT), PAPER_EDGE)                          # gutter
b.finish(BOOK)

# ---- room: floor, planks, rug

b = Builder("Room_Floor")
floor_x, floor_y = W - 0.12, -2.05
b.box((0, floor_y, 0), (floor_x, 0, 0.14), WOOD_DARK)
plank, gap = 0.196, 0.008
row = 0
y = floor_y + 0.012
while y + plank <= -0.004:
    x = 0.012
    first = True
    while x < floor_x - 0.02:
        length = random.uniform(0.75, 1.35) * (0.55 if first and row % 2 else 1.0)
        end = min(x + length, floor_x - 0.012)
        if floor_x - 0.012 - end < 0.25:
            end = floor_x - 0.012
        b.box((x, y, 0.14), (end, y + plank, FL), random.choice(WOODS))
        x = end + gap
        first = False
    y += plank + gap
    row += 1
b.box((0.55, -1.88, FL), (2.75, -0.66, FL + 0.013), RUG)
for lo, hi in (
    ((0.63, -1.80, 0), (2.67, -1.775, 0)), ((0.63, -0.765, 0), (2.67, -0.74, 0)),
    ((0.63, -1.775, 0), (0.655, -0.765, 0)), ((2.645, -1.775, 0), (2.67, -0.765, 0)),
):
    b.box((lo[0], lo[1], FL + 0.013), (hi[0], hi[1], FL + 0.016), RUG_LINE)
b.box((0.80, -1.63, FL + 0.013), (2.50, -0.91, FL + 0.0155), RUG_PANEL)
b.cbox((1.65, -1.27, FL + 0.017), (0.42, 0.42, 0.003), RUG_LINE, rz=math.radians(45))
b.cbox((1.65, -1.27, FL + 0.019), (0.24, 0.24, 0.003), RUG, rz=math.radians(45))
b.finish(ROOM)

# ---- room: desk with drawer unit

b = Builder("Room_Desk")
b.box((0.75, -0.82, 0.98), (3.05, -0.06, 1.04), WOOD)
b.box((0.80, -0.78, FL), (0.86, -0.10, 0.98), WOOD)
b.box((2.40, -0.78, FL), (3.00, -0.10, 0.98), WOOD)
for z0, z1 in ((0.19, 0.43), (0.46, 0.70), (0.73, 0.95)):
    b.box((2.43, -0.805, z0), (2.97, -0.78, z1), SAGE_PAINT)
    mid = (z0 + z1) / 2
    b.box((2.62, -0.826, mid - 0.012), (2.78, -0.805, mid + 0.012), HANDLE)
b.finish(ROOM, bevel=0.01)

# ---- room: everything standing on the desk

b = Builder("Room_DeskItems")
# laptop, screen toward the chair
b.cbox((1.85, -0.46, 1.049), (0.44, 0.30, 0.018), SILVER)
tilt = math.radians(-14)
hinge = Vector((1.85, -0.31, 1.056))
screen_rot = (tilt, 0, 0)
up = Euler(screen_rot).to_matrix() @ Vector((0, 0, 1))
out = Euler(screen_rot).to_matrix() @ Vector((0, -1, 0))
b.cbox(hinge + up * 0.15, (0.44, 0.014, 0.30), SILVER, rot=screen_rot)
b.cbox(hinge + up * 0.15 + out * 0.008, (0.40, 0.004, 0.25), SCREEN, rot=screen_rot)
for i, (indent, length) in enumerate(((0.0, 0.16), (0.03, 0.22), (0.03, 0.12), (0.06, 0.18), (0.03, 0.09), (0.0, 0.14))):
    centre = hinge + up * (0.245 - i * 0.032) + out * 0.0115 + Vector((-0.17 + indent + length / 2, 0, 0))
    b.cbox(centre, (length, 0.002, 0.011), CODE_LINES[i % len(CODE_LINES)], rot=screen_rot)
# lamp
b.cyl((1.10, -0.28, 1.04), 0.085, 0.018, OFF_WHITE)
b.cyl((1.10, -0.28, 1.058), 0.011, 0.33, METAL, segments=10)
arm = math.radians(55)
b.cyl((1.10, -0.28, 1.388), 0.011, 0.26, METAL, segments=10, rot=(0, arm, 0))
tip = Vector((1.10 + 0.26 * math.sin(arm), -0.28, 1.388 + 0.26 * math.cos(arm)))
b.cyl((tip.x + 0.02, tip.y, tip.z - 0.11), 0.11, 0.12, OFF_WHITE, top_radius=0.045)
b.blob((tip.x + 0.02, tip.y, tip.z - 0.09), 0.035, mat("Lamp_Bulb", "#FFE7B8", 0.4, emit=3.0), detail=1)
# mug
b.cyl((2.20, -0.55, 1.04), 0.045, 0.085, OFF_WHITE, segments=16)
b.cyl((2.20, -0.55, 1.125), 0.037, 0.003, COFFEE, segments=16)
# notebook and pen
b.cbox((2.62, -0.50, 1.05), (0.26, 0.34, 0.02), SLATE, rz=0.2)
b.cbox((2.62, -0.50, 1.066), (0.012, 0.2, 0.012), INK, rz=0.55)
# pencil cup
b.cyl((2.80, -0.22, 1.04), 0.042, 0.10, PASTELS[0], segments=14)
for dx, dy, lean, colour in ((0.012, 0.0, 0.14, PASTELS[1]), (-0.012, 0.008, -0.12, PASTELS[2]), (0.0, -0.012, 0.05, INK)):
    b.cyl((2.80 + dx, -0.22 + dy, 1.08), 0.007, 0.15, colour, segments=6, rot=(lean, lean, 0))
# desk plant
b.cyl((1.42, -0.22, 1.04), 0.058, 0.10, TERRACOTTA, top_radius=0.075, segments=14)
foliage(b, (1.42, -0.22, 1.17), 0.07, 9, size=0.065)
b.finish(ROOM)

# ---- room: chair, seen from behind

b = Builder("Room_Chair").place((1.72, -1.34, 0), math.radians(-16))
for k in range(5):
    angle = math.radians(90 + k * 72)
    direction = Vector((math.cos(angle), math.sin(angle), 0))
    b.cbox(direction * 0.15 + Vector((0, 0, FL + 0.068)), (0.30, 0.05, 0.035), METAL, rz=angle)
    b.blob(direction * 0.29 + Vector((0, 0, FL + 0.034)), 0.034, INK, detail=1)
b.cyl((0, 0, FL + 0.08), 0.028, 0.37, METAL, segments=12)
b.cbox((0, 0, 0.635), (0.52, 0.50, 0.07), OFF_WHITE)
b.cbox((0, 0.01, 0.685), (0.46, 0.44, 0.045), PASTELS[2])
b.cbox((0, -0.255, 0.80), (0.08, 0.035, 0.30), METAL)
lean = (math.radians(-9), 0, 0)
b.cbox((0, -0.285, 1.08), (0.48, 0.06, 0.46), OFF_WHITE, rot=lean)
b.cbox((0, -0.256, 1.08), (0.42, 0.03, 0.40), PASTELS[2], rot=lean)
b.finish(ROOM, bevel=0.014)

# ---- room: tall bookshelf on the left wall

b = Builder("Room_Bookshelf")
sx0, sx1, sy0, sy1 = 0.0, 0.32, -2.0, -1.52
b.box((sx0, sy0, FL), (sx1, sy0 + 0.03, 2.15), WOOD)
b.box((sx0, sy1 - 0.03, FL), (sx1, sy1, 2.15), WOOD)
shelf_levels = (FL, 0.63, 1.10, 1.57, 2.12)
for z in shelf_levels:
    b.box((sx0, sy0 + 0.03, z), (sx1, sy1 - 0.03, z + 0.03), WOOD)
book_row(b, (0.03, sy0 + 0.04, 0.66), 0.40, 0.22, 0.40, along="y")
book_row(b, (0.03, sy0 + 0.04, 1.13), 0.22, 0.22, 0.40, along="y")
book_row(b, (0.03, sy0 + 0.04, 1.60), 0.40, 0.22, 0.46, along="y")
b.cyl((0.16, -1.66, 1.13), 0.055, 0.09, OFF_WHITE, top_radius=0.065, segments=14)
foliage(b, (0.16, -1.66, 1.25), 0.055, 7, size=0.055)
b.box((0.04, -1.93, FL + 0.03), (0.28, -1.60, FL + 0.27), PASTELS[5])
# loose stack on the floor beside it
b.cbox((0.62, -1.34, FL + 0.025), (0.32, 0.23, 0.05), PASTELS[0], rz=0.12)
b.cbox((0.61, -1.35, FL + 0.072), (0.30, 0.22, 0.044), PAPER, rz=-0.08)
b.cbox((0.62, -1.34, FL + 0.114), (0.27, 0.20, 0.04), SLATE, rz=0.3)
b.finish(ROOM, bevel=0.006)

# ---- room: window on the left wall

b = Builder("Room_Window")
wy0, wy1, wz0, wz1 = -1.33, -0.37, 1.08, 2.22
b.box((0, wy0, wz0), (0.05, wy0 + 0.06, wz1), WOOD_PALE)
b.box((0, wy1 - 0.06, wz0), (0.05, wy1, wz1), WOOD_PALE)
b.box((0, wy0 + 0.06, wz1 - 0.06), (0.05, wy1 - 0.06, wz1), WOOD_PALE)
b.box((0, wy0 + 0.06, wz0), (0.05, wy1 - 0.06, wz0 + 0.06), WOOD_PALE)
b.box((0.006, -0.865, wz0 + 0.06), (0.04, -0.835, wz1 - 0.06), WOOD_PALE)
b.box((0.006, wy0 + 0.06, 1.72), (0.04, wy1 - 0.06, 1.75), WOOD_PALE)
b.box((0, wy0 + 0.06, wz0 + 0.06), (0.012, wy1 - 0.06, wz1 - 0.06), SKY)
for y0, y1, top in ((-1.22, -1.06, 1.56), (-1.02, -0.92, 1.84), (-0.80, -0.62, 1.44), (-0.60, -0.50, 1.66)):
    b.box((0.012, y0, wz0 + 0.06), (0.016, y1, top), SKYLINE)
b.box((0, wy0 - 0.05, 1.03), (0.16, wy1 + 0.05, wz0), WOOD_PALE)
b.cyl((0.09, -0.60, wz0), 0.045, 0.075, TERRACOTTA, top_radius=0.056, segments=12)
foliage(b, (0.09, -0.60, wz0 + 0.11), 0.045, 6, size=0.05)
b.finish(ROOM, bevel=0.005)

# ---- room: wall shelf, pegboard, framed picture on the right wall

b = Builder("Room_WallShelf")
b.box((0.95, -0.24, 2.12), (2.40, 0, 2.16), WOOD)
b.box((1.10, -0.20, 2.02), (1.13, 0, 2.12), WOOD)
b.box((2.22, -0.20, 2.02), (2.25, 0, 2.12), WOOD)
book_row(b, (1.55, -0.03, 2.16), 0.55, 0.18, 0.32, along="x")
b.cyl((1.12, -0.12, 2.16), 0.06, 0.10, OFF_WHITE, top_radius=0.07, segments=14)
foliage(b, (1.12, -0.12, 2.28), 0.06, 8, size=0.06)
for i in range(9):   # trailing vine
    b.blob((1.02 + math.sin(i * 1.3) * 0.035, -0.07, 2.16 - i * 0.075), 0.045 - i * 0.002, random.choice(LEAF), scale=(1, 0.7, 1), detail=1)
b.blob((2.28, -0.12, 2.215), 0.055, OFF_WHITE, scale=(1, 1, 1.1), detail=2)
b.finish(ROOM, bevel=0.005)

b = Builder("Room_Pegboard")
b.box((1.25, -0.025, 1.22), (2.30, 0, 1.98), PEGBOARD)
cards = (
    (1.33, 1.66, 0.20, 0.26, 0), (1.58, 1.70, 0.18, 0.22, 1), (1.80, 1.64, 0.22, 0.28, 2),
    (2.07, 1.70, 0.17, 0.22, 3), (1.36, 1.30, 0.22, 0.28, 4), (1.64, 1.32, 0.18, 0.24, 5),
    (1.88, 1.30, 0.16, 0.20, 1), (2.08, 1.32, 0.17, 0.26, 0),
)
for x, z, w, h, colour in cards:
    b.box((x, -0.032, z), (x + w, -0.025, z + h), PAPER)
    b.box((x + 0.018, -0.035, z + h * 0.34), (x + w - 0.018, -0.032, z + h - 0.02), PASTELS[colour])
b.box((2.60, -0.03, 1.42), (3.02, 0, 1.96), WOOD_PALE)
b.box((2.64, -0.036, 1.46), (2.98, -0.03, 1.92), SKY)
b.box((2.64, -0.040, 1.46), (2.98, -0.036, 1.62), LEAF[1])
b.cyl((2.88, -0.036, 1.80), 0.045, 0.004, PASTELS[1], segments=18, rot=(math.radians(90), 0, 0))
b.finish(ROOM)

# ---- tabs: rounded-top slabs, one object each


def build_tab(section, y_centre, x_layer):
    name = "Tab_" + section.capitalize()
    bm = bmesh.new()
    half = TAB_W / 2
    profile = [(-half, -TAB_DEPTH), (half, -TAB_DEPTH), (half, TAB_H - TAB_R)]
    for i in range(1, 8):
        a = (i / 8) * math.pi / 2
        profile.append((half - TAB_R + TAB_R * math.cos(a), TAB_H - TAB_R + TAB_R * math.sin(a)))
    profile += [(half - TAB_R, TAB_H), (-half + TAB_R, TAB_H)]
    for i in range(1, 8):
        a = math.pi / 2 + (i / 8) * math.pi / 2
        profile.append((-half + TAB_R + TAB_R * math.cos(a), TAB_H - TAB_R + TAB_R * math.sin(a)))
    profile.append((-half, TAB_H - TAB_R))
    front = [bm.verts.new((x, -TAB_T / 2, z)) for x, z in profile]
    back = [bm.verts.new((x, TAB_T / 2, z)) for x, z in profile]
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    count = len(profile)
    for i in range(count):
        j = (i + 1) % count
        bm.faces.new((front[j], front[i], back[i], back[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(TAB_MATERIALS[section])
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (x_layer, y_centre, PT)
    obj.rotation_euler = (0, 0, math.pi / 2)   # local X runs along the page top, face looks out at +X
    obj["section"] = section
    TABS.objects.link(obj)
    return obj


build_tab("about", -2.78, -0.030)
build_tab("projects", -1.72, -0.065)
build_tab("skills", -0.66, -0.100)

# ---- props around the book

b = Builder("Prop_BookStack").place((0.6, -4.1, 0), math.radians(22))


def lying_book(builder, z, size, cover, rz, offset=(0, 0)):
    sx, sy = size
    ox, oy = offset
    builder.cbox((ox, oy, z + 0.012), (sx, sy, 0.024), cover, rz=rz)
    builder.cbox((ox + 0.012 * math.cos(rz), oy + 0.012 * math.sin(rz), z + 0.076), (sx - 0.05, sy - 0.04, 0.104), PAPER, rz=rz)
    builder.cbox((ox, oy, z + 0.140), (sx, sy, 0.024), cover, rz=rz)
    spine = Matrix.Rotation(rz, 3, "Z") @ Vector((-sx / 2 + 0.011, 0, 0))
    builder.cbox((ox + spine.x, oy + spine.y, z + 0.076), (0.024, sy, 0.150), cover, rz=rz)


lying_book(b, 0.0, (1.0, 0.72), SLATE, 0.0)
lying_book(b, 0.152, (0.86, 0.62), mat("Book_Cream", "#EDE4D3", 0.85), math.radians(13), offset=(0.02, 0.01))
cup = Vector((0.14, 0.02, 0.304))
b.cyl(cup, 0.13, 0.012, HANDLE, segments=24)                                        # coaster
b.cyl(cup + Vector((0, 0, 0.012)), 0.082, 0.19, COFFEE, top_radius=0.098, segments=24)
b.cyl(cup + Vector((0, 0, 0.202)), 0.098, 0.07, MILK, top_radius=0.104, segments=24)
b.cyl(cup + Vector((0, 0, 0.272)), 0.110, 0.018, OFF_WHITE, segments=24)
b.cyl(cup + Vector((0.02, 0, 0.20)), 0.008, 0.24, INK, segments=8, rot=(0, math.radians(9), 0))
b.cbox((0.86, -0.34, 0.016), (0.30, 0.40, 0.032), PASTELS[2], rz=math.radians(28))
b.finish(PROPS, bevel=0.01)

b = Builder("Prop_Plant").place((4.5, 1.3, 0), 0.4)
b.cyl((0, 0, 0), 0.20, 0.34, OFF_WHITE, top_radius=0.26, segments=28)
b.cyl((0, 0, 0.335), 0.24, 0.012, SOIL, segments=28)
for i in range(11):
    turn = i * 2.4
    raise_angle = math.radians(random.uniform(28, 66))
    reach = random.uniform(0.26, 0.44)
    height = 0.42 + i * 0.045
    rotation = Euler((0, -raise_angle, turn), "XYZ")
    centre = rotation.to_matrix() @ Vector((reach, 0, 0)) + Vector((0, 0, height))
    b.blob(centre, 1.0, LEAF[i % 3], scale=(0.24, 0.13, 0.014), rot=(0, -raise_angle, turn), detail=2)
    stem_dir = centre - Vector((0, 0, 0.34))
    b.cyl((0, 0, 0.34), 0.009, stem_dir.length * 0.82, LEAF[2], segments=6,
          rot=stem_dir.to_track_quat("Z", "Y").to_euler())
b.finish(PROPS)

# ---- poster-only ground that catches shadows

ground_mesh = bpy.data.meshes.new("Ground")
ground_mesh.from_pydata([(-40, -40, 0), (40, -40, 0), (40, 40, 0), (-40, 40, 0)], [], [(0, 1, 2, 3)])
ground = bpy.data.objects.new("Ground", ground_mesh)
ground_mesh.materials.append(mat("Ground", "#F6F1EA", 1.0))
RENDER_ONLY.objects.link(ground)
try:
    ground.is_shadow_catcher = True
except Exception:
    pass

# ---- lights

focus = Vector((1.2, -1.2, 1.3))


def sun(name, toward, strength, colour, angle_deg, shadow):
    data = bpy.data.lights.new(name, "SUN")
    data.energy = strength
    data.color = colour
    data.angle = math.radians(angle_deg)
    try:
        data.use_shadow = shadow
    except Exception:
        pass
    obj = bpy.data.objects.new(name, data)
    direction = Vector(toward).normalized()
    obj.location = focus + direction * 14
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    LIGHTS.objects.link(obj)
    return obj


sun("Light_Key", (0.56, -0.22, 0.80), 2.3, (1.0, 0.955, 0.89), 9, True)
sun("Light_Fill", (0.30, -0.80, 0.50), 0.6, (0.93, 0.96, 1.0), 40, False)

world = bpy.data.worlds.new("World")
if world.node_tree is None:
    world.use_nodes = True
background = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None)
if background is not None:
    background.inputs["Color"].default_value = (0.94, 0.96, 1.0, 1.0)
    background.inputs["Strength"].default_value = 0.45
scene.world = world

# ---- cameras: direction and field of view are authored here, read by the site


def framing_points():
    """Everything the safe area must contain: the book, the room, and the tabs at full lift."""
    points = []
    for coll in (BOOK, ROOM, TABS):
        for obj in coll.objects:
            lift = Vector((0, 0, 0.16)) if coll is TABS else Vector((0, 0, 0))
            points += [obj.matrix_world @ vertex.co + lift for vertex in obj.data.vertices]
    return points


def fit_camera(obj, points, fov_y, safe_aspect, margin=0.06):
    """Slide and dolly the camera, keeping its direction, until the points fill the safe area."""
    basis = obj.rotation_euler.to_matrix()
    right, up, back = basis.col[0].copy(), basis.col[1].copy(), basis.col[2].copy()
    tan_v = math.tan(fov_y / 2)
    tan_h = tan_v * safe_aspect
    for _ in range(16):
        location = obj.location.copy()
        xs, ys, depths = [], [], []
        for point in points:
            offset = point - location
            depth = -offset.dot(back)
            xs.append(offset.dot(right) / depth / tan_h)
            ys.append(offset.dot(up) / depth / tan_v)
            depths.append(depth)
        mean_depth = sum(depths) / len(depths)
        centre_x, centre_y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        half = max((max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2)
        location += right * (centre_x * tan_h * mean_depth) + up * (centre_y * tan_v * mean_depth)
        location += back * (mean_depth * (half / (1 - margin) - 1))
        obj.location = location


def camera(name, target, azimuth_deg, elevation_deg, distance, fov_y_deg, frame_aspect, safe_aspect, poster_height):
    data = bpy.data.cameras.new(name)
    data.sensor_fit = "VERTICAL"
    data.sensor_height = 24.0
    data.lens = 12.0 / math.tan(math.radians(fov_y_deg) / 2)
    data.clip_start = 1.0
    data.clip_end = 80.0
    obj = bpy.data.objects.new(name, data)
    azimuth, elevation = math.radians(azimuth_deg), math.radians(elevation_deg)
    to_camera = Vector((math.cos(elevation) * math.cos(azimuth), -math.cos(elevation) * math.sin(azimuth), math.sin(elevation)))
    obj.location = Vector(target) + to_camera * distance
    obj.rotation_euler = (-to_camera).to_track_quat("-Z", "Y").to_euler()
    obj["frame_aspect"] = frame_aspect
    obj["safe_aspect"] = safe_aspect
    obj["poster_height"] = poster_height
    CAMERAS.objects.link(obj)
    bpy.context.view_layer.update()
    fit_camera(obj, framing_points(), math.radians(fov_y_deg), safe_aspect)
    return obj


desktop = camera("Camera_Desktop", (1.17, -1.17, 1.33), 33, 24, 13.4, 22, 1.5, 1.25, 1240)
camera("Camera_Mobile", (0.85, -1.24, 1.32), 17, 23, 15.0, 22, 1.15, 1.08, 1140)
scene.camera = desktop

# ---- render settings used by poster export

scene.render.engine = "CYCLES"
scene.render.film_transparent = True
scene.cycles.samples = 128
try:
    scene.cycles.use_denoising = True
except Exception:
    pass
# Same tone curve as the site's renderer, so posters and the live view agree.
for transform in ("Khronos PBR Neutral", "Standard"):
    try:
        scene.view_settings.view_transform = transform
        break
    except TypeError:
        continue
scene.view_settings.look = "None"
scene.render.resolution_x = 2400
scene.render.resolution_y = 1200

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("[build_book] wrote", OUT)
