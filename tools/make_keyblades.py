"""SoraSouls – convert KH2 Keyblade FBX exports (OpenKH) into DSR weapon parts, without Blender (v63).

Each Keyblade becomes its own weapon model WP_A_<model>.partsbnd.dcx, built on the Kingdom Key binder already
in the mod (WP_A_0204: blade FLVER + collapsed sheath + TPF), so material, layout, bones and dummies match a part
the game already accepts.
  * Geometry: every triangle of the FBX whose vertices are skinned to the Keyblade bones (Bone0000-0002). The
    keychain + token (Bone0003-0011) are dropped, as for the Kingdom Key (DSR would hold the chain rigid).
  * Transform: game = 0.01085 * R * (kh2 - grip), R = [[1,0,0],[0,0,-1],[0,-1,0]], grip = Bone0000 (-59.7,108,-2.5).
    Fitted on W_EX010.fbx against the Blender-built Kingdom Key: max error 2e-7 m. UVs: (u, 1-v), FBX winding kept
    (272/281 Kingdom Key faces match it; the rest are degenerate/duplicates).
  * Normals: the OpenKH FBX has none -> area-weighted face normals averaged per position within 45 deg (creases
    stay sharp). Tangents from UVs (w = handedness), like the Blender export.
  * Dummies: blade hit spheres (206), tip (100) and 130 are scaled to the new blade length (tip = lowest Y).
  * Texture: <fbx stem>.png next to the FBX (one 256x128 sheet per KH2 Keyblade) -> DXT5 "KB_<KEY>" in the TPF;
    the flat normal/specular maps KEYBLADE_n/_s are kept.
  * v64 (in-game v63: Ultima Weapon "a solid mass", Oblivion's teeth solid, Oathkeeper a bit odd): KH2 cuts shapes out
    of the faces with texture alpha (faces sampling alpha < 128: Ultima 23%, Oblivion 9%, Oathkeeper 7%). Material
    is now P_Metal[DSB]_Edge (alpha test). Per-Keyblade "brighten" multiplies the texture colour (none used since v65).
  * v66: Keyblades with "thicken" (half-thickness, m) get solid cut-out cards – tools/thicken_cards.py (Ultima).
  * v65 (in-game v64: Keyblades lit at different brightness, "like Sora before"): KEYBLADE_n, the normal map copied
    from the Kingdom Key binder, was pure black like SORA_n was – replaced with the flat map from fix_sora_normalmap.
Usage: python make_keyblades.py <keyblade dir with W_EX010_xx.fbx + .png> <Kingdom Key partsbnd> <out parts dir>
"""
import copy, io, os, sys
import numpy as np
from PIL import Image
from soulstruct.containers import Binder
from soulstruct.containers.tpf import TPF
from soulstruct.flver import FLVER

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fbx_keyblade import load_keyblade
from fix_sora_normalmap import flat_dxt1
from thicken_cards import thicken
from keyblades import KEYBLADES

R = np.array([[1, 0, 0], [0, 0, -1], [0, -1, 0]], float)
GRIP = np.array([-59.7, 108.0, -2.5])
SCALE = 0.01085
KEEP_BONES = {0, 1, 2}
SMOOTH_DEG = 45.0
W_SIGN = -1.0   # matches the Kingdom Key: tangents 0.95 mean dot, handedness 95% equal
SCALED_DUMMIES = {206, 100, 130}


