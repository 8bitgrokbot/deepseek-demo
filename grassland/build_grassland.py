#!/usr/bin/env python3
"""
build_grassland.py -- stylized low/mid-poly GRASSLAND landscape with wind animation.

Blender 4.2 (headless, Cycles CPU).  Procedural only (no external images/fonts/addons).

Modes (environment variables)
  (default)        build -> save .blend -> export .glb -> render ONE still
  GRASS_MODE=anim  build -> save .blend -> render animation frames to D/anim/frame_####.png
Optional knobs:
  GRASS_RES_PCT (100), GRASS_SAMPLES (20), GRASS_STILL_FRAME (1),
  GRASS_STILL_PATH (D/render/grassland_still.png),
  GRASS_FRAMES (192), GRASS_FRAME_START (1), GRASS_FRAME_END (FRAMES)

Notes / limitations
  * Wind is done with shape keys (Basis + 'sway_wind' + 'sway_cross') per grass patch and on
    the flower mesh.  Shape-key (morph) animation IS exported to glTF, so the sway travels
    to the .glb as morph target animation.
  * Sky uses a procedural vertical gradient world (allowed alternative to Nishita); the Sun
    lamp is the only light source, so there is no doubled sun disc.
"""

import bpy
import bmesh
import math
import random
import os
import sys
from mathutils import Vector, Matrix

# ---------------------------------------------------------------- constants
D = '/workspace/grassland'
RENDER_DIR = os.path.join(D, 'render')
EXPORT_DIR = os.path.join(D, 'export')
ANIM_DIR = os.path.join(D, 'anim')
TMP_DIR = os.path.join(D, 'tmp')
for _d in (RENDER_DIR, EXPORT_DIR, ANIM_DIR, TMP_DIR):
    os.makedirs(_d, exist_ok=True)

MODE = os.environ.get('GRASS_MODE', '').strip().lower()
RES_PCT = int(os.environ.get('GRASS_RES_PCT', '100'))
SAMPLES = int(os.environ.get('GRASS_SAMPLES', '20'))
STILL_FRAME = int(os.environ.get('GRASS_STILL_FRAME', '1'))
STILL_PATH = os.environ.get('GRASS_STILL_PATH', os.path.join(RENDER_DIR, 'grassland_still.png'))
FRAMES = int(os.environ.get('GRASS_FRAMES', '192'))
FSTART = int(os.environ.get('GRASS_FRAME_START', '1'))
FEND = int(os.environ.get('GRASS_FRAME_END', str(FRAMES)))
FPS = 24
PERIOD = 192                       # animation loop length in frames (8 s @ 24 fps)

TOTAL_BLADES = 38000               # spec: 25k-40k blades, 3 tris each
TUFT_AVG = 1.5                     # blades per sampled tuft
FLOWER_TARGET = 340                # 250-400 flowers, in clusters
NX, NY = 6, 6                      # grass patch grid (36 patch objects)
GX0, GX1 = -60.0, 60.0             # grass/terrain x range
GY0, GY1 = -60.0, 40.0             # grass y range (meadow in front of the camera)
CW = (GX1 - GX0) / NX
CH = (GY1 - GY0) / NY

SWAY_AMP = 0.13                    # 13 cm blade-tip motion each way (26 cm peak-to-peak)
WIND = Vector((0.94, 0.34, 0.0)).normalized()          # wind direction (horizontal)
PERP = Vector((-WIND.y, WIND.x, 0.0))

random.seed(20240610)
T_ZERO = os.times().elapsed


# ---------------------------------------------------------------- terrain height
def h(x, y):
    """Smooth rolling-meadow height field, in metres (used for EVERYTHING)."""
    base = (1.4 * math.sin(x * 0.075 + 0.8) * math.cos(y * 0.060 - 0.4)
            + 0.70 * math.sin(x * 0.033 - 1.2)
            + 0.50 * math.cos(x * 0.055 + y * 0.075 + 2.1)
            + 0.30 * math.sin(y * 0.120 + 0.3))
    # keep a calm, nearly flat corridor around the camera path (front edge of the meadow)
    fade = min(1.0, max(0.0, (y + 46.0) / 22.0))
    return (0.12 + 0.88 * fade) * base


