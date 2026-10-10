"""SoraSouls – Roxas's armor parts (model 9556), for Sora's hollow look (v126). User 2026-10-10: "When humanity is lost
on death sora should look like roxas".

Finding: KH2's Roxas (P_EX110) uses exactly Sora's skeleton (all 228 bones, same names, same bind pose; Roxas adds
one) – only the meshes differ. So Roxas is fitted with Sora's own, tested fit instead of a new one:
  * Sora's finished parts + recipes give, for every finished vertex, the KH2 vertex it came from. Per KH2 bone, an
    affine KH2 -> Dark Souls map is fitted on the Sora vertices that bone dominates (bones with too few vertices use
    their parent's), and the Dark Souls bone weights those vertices ended up with are averaged.
  * Each Roxas vertex is moved by the blend of its KH2 bones' maps (its own KH2 skin weights – smooth across joints)
    and gets the blended Dark Souls weights.
  * Parts are written by kh_party_model.build_parts (Sora's parts as templates, bone-usage safety, textures from
    Roxas's own PNGs, all _M / LG_F variants), as for Donald and Goofy.

  python roxas_model.py <roxas export dir (P_EX110.fbx + PNGs)> <sora export dir (P_EX100.fbx)> <Sora parts dir>
                        <recipe dir> <DSR skeleton json> <out parts dir> [preview dir]
"""
import json, os, sys
import numpy as np
from soulstruct.containers import Binder
from soulstruct.flver import FLVER

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kh_fbx            # noqa: E402
import kh_party_model    # noqa: E402

MODEL, PREFIX = 9556, "ROXAS"
MIN_VERTS = 12
MIRROR = np.array([1.0, 1.0, -1.0])   # KH2 faces +Z, Dark Souls -Z: a mirror, which a rotation cannot express
kh_party_model.CHARS["roxas"] = dict(fbx="P_EX110.fbx", model=MODEL, tex_prefix=PREFIX)


def _names(d):
    return {oid: b["name"] for oid, b in d["bones"].items()}


def _parents(d):
    nm = _names(d)
    return {b["name"]: nm.get(b["parent"]) for b in d["bones"].values()}


def sora_pairs(sora_fbx, sora_parts, recipes):
    """(KH2 position, KH2 weights by bone name, Dark Souls position, Dark Souls weights by bone name) for every
    finished Sora vertex."""
    s = kh_fbx.load(sora_fbx)
    nm = _names(s)
    out = []
    for stem in ("HD_A_9550", "BD_A_9550", "AM_A_9550", "LG_M_9550"):
        info = json.load(open(os.path.join(recipes, f"{stem}.recipe.json"), encoding="utf-8"))
        arr = np.load(os.path.join(recipes, f"{stem}.recipe.npz"))
        fins = {e.path: FLVER.from_bytes(e.data) for e in
                Binder.from_path(os.path.join(sora_parts, f"{stem}.partsbnd.dcx")).entries if e.path.endswith(".flver")}
        for path, metas in info["meshes"].items():
            f = fins[path]
            for m, mi in zip(f.meshes, metas):
                src = arr[mi["key"] + "_src"]
                pal = list(m.bone_indices)
                v = m.vertices
                for i, (k, t, c) in enumerate(src):
                    if k < 0:
                        continue
                    mesh = s["meshes"][k]
                    cp = mesh["tris"][t][c]
                    kw = {nm[o]: w for o, w in mesh["W"][cp].items()}
                    dw = {}
                    for bi, w in zip(v["bone_indices"][i], v["bone_weights"][i]):
                        if w > 0:
                            n = f.bones[pal[bi] if pal else bi].name
                            dw[n] = dw.get(n, 0.0) + float(w)
                    out.append((mesh["V"][cp], kw, v["position"][i].astype(float), dw))
    return out


BONE_MAP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "bone_map_sora.json")


