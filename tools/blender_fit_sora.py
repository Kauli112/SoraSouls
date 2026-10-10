"""SoraSouls – Step 2a: put Sora's mesh on the DSR player skeleton inside Blender.

Run headless (see tools/run_fit_sora.bat) or from Blender's Scripting tab.
Inputs  (paths relative to the project root E:/SoraSouls):
  work/sora/P_EX100.fbx            – exported with OpenKH Kh2MdlxEditor
  data/bone_map_sora.json          – Sora bone index -> DSR bone name
  work/dsr_c0000_skeleton.json     – DSR c0000 bone world transforms (from your own game files)
Outputs:
  work/sora/sora_dsr_fit_v3.blend  – Sora mesh skinned to a DSR armature (rest pose)
  work/sora/posed_front.png, posed_side.png – deformation test (arms down, elbows, knee, twist)
  work/sora/preview_front.png, preview_side.png – renders with DSR joints as red dots
  work/sora/fit_report.txt

Coordinate conventions (verified 2026-10-04 from file data):
  Sora FBX: Y-up, centimetres, faces +Z.   DSR: Y-up, metres, faces -Z, L_ bones on +X.
  Sora (x,y,z) -> DSR (s*x, s*y, -s*z + tz), s = 0.01085, tz = -0.0602 (least-squares fit of 14 joints,
  feet kept on the ground; v1 used s = 0.01053 with no offset and sat ~6 cm behind the skeleton).
  DSR (X,Y,Z) -> Blender (X, Z, Y)  (same Y/Z swap soulstruct-blender uses).
"""
import bpy, json, os, sys, math
from mathutils import Matrix, Vector

ROOT = os.environ.get("SORASOULS_ROOT", "E:/SoraSouls")
FBX = os.path.join(ROOT, "work/sora/P_EX100.fbx")
BONE_MAP = os.path.join(ROOT, "data/bone_map_sora.json")
SKELETON = os.path.join(ROOT, "work/dsr_c0000_skeleton.json")
OUT_DIR = os.path.join(ROOT, "work/sora")
SCALE = 0.01085
OFFSET_DSR_Z = -0.0602  # metres, DSR space (Blender Y)
report = []

def log(msg):
    print("[SoraSouls]", msg); report.append(msg)

def dsr_to_blender(v):
    return Vector((v[0], v[2], v[1]))

# --- 1. clean scene and import --------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=FBX, use_anim=False, ignore_leaf_bones=False,
                         automatic_bone_orientation=False)
# OpenKH writes texture paths without ".png" -> point images at the real files.
for img in bpy.data.images:
    base = os.path.splitext(os.path.basename(bpy.path.abspath(img.filepath)))[0] or img.name
    png = os.path.join(os.path.dirname(FBX), os.path.splitext(base)[0] + ".png")
    if os.path.exists(png):
        img.filepath = png; img.reload()
    log(f"image {img.name}: {'OK ' + os.path.basename(png) if os.path.exists(png) else 'MISSING'}")
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
kh_arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
log(f"imported {len(meshes)} meshes, {len(kh_arms)} armature(s), "
    f"{sum(len(m.data.vertices) for m in meshes)} vertices")

bmap = {int(k): v["dsr"] for k, v in json.load(open(BONE_MAP))["bones"].items()}
skel = json.load(open(SKELETON))

# --- 2. bake transforms, rescale, merge vertex groups -----------------------------------------
# Importer gives Sora in Blender space at 0.01 (cm->m). Extra factor turns it into DSR scale.
k = SCALE / 0.01
for ob in meshes:
    mw = ob.matrix_world.copy()
    ob.parent = None
    for mod in list(ob.modifiers):
        ob.modifiers.remove(mod)
    ob.data.transform(Matrix.Translation((0, OFFSET_DSR_Z, 0)) @ Matrix.Scale(k, 4) @ mw)
    ob.matrix_world = Matrix.Identity(4)

    weights = {}  # vertex index -> {dsr bone: weight}
    unknown = set()
    names = {g.index: g.name for g in ob.vertex_groups}
    for v in ob.data.vertices:
        for g in v.groups:
            name = names[g.group]
            try:
                dsr = bmap[int(name.replace("Bone", ""))]
            except (ValueError, KeyError):
                unknown.add(name); continue
            weights.setdefault(v.index, {}).setdefault(dsr, 0.0)
            weights[v.index][dsr] += g.weight
    ob.vertex_groups.clear()
    groups = {}
    for vi, wd in weights.items():
        total = sum(wd.values()) or 1.0
        for dsr, w in wd.items():
            if dsr not in groups:
                groups[dsr] = ob.vertex_groups.new(name=dsr)
            groups[dsr].add([vi], w / total, "REPLACE")
    unweighted = len(ob.data.vertices) - len(weights)
    log(f"{ob.name}: {len(groups)} DSR groups, unweighted verts={unweighted}, unknown groups={sorted(unknown)}")

for a in kh_arms:
    bpy.data.objects.remove(a, do_unlink=True)