# ---------------------------------------------------------------- helpers
def clamp(v, a, b):
    return a if v < a else (b if v > b else v)


def new_collection(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def make_principled(name, color, rough=0.9, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (color[0], color[1], color[2], 1.0)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metallic
    return m


def make_emission(name, color):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    emi = nt.nodes.new('ShaderNodeEmission')
    emi.inputs['Color'].default_value = (color[0], color[1], color[2], 1.0)
    emi.inputs['Strength'].default_value = 1.0
    nt.links.new(emi.outputs['Emission'], out.inputs['Surface'])
    return m


def mesh_object(name, verts, faces, coll, mats=None, colors=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    me.update()
    if colors is not None:
        ca = me.color_attributes.new(name='Col', type='FLOAT_COLOR', domain='POINT')
        for i, c in enumerate(colors):
            ca.data[i].color = (c[0], c[1], c[2], 1.0)
    if mats:
        for m in mats:
            me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return ob


def add_shape_key_pair(ob, verts, weights, amp):
    """Basis + two sway keys whose deltas grow with 'weights' (0 at blade base, 1 at tip)."""
    ob.shape_key_add(name='Basis')
    for kname, dvec, kscale in (('sway_wind', WIND, 1.0), ('sway_cross', PERP, 0.55)):
        sk = ob.shape_key_add(name=kname)
        flat = []
        for i, co in enumerate(verts):
            w = weights[i] * amp * kscale
            flat.extend((co[0] + dvec.x * w, co[1] + dvec.y * w, co[2]))
        sk.data.foreach_set('co', flat)
    return ob


def animate_sway(ob, phase, amp_scale=1.0):
    kb = ob.data.shape_keys.key_blocks
    kw, kc = kb['sway_wind'], kb['sway_cross']
    for f in range(1, PERIOD + 2, 6):
        t = (f - 1) / float(PERIOD)
        kw.value = amp_scale * math.sin(2.0 * math.pi * t + phase)
        kc.value = amp_scale * 0.9 * math.sin(2.0 * math.pi * t + phase + 1.6)
        kw.keyframe_insert(data_path='value', frame=f)
        kc.keyframe_insert(data_path='value', frame=f)


def add_icosphere(bm, subdiv, radius, matrix):
    try:
        return bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius, matrix=matrix)
    except TypeError:                                    # older signature
        return bmesh.ops.create_icosphere(bm, subdivisions=subdiv, diameter=radius, matrix=matrix)


def add_cone(bm, segs, r1, r2, depth, matrix):
    try:
        return bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs,
                                     radius1=r1, radius2=r2, depth=depth, matrix=matrix)
    except TypeError:
        return bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs,
                                     diameter1=r1 * 2.0, diameter2=r2 * 2.0, depth=depth,
                                     matrix=matrix)


# ---------------------------------------------------------------- scene reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
scene.frame_start = 1
scene.frame_end = FRAMES
scene.render.fps = FPS
scene.render.fps_base = 1.0

COLL_MODEL = new_collection('Model')
COLL_LIGHTS = new_collection('Lights')
COLL_CAMERA = new_collection('Camera')

# ---------------------------------------------------------------- render settings
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = SAMPLES
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.02
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPENIMAGEDENOISE'
scene.cycles.denoising_use_gpu = False
scene.cycles.max_bounces = 4
scene.cycles.diffuse_bounces = 2
scene.cycles.glossy_bounces = 2
scene.cycles.transmission_bounces = 0
scene.cycles.volume_bounces = 0
scene.cycles.transparent_max_bounces = 2
scene.cycles.caustics_reflective = False
scene.cycles.caustics_refractive = False
scene.cycles.use_light_tree = True
scene.cycles.use_fast_gi = False
scene.render.use_persistent_data = True
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.resolution_percentage = RES_PCT
scene.render.film_transparent = False
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.color_depth = '8'
scene.render.image_settings.compression = 15
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
scene.view_settings.exposure = 0.35          # sunny, brighter overall

