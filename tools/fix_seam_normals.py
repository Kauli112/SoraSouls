"""SoraSouls – repair broken normals and match normals across part seams (v61).

Finding (in-game v59/v60: "a tiny scar under Sora's right jaw"; it appeared once the normal map was fixed in v59):
the body part's extra right-side neck seam vertex (x -0.045, y 1.511, z -0.021) has a ZERO-length normal, so it shades
black – a dark nick under the right jaw. More zero normals exist elsewhere (BD 2 at the waist, LG_M/LG_F 8 at the
hips). Also, vertices the head and body parts share along the neck seam carry normals up to 78 deg apart, which shows
as a hard light line around the neck.
Fix:
  1. Every zero/short normal is rebuilt from the faces around it (area-weighted, the file's winding).
  2. For positions shared by two parts (head|body neck seam, arms|body elbow seam), every copy in both parts gets the
     average of their normals, so the surface shades continuously across the seam.
Tangents are re-orthogonalised to the changed normals. Positions, UVs, weights untouched.
Usage: python fix_seam_normals.py <parts dir (input)> <out parts dir>
"""
import collections, os, sys
import numpy as np
from soulstruct.containers import Binder
from soulstruct.flver import FLVER

PARTS = ("HD_A_9550", "BD_A_9550", "AM_A_9550", "LG_M_9550", "LG_F_9550")
SEAM_PAIRS = (("HD_A_9550", "BD_A_9550"), ("AM_A_9550", "BD_A_9550"))


def key(p):
    return tuple(np.round(np.asarray(p, dtype=np.float64), 4))


def set_normal(v, i, n):
    n = n / np.linalg.norm(n)
    v["normal"][i] = n
    t = v["tangent_0"][i, :3].astype(np.float64)
    t = t - n * np.dot(t, n)
    if np.linalg.norm(t) > 1e-6:
        v["tangent_0"][i, :3] = t / np.linalg.norm(t)


def repair_zero(f):
    fixed = 0
    for m in f.meshes:
        v = m.vertices
        bad = np.where(np.linalg.norm(v["normal"], axis=1) < 0.5)[0]
        if not len(bad):
            continue
        p = v["position"].astype(np.float64)
        tris = m.face_sets[0].vertex_indices
        fn = np.cross(p[tris[:, 1]] - p[tris[:, 0]], p[tris[:, 2]] - p[tris[:, 0]])
        good = np.linalg.norm(v["normal"], axis=1) >= 0.5
        if np.mean(np.einsum("ij,ij->i", fn[good[tris[:, 0]]], v["normal"][tris[good[tris[:, 0]], 0]])) < 0:
            fn = -fn
        for i in bad:
            acc = fn[(tris == i).any(axis=1)].sum(0)
            if np.linalg.norm(acc) < 1e-12:            # degenerate faces only: borrow from a copy at this position
                same = [j for j in range(len(v)) if j != i and good[j] and key(p[j]) == key(p[i])]
                acc = v["normal"][same[0]].astype(np.float64) if same else np.array([0.0, 1.0, 0.0])
            set_normal(v, i, acc)
            fixed += 1
    return fixed


def main(src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for suffix in ("", "_M"):
        names = {p: f"{p}{suffix}.partsbnd.dcx" for p in PARTS}
        binders, flvers = {}, {}
        for p, name in names.items():
            path = os.path.join(src_dir, name)
            if not os.path.exists(path):
                continue
            b = Binder.from_path(path)
            binders[p] = b
            flvers[p] = FLVER.from_bytes(next(e for e in b.entries if e.name.lower().endswith(".flver")).data)
        report = {p: {"zero_fixed": repair_zero(f)} for p, f in flvers.items()}
        for a, c in SEAM_PAIRS:
            if a not in flvers or c not in flvers:
                continue
            copies = collections.defaultdict(list)          # position -> [(part, mesh, index)]
            for part in (a, c):
                for mi, m in enumerate(flvers[part].meshes):
                    for i, pos in enumerate(m.vertices["position"]):
                        copies[key(pos)].append((part, mi, i))
            matched = 0
            for k, lst in copies.items():
                if {x[0] for x in lst} != {a, c}:
                    continue
                acc = np.zeros(3)
                for part, mi, i in lst:
                    n = flvers[part].meshes[mi].vertices["normal"][i].astype(np.float64)
                    acc += n / np.linalg.norm(n)
                if np.linalg.norm(acc) < 1e-9:
                    continue
                for part, mi, i in lst:
                    set_normal(flvers[part].meshes[mi].vertices, i, acc)
                matched += 1
            report[a][f"seam_{c}"] = matched
        for p, b in binders.items():
            next(e for e in b.entries if e.name.lower().endswith(".flver")).data = flvers[p].to_bytes()
            b.write(os.path.join(out_dir, names[p]))
            print(names[p], report[p])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
