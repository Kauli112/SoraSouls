"""SoraSouls – Donald's staff and Goofy's shield from the user's OpenKH exports (v111). No Blender.

  W_EX020.fbx (Mage's Staff) -> WP_A_0298, built on the user's Sorcerer's Catalyst part WP_A_0910 (Donald's current
                                catalyst), so layout, bones, dummies and material match a catalyst the game accepts.
  W_EX030.fbx (Knight's Shield) -> WP_A_0299, built on the user's Tower Shield part WP_A_1505 (Goofy's current shield).

Geometry: the whole KH2 mesh (both exports: one mesh skinned to Bone0003), uniform size = the character's K / 100 (the
size factor the body uses: Donald 1.35, Goofy 0.914), grip = Bone0000.
  staff:  game = s * R (kh - grip), R = the Keyblade axes (KH2 +Z -> game -Y = the weapon's forward axis, as the
          Kingdom Key; the hat is the forward end). Dummies 100/130/206 (tip / mid / hit points) scaled to the new tip.
  shield: the handle bar (KH2 Z) -> game Y (the grip axis through the fist), the outer face (KH2 -Y) -> the side the
          Tower Shield's plate sits on (game Z sign measured from the template), KH2 X -> game X. Guard/hit dummies are
          scaled to the new plate.
Normals: area-weighted face normals averaged within 45 deg (make_keyblades.geometry style); tangents from UVs.
Faces are drawn from both sides (KH2 models are partly single-sided), as for the Keyblades.
Texture: the export's Texture0000.png (saved as W_EX0x0_Texture0000.png) -> DXT5 into the template's TPF under the
template's own diffuse name; the normal map is replaced with a flat one and the specular with a dull grey, since the
vanilla maps follow the vanilla UVs.
Usage: python make_party_weapons.py <dir with donald/ and goofy/ exports> <game parts dir> <out parts dir>
"""
import io, os, sys
import numpy as np
from PIL import Image
from soulstruct.containers import Binder
from soulstruct.containers.tpf import TPF
from soulstruct.flver import FLVER

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kh_fbx
from fix_sora_normalmap import flat_dxt1

R_STAFF = np.array([[1, 0, 0], [0, 0, -1], [0, -1, 0]], float)   # make_keyblades.R
SMOOTH_DEG = 45.0
WEAPONS = [
    dict(key="staff", who="donald", fbx="W_EX020", template=910, model=298, scale=1.35 / 100, kind="staff"),
    dict(key="shield", who="goofy", fbx="W_EX030", template=1505, model=299, scale=0.914 / 100, kind="shield"),
]


def load(fbx):
    d = kh_fbx.load(fbx)
    grip = next(b["glob"][:3, 3] for b in d["bones"].values() if b["name"] == "Bone0000")
    m = d["meshes"][0]
    tris = [((m["V"][a], m["V"][b], m["V"][c]), uv) for a, b, c, uv, tex in m["tris"]]
    return grip, tris


def transform(w, grip, tris, frontZ):
    if w["kind"] == "staff":
        M = R_STAFF
    else:
        M = np.array([[1, 0, 0], [0, 0, 1], [0, -frontZ, 0]], float)
    pos = np.array([[(p - grip) @ M.T * w["scale"] for p in t[0]] for t in tris])
    uv = np.array([[(u[0], 1.0 - u[1]) for u in t[1]] for t in tris])
    if np.linalg.det(M) > 0:                 # keep the Keyblade's handedness convention (its R has det -1)
        pos, uv = pos[:, [0, 2, 1]], uv[:, [0, 2, 1]]
    return pos, uv