# ---------------------------------------------------------------- world : gradient sky
world = bpy.data.worlds.new('Sky')
scene.world = world
world.use_nodes = True
wnt = world.node_tree
wnt.nodes.clear()
w_out = wnt.nodes.new('ShaderNodeOutputWorld')
w_bg = wnt.nodes.new('ShaderNodeBackground')
w_geo = wnt.nodes.new('ShaderNodeNewGeometry')
w_sep = wnt.nodes.new('ShaderNodeSeparateXYZ')
w_abs = wnt.nodes.new('ShaderNodeVectorMath')
w_abs.operation = 'ABSOLUTE'
w_ramp = wnt.nodes.new('ShaderNodeValToRGB')
w_ramp.color_ramp.elements[0].position = 0.0
w_ramp.color_ramp.elements[0].color = (0.72, 0.82, 0.90, 1.0)     # pale horizon haze
w_ramp.color_ramp.elements[1].position = 1.0
w_ramp.color_ramp.elements[1].color = (0.06, 0.18, 0.60, 1.0)     # deep sky blue
e = w_ramp.color_ramp.elements.new(0.09)
e.color = (0.44, 0.62, 0.89, 1.0)
e = w_ramp.color_ramp.elements.new(0.26)
e.color = (0.17, 0.37, 0.78, 1.0)
e = w_ramp.color_ramp.elements.new(0.60)
e.color = (0.09, 0.24, 0.66, 1.0)
w_bg.inputs['Strength'].default_value = 1.45   # stronger sky ambient -> softer, non-black shadows
wnt.links.new(w_geo.outputs['Incoming'], w_abs.inputs[0])
wnt.links.new(w_abs.outputs['Vector'], w_sep.inputs['Vector'])
wnt.links.new(w_sep.outputs['Z'], w_ramp.inputs['Fac'])
wnt.links.new(w_ramp.outputs['Color'], w_bg.inputs['Color'])
wnt.links.new(w_bg.outputs['Background'], w_out.inputs['Surface'])
# (Alternative allowed by the brief: ShaderNodeTexSky with sky_type='NISHITA',
#  sun_disc=False, sun_elevation ~40 deg.  A gradient is used here because it is
#  much cheaper to sample on CPU and gives predictable postcard colours.)

# ---------------------------------------------------------------- 1. terrain
NW = 160
SPAN = 120.0
sp = SPAN / (NW - 1)
t_verts = []
for j in range(NW):
    yy = -60.0 + j * sp
    for i in range(NW):
        xx = -60.0 + i * sp
        t_verts.append((xx, yy, h(xx, yy)))
t_faces = []
for j in range(NW - 1):
    for i in range(NW - 1):
        a = j * NW + i
        t_faces.append((a, a + 1, a + NW + 1, a + NW))

terrain_mat = bpy.data.materials.new('MeadowGrass')
terrain_mat.use_nodes = True
tnt = terrain_mat.node_tree
tbsdf = tnt.nodes['Principled BSDF']
tbsdf.inputs['Roughness'].default_value = 0.9
tnoise = tnt.nodes.new('ShaderNodeTexNoise')
tnoise.inputs['Scale'].default_value = 4.5
tnoise.inputs['Detail'].default_value = 4.0
tnoise.inputs['Roughness'].default_value = 0.55
tramp = tnt.nodes.new('ShaderNodeValToRGB')
tramp.color_ramp.elements[0].position = 0.28
tramp.color_ramp.elements[0].color = (0.080, 0.185, 0.038, 1.0)   # slightly darker patch
tramp.color_ramp.elements[1].position = 0.76
tramp.color_ramp.elements[1].color = (0.345, 0.535, 0.125, 1.0)   # light yellow-green
tme = tramp.color_ramp.elements.new(0.53)
tme.color = (0.195, 0.395, 0.080, 1.0)                            # fresh spring green
tnt.links.new(tnoise.outputs['Fac'], tramp.inputs['Fac'])
tnt.links.new(tramp.outputs['Color'], tbsdf.inputs['Base Color'])
terrain = mesh_object('Terrain', t_verts, t_faces, COLL_MODEL, mats=[terrain_mat])