# --- 3. build DSR armature ----------------------------------------------------------------------
arm_data = bpy.data.armatures.new("c0000")
arm = bpy.data.objects.new("c0000", arm_data)
bpy.context.scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
ebones = []
for b in skel:
    eb = arm_data.edit_bones.new(b["name"])
    head = dsr_to_blender(b["head"])
    axis = dsr_to_blender([row[0] for row in b["rot"]])  # bone local X
    eb.head, eb.tail = head, head + axis.normalized() * 0.05
    ebones.append(eb)
for b, eb in zip(skel, ebones):
    if b["parent"] >= 0:
        eb.parent = ebones[b["parent"]]
bpy.ops.object.mode_set(mode="OBJECT")
arm.show_in_front = True

for ob in meshes:
    ob.parent = arm
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm

# --- 4. checks ----------------------------------------------------------------------------------
heads = {b["name"]: dsr_to_blender(b["head"]) for b in skel}
def group_centroid(name):
    pts = []
    for ob in meshes:
        g = ob.vertex_groups.get(name)
        if not g: continue
        for v in ob.data.vertices:
            if any(x.group == g.index and x.weight > 0.5 for x in v.groups):
                pts.append(v.co)
    return sum(pts, Vector()) / len(pts) if pts else None

for name in ("L_Hand", "R_Hand", "L_Foot", "R_Foot", "Head"):
    c = group_centroid(name)
    if c is None:
        log(f"CHECK {name}: no vertices"); continue
    side_ok = (name.startswith("L_") and c.x > 0) or (name.startswith("R_") and c.x < 0) or name == "Head"
    log(f"CHECK {name}: verts centre {tuple(round(x,3) for x in c)} | DSR joint "
        f"{tuple(round(x,3) for x in heads[name])} | dist {round((c-heads[name]).length,3)} m | side {'OK' if side_ok else 'WRONG'}")
zs = [(ob.matrix_world @ v.co).z for ob in meshes for v in ob.data.vertices]
log(f"height: feet {round(min(zs),3)} m, top {round(max(zs),3)} m")

# --- 5. preview renders (DSR joints as red dots) -----------------------------------------------
dot_mat = bpy.data.materials.new("joint"); dot_mat.diffuse_color = (1, 0, 0, 1)
for n in ("Pelvis", "L_Thigh", "R_Thigh", "L_Calf", "R_Calf", "L_Foot", "R_Foot", "Spine1", "Neck",
          "Head", "L_UpperArm", "R_UpperArm", "L_Forearm", "R_Forearm", "L_Hand", "R_Hand"):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.018, location=heads[n])
    d = bpy.context.active_object; d.name = "joint_" + n; d.data.materials.append(dot_mat)
    d.show_in_front = True

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "FLAT"
scene.display.shading.color_type = "TEXTURE"
scene.display.shading.show_xray = True
scene.display.shading.xray_alpha = 0.6
scene.render.resolution_x, scene.render.resolution_y = 900, 1100
cam_data = bpy.data.cameras.new("cam"); cam_data.type = "ORTHO"; cam_data.ortho_scale = 2.1
cam = bpy.data.objects.new("cam", cam_data); scene.collection.objects.link(cam); scene.camera = cam
VIEWS = (("front", (0, -4, 0.95), (math.radians(90), 0, 0)),
         ("side", (4, 0, 0.95), (math.radians(90), 0, math.radians(90))))
def render(prefix):
    for label, loc, rot in VIEWS:
        cam.location, cam.rotation_euler = loc, rot
        scene.render.filepath = os.path.join(OUT_DIR, f"{prefix}_{label}.png")
        bpy.ops.render.render(write_still=True)
        log(f"rendered {scene.render.filepath}")

render("preview")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_DIR, "sora_dsr_fit_v3.blend"))
log("saved sora_dsr_fit_v3.blend (rest pose)")

# --- 6. deformation test: bend the DSR skeleton like an animation would ------------------------
for d in [o for o in scene.objects if o.name.startswith("joint_")]:
    d.hide_render = True  # dots don't follow the pose
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="POSE")
def rotate(bone, axis, degrees):
    pb = arm.pose.bones[bone]
    head = pb.head.copy()
    pb.matrix = (Matrix.Translation(head) @ Matrix.Rotation(math.radians(degrees), 4, axis)
                 @ Matrix.Translation(-head) @ pb.matrix)
    bpy.context.view_layer.update()
POSE = [("L_UpperArm", "Y", 70), ("R_UpperArm", "Y", -70),    # arms down
        ("L_Forearm", "X", -60), ("R_Forearm", "X", -60),      # elbows bent forward
        ("L_Thigh", "X", -40), ("L_Calf", "X", 70),            # left leg: step + knee bend
        ("Spine1", "Z", 20), ("Head", "X", -15)]               # twist torso, nod
for bone, axis, deg in POSE:
    rotate(bone, axis, deg)
bpy.ops.object.mode_set(mode="OBJECT")
scene.display.shading.show_xray = False  # opaque, so overlapping limbs read clearly
render("posed")
# close-ups of the joints whose positions differ most between Sora and DSR
cam_data.ortho_scale = 0.75
VIEWS = (("knee_side", (4, 0, 0.55), (math.radians(90), 0, math.radians(90))),
         ("elbow_side", (4, 0, 1.15), (math.radians(90), 0, math.radians(90))))
render("closeup")
open(os.path.join(OUT_DIR, "fit_report.txt"), "w").write("\n".join(report))
