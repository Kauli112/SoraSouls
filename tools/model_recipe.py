"""SoraSouls – model recipes: rebuild Sora's and the Kingdom Key's finished parts from the player's own KH2 files,
no Blender (v124).

These parts went through Blender once plus ~10 scripted fix-ups; re-running that fitting would not give the tested
model. A recipe instead replays the finished result:
  * template binder = the finished partsbnd with every KH2-derived payload removed: vertex positions and UVs zeroed,
    KH2 textures (*_Texture000x, + their _s) blanked down to the DDS header (drive_outfits.py / `texture` below
    rebuild them from the player's own KH2 pictures at that size);
  * per vertex: the KH2 triangle corner it came from (mesh, triangle, corner of the FBX export) and our position
    offset from that corner's vertex. UVs are recomputed from that corner (KH2 UV, V flipped, rounded to 1/1024);
  * a few header bytes soulstruct writes differently (mesh bounding boxes), at most MAX_PATCH_BYTES per FLVER.
v125 (recipes made safe to ship, 2026-10-10) – the template keeps no geometry of its own:
  * offsets are taken from a per-bone affine fit of the KH2 vertices (raw offsets gave the legs back exactly);
  * normals and tangent directions are stored as coordinates in the local frame of the surface rebuilt at build time
    (+ a float residual for the exact replay), so they say nothing about where the surface points;
  * Donald's/Goofy's head caps are offsets from the player's own DSR human head (kh_party_model.add_head_shell);
  * bones are offsets from the vanilla part they came from (armor: the Knight's <type>_9550);
  * FLVERs made from a vanilla FLVER (the Kingdom Key's collapsed sheath) are offsets from that vanilla FLVER.
  Leak test: a linear fit from all per-vertex recipe data predicts positions/normals no better than guessing the
  centre (worst: Donald's arms 0.42 m vs 0.72 m – left/right only). What remains is the triangle lists, bone weights,
  vertex colours, tangent handedness and a few bounding-box bytes – no usable shape.
Bone weights, normals' handedness and the triangle lists stay in the template. Without the export and the game the
recipe holds no usable model.
Findings (2026-10-10, deployed v123):
  * every vertex of HD/BD/AM/LG_M_9550 and of the Kingdom Key matches a KH2 corner by UV + texture; replay gives
    byte-identical FLVERs; drive_outfits.py on just the four plain Sora parts rebuilds all 60 Sora/form part files.
  * the Kingdom Key texture in v123 is Blender's sRGB->linear conversion of KH2's artwork (mean error 2.9 levels),
    i.e. darker than the artwork – the same issue v122 fixed for Sora. `texture` writes the artwork as is (like
    make_keyblades.py does for the other Keyblades) unless --linear is given; neither is bit-identical to v123.

  python model_recipe.py extract <finished partsbnd.dcx> <KH2 export .fbx> <out recipe dir> <DSR game dir>
  python model_recipe.py replay  <recipe dir> <part stem> <KH2 export .fbx> <out parts dir> <DSR game dir>
  python model_recipe.py texture <partsbnd.dcx> <KH2 weapon .mdlx> [--linear]   (fills <PREFIX>_Texture0000 in place)
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
MAX_PATCH_BYTES = 256
MAX_OWN_VERTICES = 400                  # vertices with no KH2 source (head caps), stored as is


UV_MODES = {"round": 0.5, "floor": 0.0}   # Blender-made parts round to 1/1024; soulstruct-written ones truncate


def _uv_key(u, v_flipped, tex, mode="round"):
    o = UV_MODES[mode]
    return int(np.floor(u * UV_STEP + o)), int(np.floor(v_flipped * UV_STEP + o)), tex


def _kh2_corners(kh, mode="round"):
    """(quantised uv, texture) -> [(mesh, triangle, corner)] over every triangle corner of the export."""
    corners = collections.defaultdict(list)
    for mi, m in enumerate(kh["meshes"]):
        for ti, t in enumerate(m["tris"]):
            for c in range(3):
                u, v = t[3][c]
                corners[_uv_key(u, 1.0 - v, t[4], mode)].append((mi, ti, c))
    return corners


def _corner_pos(kh, k, t, c):
    m = kh["meshes"][k]
    return m["V"][m["tris"][t][c]]


def _corner_uv(kh, k, t, c, mode="round"):
    u, v = kh["meshes"][k]["tris"][t][3][c]
    return np.array(_uv_key(u, 1.0 - v, None, mode)[:2], np.float32) / UV_STEP

def _mesh_texture(mesh):
    name = mesh.material.name                                  # e.g. SORA_Texture0001_2
    return "Texture" + name.split("_Texture")[1][:4]


def _flver_entries(b):
    return [e for e in b.entries if e.path.lower().endswith(".flver")]


def _dominant_bones(verts):
    idx = verts["bone_indices"]
    if "bone_weights" in verts.dtype.names:
        return idx[np.arange(len(idx)), np.argmax(verts["bone_weights"], axis=1)].astype(np.int64)
    return idx[:, 0].astype(np.int64)


def _affine(fits, p):
    """Per-vertex affine fit (n, 4, 3) applied element-wise (no BLAS: identical results on every machine)."""
    return p[:, 0:1] * fits[:, 0] + p[:, 1:2] * fits[:, 1] + p[:, 2:3] * fits[:, 2] + fits[:, 3]


def _fit_groups(bones, kh2, base, final, min_size=8):
    """Affine KH2 -> finished fit per dominant bone (groups too small or flat use one fit for the whole mesh).
    Returns a group id per vertex and the fits (g, 4, 3); group 0 is the whole-mesh fit."""
    def fit(sel):
        X = np.c_[base[sel], np.ones(sel.sum())]
        if np.linalg.matrix_rank(X) < 4:
            return None
        return np.linalg.lstsq(X, final[sel], rcond=None)[0]
    whole = fit(kh2)
    if whole is None:
        whole = np.vstack([np.eye(3), np.zeros(3)])
    fits, gid = [whole], np.zeros(len(bones), np.int32)
    for bone in np.unique(bones[kh2]):
        sel = kh2 & (bones == bone)
        g = fit(sel) if sel.sum() >= min_size else None
        if g is not None:
            gid[sel] = len(fits)
            fits.append(g)
    return gid, np.array(fits)


def _vertex_normals(pos, faces):
    """Area-weighted vertex normals of the (replayed) geometry; deterministic (element-wise ops, ordered add.at)."""
    p = pos.astype(np.float64)
    a, b, c = p[faces[:, 0]], p[faces[:, 1]], p[faces[:, 2]]
    e1, e2 = b - a, c - a
    fn = np.stack([e1[:, 1] * e2[:, 2] - e1[:, 2] * e2[:, 1],
                   e1[:, 2] * e2[:, 0] - e1[:, 0] * e2[:, 2],
                   e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]], axis=1)
    n = np.zeros_like(p)
    for k in range(3):
        np.add.at(n, faces[:, k], fn)
    ln = np.sqrt(n[:, 0] * n[:, 0] + n[:, 1] * n[:, 1] + n[:, 2] * n[:, 2])
    zero = ln < 1e-12
    n[zero], ln[zero] = (0.0, 1.0, 0.0), 1.0
    n = n / ln[:, None]
    # a tangent-plane axis from the normal (X axis unless the normal is nearly X)
    ax = np.where(np.abs(n[:, 0:1]) > 0.9, np.array([[0.0, 1.0, 0.0]]), np.array([[1.0, 0.0, 0.0]]))
    u = np.stack([n[:, 1] * ax[:, 2] - n[:, 2] * ax[:, 1],
                  n[:, 2] * ax[:, 0] - n[:, 0] * ax[:, 2],
                  n[:, 0] * ax[:, 1] - n[:, 1] * ax[:, 0]], axis=1)
    lu = np.sqrt(u[:, 0] * u[:, 0] + u[:, 1] * u[:, 1] + u[:, 2] * u[:, 2])
    u = u / lu[:, None]
    v = np.stack([n[:, 1] * u[:, 2] - n[:, 2] * u[:, 1],
                  n[:, 2] * u[:, 0] - n[:, 0] * u[:, 2],
                  n[:, 0] * u[:, 1] - n[:, 1] * u[:, 0]], axis=1)
    return n, u, v


def _to_frame(q, frame):
    """Direction -> coordinates in the local frame of the computed surface (+ the float residual for an exact replay).
    Local coordinates say nothing about where on the model a surface points."""
    q = q.astype(np.float64)
    coords = np.stack([q[:, 0] * f[:, 0] + q[:, 1] * f[:, 1] + q[:, 2] * f[:, 2] for f in frame], axis=1)
    return coords, q - _from_frame(coords, frame)


def _from_frame(coords, frame):
    n, u, v = frame
    return coords[:, 0:1] * n + coords[:, 1:2] * u + coords[:, 2:3] * v


def _mesh_faces(m):
    return np.asarray(m.face_sets[0].vertex_indices, np.int64).reshape(-1, 3)


def _human_head(game):
    """Donald's/Goofy's head caps are the player's own human head points, inflated (kh_party_model.add_head_shell)."""
    from kh_party_model import human_head_points, SHELL_INFLATE
    h = human_head_points(os.path.join(game, "parts"))
    c = (h.max(0) + h.min(0)) / 2
    return c + (h - c) * SHELL_INFLATE