# ---------------------------------------------------------------- 2. distant hills + far ground
FARZ = -8.0
# The far ground is tilted so its distant edge sits only ~0.3 deg below the horizon:
# from the camera it always fills the band *behind* the meadow edge, so no seam shows.
far_mat = make_emission('FarGroundMat', (0.31, 0.42, 0.29))
far_plane = mesh_object('FarGround',
                        [(-400.0, 56.0, -2.0), (400.0, 56.0, -2.0),
                         (400.0, 420.0, -0.35), (-400.0, 420.0, -0.35)],
                        [(0, 1, 2, 3)], COLL_MODEL, mats=[far_mat])
far_plane.visible_shadow = False

HILL_LAYERS = (
    (70.0, 3.0, 3.5, 0.030, 0.071, (0.225, 0.350, 0.150)),   # near : fresh green
    (105.0, 6.0, 5.0, 0.021, 0.049, (0.380, 0.490, 0.390)),  # mid  : pale green-grey
    (150.0, 9.0, 6.5, 0.015, 0.036, (0.560, 0.660, 0.760)),  # far  : pale blue
)
for li, (hy, base, amp, f1, f2, col) in enumerate(HILL_LAYERS):
    hm = make_emission('HillMat_%d' % li, col)
    segs = 120
    x0, x1 = -320.0, 320.0
    verts = []
    faces = []
    for k in range(segs + 1):
        xk = x0 + (x1 - x0) * k / segs
        zt = base + amp * (0.62 * math.sin(xk * f1 + li * 1.7)
                           + 0.38 * math.sin(xk * f2 + li * 0.9 + 2.0)
                           + 0.22 * math.cos(xk * 0.011 - li))
        verts.append((xk, hy, FARZ))
        verts.append((xk, hy, zt))
    for k in range(segs):
        a = k * 2
        faces.append((a, a + 1, a + 3, a + 2))
    hob = mesh_object('DistantHills_%d' % li, verts, faces, COLL_MODEL, mats=[hm])
    hob.visible_shadow = False

# ---------------------------------------------------------------- materials for flora
grass_mat = bpy.data.materials.new('GrassBlade')
grass_mat.use_nodes = True
gnt = grass_mat.node_tree
gbsdf = gnt.nodes['Principled BSDF']
gbsdf.inputs['Roughness'].default_value = 0.75
gattr = gnt.nodes.new('ShaderNodeAttribute')
gattr.attribute_name = 'Col'
gnt.links.new(gattr.outputs['Color'], gbsdf.inputs['Base Color'])

stem_mat = make_principled('FlowerStem', (0.10, 0.26, 0.045), 0.8)
petal_mats = [
    make_principled('PetalWhite', (0.96, 0.96, 0.91), 0.55),
    make_principled('PetalYellow', (1.00, 0.86, 0.06), 0.55),
    make_principled('PetalPink', (0.97, 0.32, 0.56), 0.55),
    make_principled('PetalPurple', (0.64, 0.44, 0.95), 0.55),
    make_principled('PetalOrange', (1.00, 0.46, 0.06), 0.55),
]
trunk_mat = make_principled('TrunkBark', (0.140, 0.078, 0.042), 0.95)
leaf_mat = make_principled('TreeFoliage', (0.075, 0.230, 0.055), 0.85)
cloud_mat = make_principled('CloudPuff', (0.82, 0.85, 0.90), 1.0)

