"""SoraSouls â€“ model recipes: rebuild Sora's finished armor parts from the player's own KH2 export, no Blender (v124).

Sora's parts went through Blender once plus ~10 scripted fix-ups; re-running that fitting would not give the tested
model. A recipe instead replays the finished result:
  * template binder = the finished partsbnd with every KH2-derived payload removed: vertex positions and UVs zeroed,
    KH2 diffuse/specular textures replaced by a flat placeholder (drive_outfits.py rewrites them from the player's
    own PNGs afterwards);
  * per vertex: the KH2 control point it came from (mesh, index into the FBX export) and our position offset from it.
    UVs are recomputed from that corner of the export (KH2 UV, V flipped, rounded to 1/1024 â€“ checked exact).
Bone weights, normals and tangents are our own work and stay in the template. Without the export the recipe holds no
usable model: positions are offsets from KH2 vertices the recipe does not contain.

Findings (2026-10-10, deployed v123): every vertex of HD/BD/AM/LG_M_9550 matches a KH2 corner by UV + texture; the
finished FLVERs round-trip byte-identically through soulstruct 2.6, so replaying into the template gives the exact
deployed file. drive_outfits.py run on just these four plain parts rebuilds all 60 Sora/form part files exactly.

  python model_recipe.py extract <finished partsbnd.dcx> <KH2 export .fbx> <out recipe dir>
  python model_recipe.py replay  <recipe dir> <part stem> <KH2 export .fbx> <out parts dir>
"""
import collections, json, os, sys
import numpy as np
from soulstruct.containers import Binder
from soulstruct.containers.tpf import TPF
from soulstruct.flver import FLVER

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kh_fbx  # noqa: E402

SCALE = np.array([0.01, 0.01, -0.01])   # KH2 cm, faces +Z -> DSR m, faces -Z (only picks the nearest source corner)
UV_STEP = 1024
KH2_TEXTURE_TAG = "_Texture000"         # SORA_Texture0000..0002 (+ _s): built from the player's PNGs later


def _uv_key(u, v_flipped, tex):
    return int(np.floor(u * UV_STEP + 0.5)), int(np.floor(v_flipped * UV_STEP + 0.5)), tex


def _kh2_corners(kh):
    """(rounded uv, texture) -> [(mesh, triangle, corner)] over every triangle corner of the export."""
    corners = collections.defaultdict(list)
    for mi, m in enumerate(kh["meshes"]):
        for ti, t in enumerate(m["tris"]):
            for c in range(3):
                u, v = t[3][c]
                corners[_uv_key(u, 1.0 - v, t[4])].append((mi, ti, c))
    return corners


def _corner_pos(kh, k, t, c):
    m = kh["meshes"][k]
    return m["V"][m["tris"][t][c]]


def _corner_uv(kh, k, t, c):
    u, v = kh["meshes"][k]["tris"][t][3][c]
    return np.array(_uv_key(u, 1.0 - v, None)[:2], np.float32) / UV_STEP


def _mesh_texture(mesh):
    name = mesh.material.name                                  # e.g. SORA_Texture0001_2
    return "Texture" + name.split("_Texture")[1][:4]


def _flver_entries(b):
    return [e for e in b.entries if e.path.lower().endswith(".flver")]