def _bone_reference(game, stem):
    """Vanilla part whose bones ours were made from: armor parts -> the Knight's <type>_9550, weapons -> same stem."""
    ref = f"{stem[:4]}_9550" if stem[:2] in ("HD", "BD", "AM", "LG") else stem
    b = Binder.from_path(os.path.join(game, "parts", f"{ref}.partsbnd.dcx"))
    f = FLVER.from_bytes(next(e for e in b.entries if e.path.lower().endswith(".flver")).data)
    return {bn.name: bn for bn in f.bones}


BONE_FIELDS = ("translate", "rotate", "scale")
VERTEX_FIELDS = ("position", "normal", "tangent_0", "uv_0")


def _vanilla_flver(game, stem, name):
    b = Binder.from_path(os.path.join(game, "parts", f"{stem}.partsbnd.dcx"))
    return FLVER.from_bytes(next(e for e in b.entries if e.path.split("\\")[-1] == name).data)


def _encode_from_vanilla(f, game, stem, name):
    """A FLVER made from the vanilla one (not from KH2): per vertex the vanilla vertex it came from (same UV, nearest
    after a uniform scale) and offsets of every float field; the template keeps zeros."""
    van = _vanilla_flver(game, stem, name)
    out = []
    for mi, m in enumerate(f.meshes):
        vv = van.meshes[mi].vertices
        p, vp = m.vertices["position"].astype(np.float64), vv["position"].astype(np.float64)
        scale = float(np.ptp(p, axis=0).max() / np.ptp(vp, axis=0).max())
        src = np.zeros(len(p), np.int64)
        for i in range(len(p)):
            same_uv = np.flatnonzero((vv["uv_0"] == m.vertices["uv_0"][i]).all(axis=1))
            cand = same_uv if len(same_uv) else np.arange(len(vv))
            src[i] = cand[np.argmin(np.linalg.norm(vp[cand] * scale - p[i], axis=1))]
        d = {}
        for fl in VERTEX_FIELDS:
            ref = vv[fl][src].astype(np.float64) * (scale if fl == "position" else 1.0)
            d[fl] = m.vertices[fl].astype(np.float64) - ref
            m.vertices[fl][:] = 0
        out.append(dict(src=src, scale=scale, **d))
    return out