# ---------------------------------------------------------------- 3. trees
TREE_SPOTS = (
    (-19.0, -12.0, 1.30), (22.0, -8.0, 1.20),          # two big framing trees, sides of the view
    (-22.0, 18.0, 1.15), (26.0, 22.0, 1.05),
    (-34.0, 40.0, 0.95), (14.0, 42.0, 0.80), (-6.0, 30.0, 0.70),
)
for ti, (tx, ty, tsc) in enumerate(TREE_SPOTS):
    bm = bmesh.new()
    tz = h(tx, ty)
    trunk_h = 3.0 * tsc
    add_cone(bm, 7, 0.30 * tsc, 0.16 * tsc, trunk_h,
             Matrix.Translation(Vector((tx, ty, tz + trunk_h * 0.5))))
    n_trunk = len(bm.faces)
    blobs = random.randint(3, 5)
    for b in range(blobs):
        r = random.uniform(1.5, 2.6) * tsc
        bx = tx + random.uniform(-1.2, 1.2) * tsc
        by = ty + random.uniform(-1.2, 1.2) * tsc
        bz = tz + trunk_h * random.uniform(0.80, 1.25) + r * 0.45
        mat = (Matrix.Translation(Vector((bx, by, bz)))
               @ Matrix.Diagonal(Vector((r, r, r * random.uniform(0.70, 0.95), 1.0))))
        add_icosphere(bm, 2, 1.0, mat)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new('Tree_%02d' % ti)
    bm.faces.ensure_lookup_table()
    for fi, f in enumerate(bm.faces):
        f.material_index = 0 if fi < n_trunk else 1
    bm.to_mesh(me)
    bm.free()
    me.materials.append(trunk_mat)
    me.materials.append(leaf_mat)
    for fi, p in enumerate(me.polygons):
        if p.material_index == 1:
            p.use_smooth = True
    ob = bpy.data.objects.new('Tree_%02d' % ti, me)
    COLL_MODEL.objects.link(ob)

# ---------------------------------------------------------------- 4. grass (merged patches)
# per-blade colour ramp (linear values): green base -> light yellow-green tip
GBASE = (0.060, 0.170, 0.032)
GTIP = (0.520, 0.645, 0.135)

density = []
for iy in range(NY):
    yc = GY0 + (iy + 0.5) * CH
    density.append(math.exp(-max(0.0, yc + 44.0) / 20.0))
row_sum = sum(density) * NX
counts = [[max(8, int(TOTAL_BLADES * density[iy] / (row_sum * TUFT_AVG))) for ix in range(NX)]
          for iy in range(NY)]

