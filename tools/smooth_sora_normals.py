"""SoraSouls – smooth Sora's vertex normals (v58). User 2026-10-07: "the lighting on the face looks off".

Finding (HD_A_9550, deployed v57): the KH2 mesh is split into 1081 vertices at only 352 positions, and the copies at
one position carry different normals – on the front of the face the normals at a shared position differ by 25 deg
(median), up to 177 deg. DSR lights per vertex normal, so the face shades in flat facets with hard light/dark lines
(the diagonal shadow across the cheek). The normal map SORA_n is flat, so vertex normals decide the shading alone.
Fix: every vertex normal becomes the area-weighted average of the face normals around its POSITION (all copies, all
meshes of the part), using only faces within SMOOTH_ANGLE of the vertex's own original normal – so real creases
(hair spikes, ear/jaw edges, inner surfaces) stay sharp. Tangents are re-orthogonalised to the new normals (handedness
kept). Positions, UVs, weights untouched.
Usage: python smooth_sora_normals.py <mod parts dir (input)> <out parts dir> [part stems...]   (default: HD_A_9550)
"""
import os, sys, collections
import numpy as np
from soulstruct.containers import Binder
from soulstruct.flver import FLVER

SMOOTH_ANGLE = 70.0


def smooth(data):
    f = FLVER.from_bytes(data)
    cos_lim = np.cos(np.radians(SMOOTH_ANGLE))
    faces = collections.defaultdict(list)          # position key -> [(area-weighted face normal)]
    per_mesh = []
    for m in f.meshes:
        v = m.vertices
        p = v["position"].astype(np.float64)
        tris = m.face_sets[0].vertex_indices
        fn = np.cross(p[tris[:, 1]] - p[tris[:, 0]], p[tris[:, 2]] - p[tris[:, 0]])
        n0 = v["normal"].astype(np.float64)
        # match the file's winding: flip if face normals mostly oppose the stored vertex normals
        if np.mean(np.einsum("ij,ij->i", fn, n0[tris[:, 0]])) < 0:
            fn = -fn
        keys = [tuple(np.round(x, 4)) for x in p]
        for t, n in zip(tris, fn):
            for i in t:
                faces[keys[i]].append(n)
        per_mesh.append((m, keys))
    changed = 0
    for m, keys in per_mesh:
        v = m.vertices
        for i, k in enumerate(keys):
            ref = v["normal"][i].astype(np.float64)
            ref /= np.linalg.norm(ref) + 1e-12
            acc = np.zeros(3)
            for n in faces[k]:
                ln = np.linalg.norm(n)
                if ln > 0 and np.dot(n / ln, ref) >= cos_lim:
                    acc += n
            if np.linalg.norm(acc) < 1e-12:
                continue
            new = acc / np.linalg.norm(acc)
            if np.degrees(np.arccos(np.clip(np.dot(new, ref), -1, 1))) > 0.5:
                changed += 1
            v["normal"][i] = new
            t = v["tangent_0"][i, :3].astype(np.float64)
            t = t - new * np.dot(t, new)
            if np.linalg.norm(t) > 1e-6:
                v["tangent_0"][i, :3] = t / np.linalg.norm(t)
    return f.to_bytes(), changed


def main(src_dir, out_dir, parts):
    os.makedirs(out_dir, exist_ok=True)
    for part in parts:
        for name in (f"{part}.partsbnd.dcx", f"{part}_M.partsbnd.dcx"):
            b = Binder.from_path(os.path.join(src_dir, name))
            for e in b.entries:
                if e.name.lower().endswith(".flver"):
                    e.data, changed = smooth(bytes(e.data))
                    print(f"{name}: {changed} vertex normals smoothed")
            b.write(os.path.join(out_dir, name))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:] or ["HD_A_9550"])