def extract(part_path, fbx_path, out_dir, game):
    kh = kh_fbx.load(fbx_path)
    human = None
    corners = {mode: _kh2_corners(kh, mode) for mode in UV_MODES}
    b = Binder.from_path(part_path)
    stem = os.path.basename(part_path).split(".")[0]
    recipe, uv_mode, bone_info, vanilla_flvers = {}, {}, {}, {}
    for fe in _flver_entries(b):
        f = FLVER.from_bytes(fe.data)
        hits = {mode: sum(_uv_key(float(uv[0]), float(uv[1]), _mesh_texture(m), mode) in cor
                          for m in f.meshes for uv in m.vertices["uv_0"]) for mode, cor in corners.items()}
        mode = max(hits, key=hits.get)
        total = sum(len(m.vertices) for m in f.meshes)
        if not hits[mode]:                  # e.g. the sheath WP_A_0204_1: the vanilla sheath scaled to 1/1000
            vanilla_flvers[fe.path] = _encode_from_vanilla(f, game, stem, os.path.basename(fe.path))
            fe.data = bytes(f.to_bytes())
            print(f"{stem}: {os.path.basename(fe.path)} has no KH2 geometry, stored as offsets from the vanilla one")
            continue
        if total - hits[mode] > MAX_OWN_VERTICES:
            raise RuntimeError(f"{stem}: {total - hits[mode]} of {total} vertices match no KH2 corner")
        cor, uv_mode[fe.path] = corners[mode], mode
        meshes = []
        for mi, m in enumerate(f.meshes):
            tex = _mesh_texture(m)
            verts = m.vertices
            src = np.full((len(verts), 3), -1, np.int32)
            delta = np.zeros((len(verts), 3), np.float64)
            own_uv = {}
            for i, (p, uv) in enumerate(zip(verts["position"], verts["uv_0"])):
                cands = cor.get(_uv_key(float(uv[0]), float(uv[1]), tex, mode))
                if not cands:              # our own vertex (Donald's/Goofy's head cap): from the human head
                    if human is None:
                        human = _human_head(game)
                    j = int(np.argmin(np.linalg.norm(human - p, axis=1)))
                    src[i] = (-2, j, 0)
                    delta[i], own_uv[i] = p.astype(np.float64) - human[j], np.array(uv, np.float32)
                    continue
                base = np.array([_corner_pos(kh, *x) for x in cands]) * SCALE
                j = int(np.argmin(np.linalg.norm(base - p, axis=1)))
                src[i] = cands[j]
            uvs = np.zeros((len(verts), 2), np.float32)
            for i, v in own_uv.items():
                uvs[i] = v
            # offsets are taken from a per-bone affine fit of the KH2 vertices, not from the raw KH2 vertices:
            # raw offsets would let anyone rebuild the model shape from the recipe alone (checked: legs exactly)
            kh2 = src[:, 0] >= 0
            base = np.zeros((len(verts), 3))
            base[kh2] = np.array([_corner_pos(kh, *x) for x in src[kh2]]) * SCALE
            gid, fits = _fit_groups(_dominant_bones(verts), kh2, base, verts["position"].astype(np.float64))
            delta[kh2] = verts["position"][kh2].astype(np.float64) - _affine(fits[gid[kh2]], base[kh2])
            # normals / tangent directions as offsets from what the geometry itself gives at build time (they would
            # otherwise describe the surface shape)
            frame = _vertex_normals(verts["position"], _mesh_faces(m))
            nco, ncr = _to_frame(verts["normal"], frame)
            tco, tcr = _to_frame(verts["tangent_0"][:, :3], frame)
            meshes.append(dict(src=src, delta=delta, tex=tex, own_uv=uvs, gid=gid, fits=fits,
                               nco=nco, ncr=ncr, tco=tco, tcr=tcr))
            verts["position"][:] = 0
            verts["uv_0"][:] = 0
            verts["normal"][:] = 0
            verts["tangent_0"][:, :3] = 0              # w (handedness) stays
        # bones: offsets from the vanilla part they came from (read from the player's game at build time)
        ref = _bone_reference(game, stem)
        bones = {}
        for bi, bn in enumerate(f.bones):
            r = ref.get(bn.name)
            if r is None:
                continue
            bones[bi] = [[float(a) - float(c) for a, c in zip(getattr(bn, fl), getattr(r, fl))] for fl in BONE_FIELDS]
            for fl in BONE_FIELDS:
                setattr(bn, fl, type(getattr(bn, fl))((0.0, 0.0, 0.0)))
        fe.data = bytes(f.to_bytes())
        recipe[fe.path] = meshes
        bone_info[fe.path] = bones
    _strip_textures(b)
    os.makedirs(out_dir, exist_ok=True)
    b.write(os.path.join(out_dir, f"{stem}.template.partsbnd.dcx"))
    arrays, index = {}, {}
    for path, meshes in recipe.items():
        index[path] = []
        for mi, m in enumerate(meshes):
            key = f"{os.path.basename(path)}_{mi}"
            for s in ("src", "delta", "own_uv", "gid", "fits", "nco", "ncr", "tco", "tcr"):
                arrays[f"{key}_{s}"] = m[s]
            index[path].append(dict(key=key, tex=m["tex"]))
    vanilla_index = {}
    for path, meshes in vanilla_flvers.items():
        vanilla_index[path] = []
        for mi, m in enumerate(meshes):
            key = f"van_{os.path.basename(path)}_{mi}"
            arrays[key + "_src"] = m["src"]
            for fl in VERTEX_FIELDS:
                arrays[f"{key}_{fl}"] = m[fl]
            vanilla_index[path].append(dict(key=key, scale=m["scale"]))
    np.savez_compressed(os.path.join(out_dir, f"{stem}.recipe.npz"), **arrays)
    def write_json(patches=None):
        with open(os.path.join(out_dir, f"{stem}.recipe.json"), "w", encoding="utf-8") as fp:
            json.dump(dict(part=stem, fbx=os.path.basename(fbx_path), meshes=index, uv_mode=uv_mode,
                           bones=bone_info, vanilla=vanilla_index, patches=patches or {}), fp, indent=1)

    write_json()
    finished = {e.path: bytes(e.data) for e in _flver_entries(Binder.from_path(part_path))}
    replayed = Binder.from_path(replay(out_dir, stem, fbx_path, out_dir + "/check", game))
    # soulstruct recomputes a few header fields (mesh bounding boxes) differently from the finished file: keep the
    # finished bytes as small patches (refused if large – geometry must come from the export, not the recipe)
    patches = {}
    for e in _flver_entries(replayed):
        a, ref = bytes(e.data), finished[e.path]
        runs, i = [], 0
        while i < len(ref):
            if a[i] != ref[i]:
                j = i
                while j < len(ref) and a[j] != ref[j]:
                    j += 1
                runs.append([i, ref[i:j].hex()])
                i = j
            else:
                i += 1
        if runs:
            size = sum(len(h) // 2 for _, h in runs)
            if size > MAX_PATCH_BYTES:
                raise RuntimeError(f"{stem}: replay differs in {size} bytes of {e.path} – too large for a header patch")
            patches[e.path] = runs
    if patches:
        write_json(patches)
        replayed = Binder.from_path(replay(out_dir, stem, fbx_path, out_dir + "/check", game))
    ok = all(bytes(e.data) == finished[e.path] for e in _flver_entries(replayed))
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


def replay(recipe_dir, stem, fbx_path, out_dir, game):
    """Template + recipe + the player's KH2 export -> the finished part (textures still placeholders)."""
    with open(os.path.join(recipe_dir, f"{stem}.recipe.json"), encoding="utf-8") as fp:
        info = json.load(fp)
    arrays = np.load(os.path.join(recipe_dir, f"{stem}.recipe.npz"))
    kh = kh_fbx.load(fbx_path)
    b = Binder.from_path(os.path.join(recipe_dir, f"{stem}.template.partsbnd.dcx"))
    human, ref = None, None
    for fe in _flver_entries(b):
        if fe.path in info.get("vanilla", {}):                 # made from the vanilla FLVER, not from KH2
            f = FLVER.from_bytes(fe.data)
            van = _vanilla_flver(game, stem, fe.path.split("\\")[-1])
            for m, vm, mi in zip(f.meshes, van.meshes, info["vanilla"][fe.path]):
                src = arrays[mi["key"] + "_src"]
                for fl in VERTEX_FIELDS:
                    ref = vm.vertices[fl][src].astype(np.float64) * (mi["scale"] if fl == "position" else 1.0)
                    m.vertices[fl][:] = (ref + arrays[f"{mi['key']}_{fl}"]).astype(m.vertices[fl].dtype)
            data = bytearray(f.to_bytes())
            for off, hx in info.get("patches", {}).get(fe.path, []):
                data[off:off + len(hx) // 2] = bytes.fromhex(hx)
            fe.data = bytes(data)
            continue
        if fe.path not in info["meshes"]:
            continue
        f = FLVER.from_bytes(fe.data)
        mode = info.get("uv_mode", {}).get(fe.path, "round")
        for m, mi in zip(f.meshes, info["meshes"][fe.path]):
            src, delta, uv, gid, fits, nco, ncr, tco, tcr = (arrays[f"{mi['key']}_{s}"] for s in
                                                             ("src", "delta", "own_uv", "gid", "fits", "nco", "ncr", "tco", "tcr"))
            kh2, own = src[:, 0] >= 0, src[:, 0] == -2
            base = np.zeros((len(src), 3))
            base[kh2] = np.array([_corner_pos(kh, *x) for x in src[kh2]]) * SCALE
            base[kh2] = _affine(fits[gid[kh2]], base[kh2])
            if own.any():
                if human is None:
                    human = _human_head(game)
                base[own] = human[src[own, 1]]
            m.vertices["position"][:] = (base + delta).astype(np.float32)
            uv = uv.copy()
            uv[kh2] = np.array([_corner_uv(kh, *x, mode) for x in src[kh2]])
            m.vertices["uv_0"][:] = uv
            frame = _vertex_normals(m.vertices["position"], _mesh_faces(m))
            m.vertices["normal"][:] = (_from_frame(nco, frame) + ncr).astype(np.float32)
            m.vertices["tangent_0"][:, :3] = (_from_frame(tco, frame) + tcr).astype(np.float32)
        for bi, vals in info.get("bones", {}).get(fe.path, {}).items():
            if ref is None:
                ref = _bone_reference(game, stem)
            bn = f.bones[int(bi)]
            r = ref[bn.name]
            for fl, d in zip(BONE_FIELDS, vals):
                setattr(bn, fl, type(getattr(bn, fl))(tuple(float(a) + x for a, x in zip(getattr(r, fl), d))))
        data = bytearray(f.to_bytes())
        for off, hx in info.get("patches", {}).get(fe.path, []):
            data[off:off + len(hx) // 2] = bytes.fromhex(hx)
        fe.data = bytes(data)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{stem}.partsbnd.dcx")
    b.write(out)
    return out

def pngs(part_path, png_dir):
    """Fill blanked <PREFIX>_Texture000N textures from <png_dir>/Texture000N.png the way kh_party_model.py writes
    Donald's and Goofy's (Pillow DXT5 of the artwork)."""
    from kh_party_model import dxt
    b = Binder.from_path(part_path)
    te = next(e for e in b.entries if e.path.lower().endswith(".tpf"))
    tpf = TPF.from_bytes(te.data)
    done = []
    for t in tpf.textures:
        tag = t.stem.rsplit("_", 1)[-1]
        if tag.startswith("Texture000") and KH2_TEXTURE_TAG in t.stem:
            t.data, t.format = dxt(os.path.join(png_dir, tag + ".png"), "DXT5"), 5
            done.append(t.stem)
    te.data = bytes(tpf.to_bytes())
    b.write(part_path)
    print(f"{os.path.basename(part_path)}: {', '.join(done)} from {png_dir}")


def texture(part_path, mdlx_path, linear=False):
    """Fill <PREFIX>_Texture0000 of a weapon part from the KH2 weapon's own texture sheet (read from its .mdlx)."""
    import io
    from PIL import Image
    from kh2_weapon_texture import texture as mdlx_texture
    img = mdlx_texture(mdlx_path).convert("RGBA")
    if linear:                                                 # v123 look: Blender's sRGB -> linear conversion
        a = np.asarray(img).astype(np.float32) / 255.0
        rgb = a[..., :3]
        a[..., :3] = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
        img = Image.fromarray(np.round(a * 255).astype(np.uint8), "RGBA")
    b = Binder.from_path(part_path)
    te = next(e for e in b.entries if e.path.lower().endswith(".tpf"))
    tpf = TPF.from_bytes(te.data)
    t = next(x for x in tpf.textures if x.stem.endswith("_Texture0000"))
    w, h = int.from_bytes(t.data[16:20], "little"), int.from_bytes(t.data[12:16], "little")
    if img.size != (w, h):
        raise RuntimeError(f"{mdlx_path}: texture is {img.size}, the part expects {(w, h)}")
    buf = io.BytesIO()
    img.save(buf, "DDS", pixel_format="DXT5")
    t.data, t.format = buf.getvalue(), 5
    te.data = bytes(tpf.to_bytes())
    b.write(part_path)
    print(f"{os.path.basename(part_path)}: {t.stem} from {os.path.basename(mdlx_path)} ({'linear' if linear else 'artwork'})")


if __name__ == "__main__":
    import logging
    logging.disable(logging.WARNING)
    cmd, *a = sys.argv[1:]
    if cmd == "extract":
        sys.exit(0 if extract(*a) else 1)
    if cmd == "texture":
        texture(a[0], a[1], linear="--linear" in a)
    elif cmd == "pngs":
        pngs(*a)
    else:
        print("wrote", replay(*a))