blade_total = 0
patch_objs = []
for iy in range(NY):
    for ix in range(NX):
        cy0 = GY0 + iy * CH
        cx0 = GX0 + ix * CW
        verts = []
        faces = []
        cols = []
        wts = []
        for _k in range(counts[iy][ix]):
            ntuft = random.randint(1, 2)
            bx = cx0 + random.random() * CW
            by = cy0 + random.random() * CH
            bz = h(bx, by) - 0.02
            tint = random.uniform(0.82, 1.15)
            tgr = random.uniform(-0.03, 0.03)
            for _b in range(ntuft):
                x = bx + random.uniform(-0.10, 0.10)
                y = by + random.uniform(-0.10, 0.10)
                z = h(x, y) - 0.02
                hh = random.uniform(0.22, 0.48)
                wid = random.uniform(0.024, 0.034)
                theta = random.uniform(0.0, math.pi)
                bend = hh * random.uniform(0.10, 0.32)
                ux, uy = math.cos(theta), math.sin(theta)
                i0 = len(verts)
                for t, wf in ((0.0, 1.0), (0.52, 0.60), (1.0, 0.0)):
                    cz = z + hh * t
                    cxx = x + WIND.x * bend * (t * t)
                    cyy = y + WIND.y * bend * (t * t)
                    f = t
                    cr = (GBASE[0] + (GTIP[0] - GBASE[0]) * f) * tint + tgr
                    cg = (GBASE[1] + (GTIP[1] - GBASE[1]) * f) * tint
                    cb = (GBASE[2] + (GTIP[2] - GBASE[2]) * f) * tint
                    w = t ** 1.4
                    if wf > 0.0:
                        hw = 0.5 * wid * wf
                        verts.append((cxx - ux * hw, cyy - uy * hw, cz))
                        verts.append((cxx + ux * hw, cyy + uy * hw, cz))
                        cols.append((cr, cg, cb))
                        cols.append((cr, cg, cb))
                        wts.append(w)
                        wts.append(w)
                    else:
                        verts.append((cxx, cyy, cz))
                        cols.append((cr, cg, cb))
                        wts.append(w)
                faces.append((i0, i0 + 1, i0 + 3, i0 + 2))
                faces.append((i0 + 2, i0 + 3, i0 + 4))
            blade_total += ntuft

        pname = 'GrassPatch_r%dc%d' % (iy, ix)
        if verts:
            pob = mesh_object(pname, verts, faces, COLL_MODEL, mats=[grass_mat], colors=cols)
            add_shape_key_pair(pob, verts, wts, SWAY_AMP)
            phase = 2.0 * math.pi * (0.13 * ix + 0.29 * iy)
            animate_sway(pob, phase)
            patch_objs.append(pob)
        else:
            pob = mesh_object(pname, [], [], COLL_MODEL, mats=[grass_mat])
            patch_objs.append(pob)

# ---------------------------------------------------------------- 5. flowers
f_verts = []
f_faces = []
f_mat = []
f_wts = []
nflowers = 0
while nflowers < FLOWER_TARGET:
    ccy = -46.0 + (random.random() ** 1.4) * 54.0        # clusters biased to the foreground / camera path
    half_w = 0.62 * (ccy + 48.0) + 6.0                   # keep flowers inside the view cone
    ccx = random.uniform(-half_w, half_w)
    for _f in range(random.randint(4, 9)):
        if nflowers >= FLOWER_TARGET:
            break
        fx = ccx + random.gauss(0.0, 1.2)
        fy = ccy + random.gauss(0.0, 1.2)
        if not (GX0 + 4.0 < fx < GX1 - 4.0 and GY0 + 4.0 < fy < GY1 - 4.0):
            continue
        nflowers += 1
        fz = h(fx, fy)
        hh = random.uniform(0.26, 0.50)                  # 26-50 cm stems -> heads above the grass tips
        ang = random.uniform(0.0, 2.0 * math.pi)
        tilt = random.uniform(-0.14, 0.14)
        dx = math.cos(ang) * tilt * hh
        dy = math.sin(ang) * tilt * hh
        ux, uy = math.cos(ang), math.sin(ang)
        sw = 0.014
        i0 = len(f_verts)
        f_verts.append((fx - ux * sw, fy - uy * sw, fz))
        f_verts.append((fx + ux * sw, fy + uy * sw, fz))
        f_verts.append((fx + dx + ux * sw * 0.7, fy + dy + uy * sw * 0.7, fz + hh))
        f_verts.append((fx + dx - ux * sw * 0.7, fy + dy - uy * sw * 0.7, fz + hh))
        f_wts.extend((0.0, 0.0, 1.0, 1.0))
        f_faces.append((i0, i0 + 1, i0 + 2, i0 + 3))
        f_mat.append(0)
        # pentagon head (~14-20 cm across), tilted up AND toward the camera so it reads
        # as a face rather than an edge-on sliver from the low forward-looking camera
        r = random.uniform(0.070, 0.100)
        a_up = random.uniform(0.55, 0.95)                # tilt away from vertical
        yawh = random.uniform(-0.7, 0.7)
        nrm = Vector((math.sin(yawh) * math.sin(a_up),
                      -math.cos(yawh) * math.sin(a_up),
                      math.cos(a_up))).normalized()
        b1 = Vector((ux, uy, 0.0))
        b1 = b1 - nrm * b1.dot(nrm)
        if b1.length < 1e-4:
            b1 = Vector((1.0, 0.0, 0.0))
        b1.normalize()
        b2 = nrm.cross(b1).normalized()
        center = Vector((fx + dx, fy + dy, fz + hh)) + nrm * 0.006
        o0 = len(f_verts)
        rot0 = random.random()
        for k in range(5):
            a2 = 2.0 * math.pi * k / 5.0 + rot0
            p = center + b1 * (r * math.cos(a2)) + b2 * (r * math.sin(a2))
            f_verts.append((p.x, p.y, p.z))
            f_wts.append(1.0)
        f_verts.append((center.x, center.y, center.z))
        f_wts.append(1.0)
        pmid = 1 + random.choice((0, 0, 0, 1, 1, 2, 2, 3, 3, 4))
        for k in range(5):
            f_faces.append((o0 + k, o0 + (k + 1) % 5, o0 + 5))
            f_mat.append(pmid)