def extract(part_path, fbx_path, out_dir):
    kh = kh_fbx.load(fbx_path)
    corners = _kh2_corners(kh)
    b = Binder.from_path(part_path)
    stem = os.path.basename(part_path).split(".")[0]
    recipe = {}
    for fe in _flver_entries(b):
        f = FLVER.from_bytes(fe.data)
        meshes = []
        for mi, m in enumerate(f.meshes):
            tex = _mesh_texture(m)
            verts = m.vertices
            src = np.zeros((len(verts), 3), np.int32)
            delta = np.zeros((len(verts), 3), np.float64)
            for i, (p, uv) in enumerate(zip(verts["position"], verts["uv_0"])):
                cands = corners.get(_uv_key(float(uv[0]), float(uv[1]), tex))
                if not cands:
                    raise RuntimeError(f"{stem} mesh {mi} vertex {i}: no KH2 corner with this UV")
                base = np.array([_corner_pos(kh, *x) for x in cands]) * SCALE
                j = int(np.argmin(np.linalg.norm(base - p, axis=1)))
                src[i] = cands[j]
                delta[i] = p.astype(np.float64) - base[j]
            meshes.append(dict(src=src, delta=delta, tex=tex))
            verts["position"][:] = 0
            verts["uv_0"][:] = 0
        fe.data = bytes(f.to_bytes())
        recipe[fe.path] = meshes
    _strip_textures(b)
    os.makedirs(out_dir, exist_ok=True)
    b.write(os.path.join(out_dir, f"{stem}.template.partsbnd.dcx"))
    arrays, index = {}, {}
    for path, meshes in recipe.items():
        index[path] = []
        for mi, m in enumerate(meshes):
            key = f"{os.path.basename(path)}_{mi}"
            arrays[key + "_src"], arrays[key + "_delta"] = m["src"], m["delta"]
            index[path].append(dict(key=key, tex=m["tex"]))
    np.savez_compressed(os.path.join(out_dir, f"{stem}.recipe.npz"), **arrays)
    with open(os.path.join(out_dir, f"{stem}.recipe.json"), "w", encoding="utf-8") as fp:
        json.dump(dict(part=stem, fbx=os.path.basename(fbx_path), meshes=index), fp, indent=1)
    replayed = Binder.from_path(replay(out_dir, stem, fbx_path, out_dir + "/check"))
    finished = Binder.from_path(part_path)
    ok = all(bytes(a.data) == bytes(b2.data) for a, b2 in zip(_flver_entries(replayed), _flver_entries(finished)))
    print(f"{stem}: recipe written, replayed FLVER {'IDENTICAL to' if ok else 'DIFFERS from'} the finished part")
    return ok


def _strip_textures(b):
    """Blank the KH2-derived textures: keep the DDS header (size, mips, format – drive_outfits.py rebuilds each texture
    at that size), zero every pixel block."""
    te = next(e for e in b.entries if e.path.lower().endswith(".tpf"))
    tpf = TPF.from_bytes(te.data)
    for t in tpf.textures:
        if KH2_TEXTURE_TAG in t.stem:
            head = 148 if bytes(t.data[84:88]) == b"DX10" else 128
            t.data = bytes(t.data[:head]) + bytes(len(t.data) - head)
    te.data = bytes(tpf.to_bytes())


def replay(recipe_dir, stem, fbx_path, out_dir):
    """Template + recipe + the player's KH2 export -> the finished part (textures still placeholders)."""
    with open(os.path.join(recipe_dir, f"{stem}.recipe.json"), encoding="utf-8") as fp:
        info = json.load(fp)
    arrays = np.load(os.path.join(recipe_dir, f"{stem}.recipe.npz"))
    kh = kh_fbx.load(fbx_path)
    b = Binder.from_path(os.path.join(recipe_dir, f"{stem}.template.partsbnd.dcx"))
    for fe in _flver_entries(b):
        f = FLVER.from_bytes(fe.data)
        for m, mi in zip(f.meshes, info["meshes"][fe.path]):
            src, delta = arrays[mi["key"] + "_src"], arrays[mi["key"] + "_delta"]
            base = np.array([_corner_pos(kh, *x) for x in src]) * SCALE
            m.vertices["position"][:] = (base + delta).astype(np.float32)
            m.vertices["uv_0"][:] = np.array([_corner_uv(kh, *x) for x in src])
        fe.data = bytes(f.to_bytes())
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{stem}.partsbnd.dcx")
    b.write(out)
    return out

if __name__ == "__main__":
    import logging
    logging.disable(logging.WARNING)
    cmd, *a = sys.argv[1:]
    if cmd == "extract":
        sys.exit(0 if extract(*a) else 1)
    print("wrote", replay(*a))