def normals_tangents(pos, uv):
    fn = np.cross(pos[:, 2] - pos[:, 0], pos[:, 1] - pos[:, 0])
    P, U = pos.reshape(-1, 3), uv.reshape(-1, 2)
    keys = [tuple(np.round(p, 5)) for p in P]
    acc = {}
    for i, k in enumerate(keys):
        acc.setdefault(k, []).append(fn[i // 3])
    cl = np.cos(np.radians(SMOOTH_DEG))
    nrm = np.zeros((len(P), 3))
    for i, k in enumerate(keys):
        own = fn[i // 3]; ou = own / (np.linalg.norm(own) + 1e-12)
        s = sum((f for f in acc[k] if np.dot(f / (np.linalg.norm(f) + 1e-12), ou) >= cl), np.zeros(3))
        nrm[i] = s / np.linalg.norm(s) if np.linalg.norm(s) > 1e-12 else ou
    tan = np.zeros((len(P), 4))
    for t in range(len(pos)):
        i0, i1, i2 = 3 * t, 3 * t + 1, 3 * t + 2
        e1, e2 = P[i1] - P[i0], P[i2] - P[i0]
        d1, d2 = U[i1] - U[i0], U[i2] - U[i0]
        det = d1[0] * d2[1] - d2[0] * d1[1]
        T = (e1 * d2[1] - e2 * d1[1]) / det if abs(det) > 1e-12 else np.array([1.0, 0, 0])
        B = (e2 * d1[0] - e1 * d2[0]) / det if abs(det) > 1e-12 else np.array([0, 1.0, 0])
        for i in (i0, i1, i2):
            n = nrm[i]; tt = T - n * np.dot(n, T)
            if np.linalg.norm(tt) < 1e-9:
                tt = np.cross(n, [0, 1, 0]) if abs(n[1]) < 0.9 else np.cross(n, [1, 0, 0])
            tt /= np.linalg.norm(tt)
            s = 1.0 if np.dot(np.cross(n, tt), B) >= 0 else -1.0
            tan[i] = (*(np.cross(n, tt) * s), -s)
    return P, nrm, tan, U


def dxt(img, fmt):
    buf = io.BytesIO(); img.save(buf, "DDS", pixel_format=fmt)
    return buf.getvalue()


def build(w, src, game_parts, out_dir):
    tstem, stem = f"WP_A_{w['template']:04d}", f"WP_A_{w['model']:04d}"
    b = Binder.from_path(os.path.join(game_parts, tstem + ".partsbnd.dcx"))
    fe = next(e for e in b.entries if e.path.endswith(".flver"))
    te = next(e for e in b.entries if e.path.endswith(".tpf"))
    f = FLVER.from_bytes(fe.data)
    m = f.meshes[0]
    old = m.vertices["position"].copy()
    frontZ = float(np.sign(old[:, 2].mean())) or -1.0       # side of the grip the shield plate sits on
    grip, tris = load(os.path.join(src, w["who"], w["fbx"] + ".fbx"))
    pos, uv = transform(w, grip, tris, frontZ)
    P, N, T, U = normals_tangents(pos, uv)
    key = np.round(np.hstack([P, N, U, T[:, 3:]]), 5)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    v = np.zeros(len(first), dtype=m.vertices.dtype)
    v["position"], v["normal"], v["tangent_0"], v["uv_0"] = P[first], N[first], T[first], U[first]
    v["normal_w"], v["bone_indices"], v["color_0"] = 127, 0, 1.0
    m.vertex_arrays[0].array = v
    m.face_sets[0].vertex_indices = inv.reshape(-1).reshape(-1, 3).astype(m.face_sets[0].vertex_indices.dtype)
    for fs in m.face_sets:
        fs.use_backface_culling = False
        fs.is_triangle_strip = False                           # vanilla parts use strips; ours is a triangle list
    for fs in m.face_sets[1:]:                                 # LOD face sets of the vanilla mesh: use the full mesh
        fs.vertex_indices = m.face_sets[0].vertex_indices.copy()
    f.meshes = [m]                                             # the catalyst's second (alpha) mesh is dropped
    m.refresh_bounding_boxes()
    # dummies: scale along the weapon axis (staff) / plate extent (shield) to the new model
    if w["kind"] == "staff":
        k = P[:, 1].min() / old[:, 1].min()
        for d in f.dummies:
            if d.reference_id in (100, 130, 206):
                d.translate = (d.translate[0], d.translate[1] * k, d.translate[2])
        info = f"tip {P[:, 1].min():.3f} m (catalyst {old[:, 1].min():.3f}), length {np.ptp(P[:, 1]):.2f} m"
    else:
        kx = np.ptp(P[:, 0]) / np.ptp(old[:, 0]); ky = np.ptp(P[:, 1]) / np.ptp(old[:, 1])
        co, cn = (old.max(0) + old.min(0)) / 2, (P.max(0) + P.min(0)) / 2
        for d in f.dummies:
            t = np.array(d.translate)
            if d.reference_id == 206:
                t = cn + (t - co) * np.array([kx, ky, 1.0])
                t[2] = np.clip(t[2], P[:, 2].min(), P[:, 2].max())
            else:
                t = np.array([0.0, 0.0, P[:, 2].mean()])
            d.translate = tuple(t)
        info = f"size x {np.ptp(P[:, 0]):.2f} y {np.ptp(P[:, 1]):.2f} z {np.ptp(P[:, 2]):.2f} m (Tower Shield " \
               f"{np.ptp(old[:, 0]):.2f} {np.ptp(old[:, 1]):.2f} {np.ptp(old[:, 2]):.2f}), plate side z {frontZ:+.0f}"
    if hasattr(f, "refresh_bounding_boxes"):
        f.refresh_bounding_boxes()
    for bone in f.bones:
        bone.name = bone.name.replace(tstem, stem)
    # texture: same names as the template's material expects
    tpf = TPF.from_bytes(te.data)
    png = os.path.join(src, w["who"], w["fbx"] + "_Texture0000.png")
    img = Image.open(png).convert("RGBA")
    for t in tpf.textures:
        if t.stem == tstem:
            t.data, t.format = dxt(img, "DXT5"), 5
        elif t.stem.endswith("_n"):
            t.data, t.format = flat_dxt1(), 0
        elif t.stem.endswith("_s"):
            t.data, t.format = dxt(Image.new("RGB", (64, 64), (40, 40, 40)), "DXT1"), 0
        t.stem = t.stem.replace(tstem, stem)
    te.set_from_binary_file(tpf)
    for tx in m.material.textures:
        tx.path = tx.path.replace(tstem, stem)
    m.material.name = stem
    fe.data = f.to_bytes()
    for e in b.entries:
        e.path = e.path.replace(tstem, stem)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, stem + ".partsbnd.dcx")
    b.write(out)
    print(f"{w['key']}: {stem} from {tstem}: {len(v)} vertices, {len(inv) // 3} triangles, {info}")
    return P, inv.reshape(-1, 3), U


if __name__ == "__main__":
    for w in WEAPONS:
        build(w, sys.argv[1], sys.argv[2], sys.argv[3])