flowers = mesh_object('Flowers', f_verts, f_faces, COLL_MODEL,
                      mats=[stem_mat] + petal_mats)
for i, p in enumerate(flowers.data.polygons):
    p.material_index = f_mat[i]
add_shape_key_pair(flowers, f_verts, f_wts, 0.070)
animate_sway(flowers, 0.7)

# ---------------------------------------------------------------- 6. clouds
cloud_objs = []
for ci in range(12):
    cx = random.uniform(-150.0, 150.0)
    cy = random.uniform(150.0, 380.0)
    cz = random.uniform(34.0, 66.0)                      # a little lower -> well visible
    bm = bmesh.new()
    nsph = random.randint(7, 11)                         # fluffier: more spheres
    for _s in range(nsph):
        r = random.uniform(11.0, 22.0)                   # ~1.5-2x bigger
        ox = random.uniform(-30.0, 30.0)
        oy = random.uniform(-13.0, 13.0)
        oz = random.uniform(-1.5, 6.0)
        flat = r * random.uniform(0.30, 0.44)            # flatter bottoms
        mat = (Matrix.Translation(Vector((cx + ox, cy + oy, cz + oz)))
               @ Matrix.Diagonal(Vector((r, r * random.uniform(0.8, 1.15), flat, 1.0))))
        add_icosphere(bm, 2, 1.0, mat)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new('Cloud_%02d' % ci)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(cloud_mat)
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new('Cloud_%02d' % ci, me)
    COLL_MODEL.objects.link(ob)
    ob.visible_shadow = False
    ob.keyframe_insert(data_path='location', frame=1)
    ob.location.x += 26.0                                # visible drift (~26 m over the clip)
    ob.keyframe_insert(data_path='location', frame=PERIOD + 1)
    ob.location.x -= 26.0
    cloud_objs.append(ob)