def geometry(fbx):
    tris = [t for t in load_keyblade(fbx) if all(int(b) in KEEP_BONES for b in t["bone"])]
    pos = np.array([(t["pos"] - GRIP) @ R.T * SCALE for t in tris])          # (n,3,3)
    uv = np.array([[(u[0], 1.0 - u[1]) for u in t["uv"]] for t in tris])   # (n,3,2)
    # mirror transform (det R = -1) reverses handedness; the Kingdom Key faces keep FBX order, so face normals use
    # the order that matches its stored normals: n = (p2-p0) x (p1-p0)
    fn = np.cross(pos[:, 2] - pos[:, 0], pos[:, 1] - pos[:, 0])
    keys = [tuple(np.round(p, 5)) for p in pos.reshape(-1, 3)]
    acc = {}
    for i, k in enumerate(keys):
        acc.setdefault(k, []).append(fn[i // 3])
    cl = np.cos(np.radians(SMOOTH_DEG))
    nrm = np.zeros((len(keys), 3))
    for i, k in enumerate(keys):
        own = fn[i // 3]; own_u = own / (np.linalg.norm(own) + 1e-12)
        s = sum((f for f in acc[k] if np.dot(f / (np.linalg.norm(f) + 1e-12), own_u) >= cl), np.zeros(3))
        nrm[i] = s / (np.linalg.norm(s) + 1e-12) if np.linalg.norm(s) > 1e-12 else own_u
    # tangents
    P, U = pos.reshape(-1, 3), uv.reshape(-1, 2)
    tan = np.zeros((len(P), 4))
    for t in range(len(tris)):
        i0, i1, i2 = 3 * t, 3 * t + 1, 3 * t + 2
        e1, e2 = P[i1] - P[i0], P[i2] - P[i0]
        d1, d2 = U[i1] - U[i0], U[i2] - U[i0]
        det = d1[0] * d2[1] - d2[0] * d1[1]
        T = (e1 * d2[1] - e2 * d1[1]) / det if abs(det) > 1e-12 else np.array([1.0, 0, 0])
        B = (e2 * d1[0] - e1 * d2[0]) / det if abs(det) > 1e-12 else np.array([0, 1.0, 0])
        for i in (i0, i1, i2):
            n = nrm[i]
            tt = T - n * np.dot(n, T)
            if np.linalg.norm(tt) < 1e-9:
                tt = np.cross(n, [0, 1, 0]) if abs(n[1]) < 0.9 else np.cross(n, [1, 0, 0])
            tt /= np.linalg.norm(tt)
            w = 1.0 if np.dot(np.cross(n, tt), B) >= 0 else -1.0
            # DSR (Blender-exported Kingdom Key) stores the UV-v direction as the tangent: cross(n, T) * w
            tan[i] = (*(np.cross(n, tt) * w), W_SIGN * w)
    return P, nrm, tan, U


def dedupe(P, N, T, U):
    key = np.round(np.hstack([P, N, U, T[:, 3:]]), 5)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    return first, inv.reshape(-1)


EDGE_MTD = "P_Metal[DSB]_Edge.mtd"   # v64: alpha-tested twin of P_Metal[DSB] (same shader and texture slots)


def dxt5(png, brighten=1.0):
    img = Image.open(png).convert("RGBA")
    if brighten != 1.0:
        a = np.asarray(img).astype(np.float32)
        a[..., :3] = np.clip(a[..., :3] * brighten, 0, 255)
        img = Image.fromarray(a.astype(np.uint8), "RGBA")
    buf = io.BytesIO(); img.save(buf, "DDS", pixel_format="DXT5")
    return buf.getvalue(), img.size


def build(kb, src_dir, template, out_dir):
    fbx = os.path.join(src_dir, kb["fbx"] + ".fbx")
    png = os.path.join(src_dir, kb["fbx"] + ".png")
    stem, tex = f"WP_A_{kb['model']:04d}", f"KB_{kb['key'].upper()}"
    b = Binder.from_path(template)
    fe = next(e for e in b.entries if e.path.endswith("WP_A_0204.flver"))
    se = next(e for e in b.entries if e.path.endswith("WP_A_0204_1.flver"))
    te = next(e for e in b.entries if e.path.endswith(".tpf"))
    f, sheath = FLVER.from_bytes(fe.data), FLVER.from_bytes(se.data)
    m = f.meshes[0]
    old_tip = float(m.vertices["position"][:, 1].min())
    P, N, T, U = geometry(fbx)
    if kb.get("thicken"):   # v66: cut-out cards get a little thickness (thicken_cards.py)
        alpha = np.asarray(Image.open(png).convert("RGBA"))[..., 3]
        (P, N, T, U), st = thicken(P, N, T, U, alpha, kb["thicken"])
        print(f"  {kb['name']}: thickness {2 * kb['thicken'] * 1000:.0f} mm on {st}")
    first, inv = dedupe(P, N, T, U)
    v = np.zeros(len(first), dtype=m.vertices.dtype)
    v["position"], v["normal"], v["tangent_0"], v["uv_0"] = P[first], N[first], T[first], U[first]
    v["normal_w"], v["bone_indices"], v["color_0"] = 127, 0, 1.0
    m.vertex_arrays[0].array = v
    m.face_sets[0].vertex_indices = inv.reshape(-1, 3).astype(m.face_sets[0].vertex_indices.dtype)
    m.refresh_bounding_boxes()
    m.face_sets[0].use_backface_culling = False   # v64: KH2 cut-out planes are single-sided, seen from both sides
    new_tip = float(P[:, 1].min())
    for d in f.dummies:
        if d.reference_id in SCALED_DUMMIES:
            d.translate = (d.translate[0], d.translate[1] * new_tip / old_tip, d.translate[2])
    for mat_owner in (m, sheath.meshes[0]):
        for t in mat_owner.material.textures:
            if t.texture_type == "g_Diffuse":
                t.path = t.path.replace("KEYBLADE_Texture0000", tex)
        mat_owner.material.name = mat_owner.material.name.replace("KEYBLADE_Texture0000", tex)
        mat_owner.material.mat_def_path = mat_owner.material.mat_def_path.replace("P_Metal[DSB].mtd", EDGE_MTD)
        if not mat_owner.material.mat_def_path.endswith(EDGE_MTD):
            raise RuntimeError(f"unexpected material {mat_owner.material.mat_def_path}")
    for fl in (f, sheath):
        for bone in fl.bones:
            bone.name = bone.name.replace("WP_A_0204", stem)
    if hasattr(f, "refresh_bounding_boxes"):
        f.refresh_bounding_boxes()
    tpf = TPF.from_bytes(te.data)
    d = next(t for t in tpf.textures if t.stem == "KEYBLADE_Texture0000")
    d.stem = tex
    d.data, size = dxt5(png, kb.get("brighten", 1.0))
    d.format = 5
    n = next(t for t in tpf.textures if t.stem == "KEYBLADE_n")   # v65: was pure black (same bug as SORA_n, v59)
    n.data, n.format = flat_dxt1(), 0
    te.set_from_binary_file(tpf)
    fe.data, se.data = f.to_bytes(), sheath.to_bytes()
    for e in b.entries:
        e.path = e.path.replace("WP_A_0204", stem)
    os.makedirs(out_dir, exist_ok=True)
    b.write(os.path.join(out_dir, stem + ".partsbnd.dcx"))
    print(f"{kb['name']}: {stem} verts {len(v)} tris {len(inv)//3} tip {new_tip:.3f} m (Kingdom Key {old_tip:.3f}) "
          f"texture {tex} {size}")
    return P


def main(src_dir, template, out_dir, only=None):
    for kb in KEYBLADES:
        if only and kb["key"] not in only:
            continue
        build(kb, src_dir, template, out_dir)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:] or None)