def _via():
    """KH2 bone name -> the bone group Sora's fitting used (data/bone_map_sora.json "via": e.g. every hair and face bone
    -> the head bone). Fitting per group keeps rigid pieces rigid (preview v2: per-bone fits bent the hair)."""
    bm = json.load(open(BONE_MAP, encoding="utf-8"))["bones"]
    hand = {s: next(f"Bone{int(v['via']):04d}" for v in bm.values() if v["dsr"] == f"{s}_Hand") for s in "LR"}
    # fingers ride the hand (preview v3: finger groups have too few Sora vertices for a stable fit – bent fingers)
    return {f"Bone{int(k):04d}": hand[v["dsr"][0]] if "_Finger" in v["dsr"] else f"Bone{int(v['via']):04d}"
            for k, v in bm.items()}


def bone_maps(pairs, parents):
    """per KH2 bone group: similarity map (4x3) and average Dark Souls weights, from the vertices it dominates"""
    via = _via()
    groups = {}
    for p, kw, q, dw in pairs:
        if kw:
            b = max(kw.items(), key=lambda x: x[1])[0]
            groups.setdefault(via.get(b, b), []).append((p, q, dw))
    maps, prof = {}, {}
    for b, g in groups.items():
        Xp = np.array([p for p, _, _ in g]) * MIRROR; Y = np.array([q for _, q, _ in g])
        if len(g) >= MIN_VERTS:
            # similarity (rotation + uniform scale + shift, Umeyama), not a free affine map: a bone whose Sora vertices
            # lie almost in a plane gave a wild affine fit (preview v1: forearm folded up, a shoe flap sticking out)
            mx, my = Xp.mean(0), Y.mean(0); A, B = Xp - mx, Y - my
            U, S, Vt = np.linalg.svd(B.T @ A / len(g))
            D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt))
            R = U @ D @ Vt
            s = np.trace(np.diag(S) @ D) / (A ** 2).sum(1).mean()
            M = np.zeros((4, 3)); M[:3] = (s * R).T; M[3] = my - (s * R) @ mx
            maps[b] = M
        acc = {}
        for _, _, dw in g:
            for n, w in dw.items():
                acc[n] = acc.get(n, 0.0) + w
        tot = sum(acc.values())
        prof[b] = {n: w / tot for n, w in acc.items()}

    def lookup(table, b):
        b = via.get(b, b)
        seen = set()
        while b is not None and b not in table and b not in seen:
            seen.add(b); b = parents.get(b)
        return table.get(b)
    return maps, prof, lookup


NEIGHBOURS = 6
CROTCH_CM, CROTCH_Y = 7.0, 80.0   # KH2 cm: the joined inner trouser faces
SIDE_CM = 3.0          # KH2 cm from the middle: beyond this, a vertex only follows Sora vertices on its own side