# ---------------------------------------------------------------- 7. sun light
sun_data = bpy.data.lights.new('Sun', type='SUN')
sun_data.energy = 2.8
sun_data.color = (1.0, 0.96, 0.88)
sun_data.angle = math.radians(5.0)          # soft shadow penumbra
sun = bpy.data.objects.new('Sun', sun_data)
COLL_LIGHTS.objects.link(sun)
sun.rotation_mode = 'QUATERNION'
sun_dir = Vector((40.0, 60.0, -50.0)).normalized()
sun.rotation_quaternion = sun_dir.to_track_quat('-Z', 'Y')
# neutral warm white -> clearly golden-peach -> back (loops at frame 193)
for fr, col, en in ((1, (1.00, 0.96, 0.88), 2.8),
                    (PERIOD // 2, (1.00, 0.70, 0.42), 3.5),
                    (PERIOD + 1, (1.00, 0.96, 0.88), 2.8)):
    sun_data.color = col
    sun_data.energy = en
    sun_data.keyframe_insert(data_path='color', frame=fr)
    sun_data.keyframe_insert(data_path='energy', frame=fr)

# ---------------------------------------------------------------- 8. camera
cam_data = bpy.data.cameras.new('Camera')
cam_data.lens = 30.0
cam_data.sensor_width = 36.0
cam = bpy.data.objects.new('Camera', cam_data)
COLL_CAMERA.objects.link(cam)
scene.camera = cam
cam.rotation_mode = 'QUATERNION'


def cam_quat(yaw, pitch):
    """Look mostly toward +Y with a gentle yaw and slight downward pitch."""
    d = Vector((math.sin(yaw), math.cos(yaw), pitch)).normalized()
    return d.to_track_quat('-Z', 'Y')


CAMY = -48.0
CAMZ = h(0.0, CAMY) + 1.62
# calm forward walk (~9.2 m) with a slight pan (±1.8 deg) and a small bob
cam_key = ((1,            (0.00, CAMY + 0.0, CAMZ),        0.0,                  -0.065),
           (48,           (0.25, CAMY + 2.4, CAMZ + 0.05), math.radians(1.8),    -0.055),
           (96,           (0.00, CAMY + 4.6, CAMZ),        0.0,                  -0.065),
           (144,          (-0.25, CAMY + 6.9, CAMZ + 0.05), math.radians(-1.8),  -0.055),
           (PERIOD + 1,   (0.00, CAMY + 9.2, CAMZ),        0.0,                  -0.065))
for fr, loc, yaw, pitch in cam_key:
    cam.location = loc
    cam.rotation_quaternion = cam_quat(yaw, pitch)
    cam.keyframe_insert(data_path='location', frame=fr)
    cam.keyframe_insert(data_path='rotation_quaternion', frame=fr)

# ---------------------------------------------------------------- linear interpolation everywhere
for act in bpy.data.actions:
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'

# ---------------------------------------------------------------- save + outputs
bpy.context.view_layer.update()
scene.frame_set(1)
build_seconds = os.times().elapsed - T_ZERO
print('BUILD_SECONDS=%.2f' % build_seconds)

# stats
scene.view_layers[0].update()
tris = 0
for ob in COLL_MODEL.objects:
    if ob.type == 'MESH':
        ob.data.calc_loop_triangles()
        tris += len(ob.data.loop_triangles)
print('TRIANGLES=%d  BLADES=%d  FLOWERS=%d  OBJECTS=%d'
      % (tris, blade_total, nflowers, len(bpy.data.objects)))

if MODE == 'anim':
    scene.render.filepath = os.path.join(ANIM_DIR, 'frame_')
else:
    scene.render.filepath = STILL_PATH

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(D, 'grassland.blend'))

if MODE == 'anim':
    scene.frame_start = FSTART
    scene.frame_end = FEND
    scene.frame_set(FSTART)
    r0 = os.times().elapsed
    bpy.ops.render.render(animation=True)
    print('RENDER_SECONDS=%.2f' % (os.times().elapsed - r0))
else:
    try:
        bpy.ops.export_scene.gltf(
            filepath=os.path.join(EXPORT_DIR, 'grassland.glb'),
            export_format='GLB', use_selection=False, export_apply=False,
            export_animations=True, export_morph=True, export_morph_animation=True,
            export_cameras=True)
    except TypeError:
        try:
            bpy.ops.export_scene.gltf(
                filepath=os.path.join(EXPORT_DIR, 'grassland.glb'),
                export_format='GLB', use_selection=False, export_apply=False,
                export_animations=True, export_morph=True, export_cameras=True)
        except Exception as exc:                                # never crash the run
            print('GLB_EXPORT_ERROR=%s' % exc)
    except Exception as exc:
        print('GLB_EXPORT_ERROR=%s' % exc)

    scene.frame_set(STILL_FRAME)
    r0 = os.times().elapsed
    bpy.ops.render.render(write_still=True)
    print('RENDER_SECONDS=%.2f' % (os.times().elapsed - r0))

print('DONE mode=%s' % (MODE or 'still'))