def fit_roxas(roxas_fbx, pairs, report=print):
    """Each Roxas vertex follows the Sora vertices nearest to it in the shared KH2 bind pose: the blend of their bone
    groups' maps moves it, the blend of their finished Dark Souls weights skins it. (Roxas's own KH2 skin weights are
    not used: preview v4 – part of his left glove is skinned 100 % to the upper arm in KH2, so it flew up.)"""
    from scipy.spatial import cKDTree
    r = kh_fbx.load(roxas_fbx)
    parents = _parents(r)
    maps, prof, lookup = bone_maps(pairs, parents)
    report(f"roxas: {len(maps)} KH2 bone groups with their own fit")
    SP = np.array([p for p, kw, q, dw in pairs]) * MIRROR
    SG = [lookup(maps, max(kw.items(), key=lambda x: x[1])[0]) if kw else None for p, kw, q, dw in pairs]
    SW = [dw for p, kw, q, dw in pairs]
    limb_side = [1 if any(n.startswith("L_") for n in dw) else -1 if any(n.startswith("R_") for n in dw) else 0
                 for dw in SW]
    # v126b (in-game: "feet messed up" – shoes fused into one flat board, trouser legs joined like a skirt): the
    # legs stand only a few cm apart in the bind pose, so a vertex on the inside of one leg also picked Sora vertices
    # of the other leg and got weights of both. Away from the middle, neighbours now come from the same side only.
    side = np.sign(SP[:, 0])
    joint_x = {oid: float(np.asarray(b["glob"])[3, 0]) for oid, b in r["bones"].items()}
    nm = _names(r)
    dsr_of = {f"Bone{int(k):04d}": v["dsr"] for k, v in json.load(open(BONE_MAP, encoding="utf-8"))["bones"].items()}
    trees = {s: (cKDTree(SP[side == s]), np.flatnonzero(side == s)) for s in (-1.0, 1.0)}
    tree = cKDTree(SP)
    pos, wts = [], []
    for m in r["meshes"]:
        V = np.asarray(m["V"], float) * MIRROR
        dist, idx = tree.query(V, k=NEIGHBOURS)
        # side of each Roxas vertex: the side of the joint of its dominant KH2 bone (limb joints sit well off the
        # middle; the inner faces of the trouser legs do not), else from its own position
        kside = np.zeros(len(V))
        for i, w in enumerate(m["W"]):
            if w:
                jx = joint_x.get(max(w.items(), key=lambda x: x[1])[0], 0.0)
                kside[i] = np.sign(jx) if abs(jx) > SIDE_CM else 0.0
        far = (kside == 0) & (np.abs(V[:, 0]) > SIDE_CM)
        kside[far] = np.sign(V[far, 0])
        for s, (t, ids) in trees.items():
            sel = np.flatnonzero(kside == s)
            if len(sel):
                d2, i2 = t.query(V[sel], k=NEIGHBOURS)
                dist[sel], idx[sel] = d2, ids[i2]
        P = np.zeros((len(V), 3)); Wd = []
        for i, p in enumerate(V):
            w = 1.0 / (dist[i] + 0.5)              # cm; nearer Sora vertices count more
            # never mix the two legs / arms: keep the neighbours of the side that weighs more (Sora's own vertices
            # never carry left and right weights together)
            sides = np.array([limb_side[j] for j in idx[i]])
            kw = m["W"][i]
            if abs(p[0]) < CROTCH_CM and p[1] < CROTCH_Y and kw:
                # inner faces of Roxas's trouser legs, joined to the other leg in his KH2 mesh: his own KH2 skin
                # (through Sora's bone map) decides, so the cloth between the legs stretches as it does in KH2
                tot = sum(kw.values())
                q, dw = np.zeros(3), {}
                for o, x in kw.items():
                    b = nm[o]
                    q += (x / tot) * (np.r_[p, 1.0] @ lookup(maps, b))
                    n = dsr_of.get(b)
                    if n:
                        dw[n] = dw.get(n, 0.0) + x / tot
                P[i] = q; Wd.append(dw)
                continue
            if (sides > 0).any() and (sides < 0).any():
                keep = 1.0 if w[sides > 0].sum() >= w[sides < 0].sum() else -1.0
                w = np.where(sides == -keep, 0.0, w)
            w = w / w.sum()
            q, dw = np.zeros(3), {}
            for wi, j in zip(w, idx[i]):
                if wi == 0:
                    continue
                A = SG[j]
                q += wi * (np.r_[p, 1.0] @ A)
                for n, y in SW[j].items():
                    dw[n] = dw.get(n, 0.0) + wi * y
            P[i] = q; Wd.append(dw)
        pos.append(P); wts.append(Wd)
    return r, pos, wts

def main(roxas_dir, sora_dir, sora_parts, recipes, skel, out, preview=None):
    pairs = sora_pairs(os.path.join(sora_dir, "P_EX100.fbx"), sora_parts, recipes)
    d, pos, wts = fit_roxas(os.path.join(roxas_dir, "P_EX110.fbx"), pairs)
    allp = np.vstack(pos)
    print(f"roxas: height {allp[:, 1].max():.2f} m, lowest {allp[:, 1].min():.3f} m, width {np.ptp(allp[:, 0]):.2f} m")
    if preview:
        from PIL import Image
        os.makedirs(preview, exist_ok=True)
        tex = {f"Texture000{i}": np.asarray(Image.open(os.path.join(roxas_dir, f"Texture000{i}.png")).convert("RGBA"))
               for i in range(3) if os.path.exists(os.path.join(roxas_dir, f"Texture000{i}.png"))}
        kh_party_model.render(kh_party_model.triangles(d, pos, tex), os.path.join(preview, "roxas_fit.png"), "Roxas (Sora's fit)")
    kh_party_model.build_parts("roxas", d, pos, wts, roxas_dir, sora_parts, out, skel_path=skel)


if __name__ == "__main__":
    import logging
    logging.disable(logging.WARNING)
    main(*sys.argv[1:8])
