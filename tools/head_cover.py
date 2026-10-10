"""SoraSouls – find the head size / placement that hides the human head inside a KH2 party member's head (v106).

Every Dark Souls human NPC renders its own FaceGen face (parts FG_A_0000, shared by all humans) and back of head
(FC_*): no param or helmet flag hides them (v45: HideFlag0 doesn't; v46/v104: helmet face scale scales the helmet;
v105: CharaInit bodyScaleHead has no visible effect). So the KH2 head must enclose them. This measures the human head
from the user's own FG_A_0000 / FC_M_0000 / FC_A_9000 (bind pose) and searches the smallest head scale (relative to the
character's K) and offset for which every human-head point lies inside the KH2 head's outline, slice by slice
(convex outline in x/z per 1.5 cm height slice, 6 mm margin).
Usage: python head_cover.py <who> <work dir> <dsr skeleton json> <human head .npy>
"""
import sys
import numpy as np
from matplotlib.path import Path
from scipy.spatial import ConvexHull

SLICE, MARGIN = 0.015, 0.006


def coverage(head_pts, human, fixed=None):
    pts = head_pts if fixed is None else np.vstack([head_pts, fixed])
    ok = 0
    for y in np.unique(np.round(human[:, 1] / SLICE)):
        hs = human[np.round(human[:, 1] / SLICE) == y]
        ks = pts[np.abs(pts[:, 1] - y * SLICE) < SLICE]
        if len(ks) < 4:
            continue
        try:
            hull = ConvexHull(ks[:, [0, 2]])
        except Exception:
            continue
        path = Path(ks[hull.vertices][:, [0, 2]])
        ok += int(path.contains_points(hs[:, [0, 2]], radius=-MARGIN).sum())
    return ok / len(human)


def search(rel, head_joint, K, human, fixed, hk_range, dy_range, dz_range):
    best = None
    for hk in hk_range:
        for dy in dy_range:
            for dz in dz_range:
                q = head_joint + K * hk * rel + np.array([0, dy, dz])
                c = coverage(q, human, fixed)
                top = q[:, 1].max()
                key = (c >= 0.995, -top if c >= 0.995 else c)
                if best is None or key > best[0]:
                    best = (key, hk, dy, dz, c, top)
    return best


if __name__ == "__main__":
    import kh_fbx, kh_party_model as M
    who, work, skel, human_npy = sys.argv[1:5]
    ch = M.CHARS[who]
    d = kh_fbx.load(f"{work}/{ch['fbx']}")
    dsr, _ = M.load_dsr(skel)
    human = np.load(human_npy)
    ch["head_k"], ch["head_offset"] = 1.0, (0, 0, 0)
    pos, wts, K = M.fit(ch, d, dsr)
    head = np.vstack([p[[i for i, w in enumerate(wl) if w.get("Head", 0) > 0.5 or w.get("Neck", 0) > 0.99 and p[i][1] > 1.5]]
                      for p, wl in zip(pos, wts)])
    rel = (head - dsr["Head"]) / K
    print(f"{who}: K {K:.3f}, head vertices {len(head)}, coverage as is {coverage(head, human):.1%}")
    b = search(rel, dsr["Head"], K, human, None, np.arange(1.0, 1.65, 0.05), np.arange(-0.06, 0.11, 0.01),
               np.arange(-0.08, 0.081, 0.01))
    print(f"  best: head_k {b[1]:.2f} offset y {b[2]:+.2f} z {b[3]:+.2f} -> coverage {b[4]:.1%}, top {b[5]:.2f} m")


# ---- v107: ray-cast visibility (in-game v106: the face still showed through Donald's forehead and Goofy's face –
# the slice outline above treats gaps between separate KH2 pieces as covered). A human-head point is exposed if a ray
# from it in any of the view directions (not steeply downward: that is the neck opening) leaves without hitting a
# KH2 triangle. The human head is inflated 8 % about its centre (FaceGen face shapes can be larger than the base mesh).
def directions(n=60, min_y=-0.35):
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n); th = np.pi * (1 + 5 ** 0.5) * i
    d = np.stack([np.cos(th) * np.sin(phi), np.cos(phi), np.sin(th) * np.sin(phi)], 1)
    return d[d[:, 1] >= min_y]


def exposed(points, tris, dirs, chunk=4000):
    """bool per point: some direction escapes. tris (m,3,3). Möller–Trumbore, vectorised."""
    v0, e1, e2 = tris[:, 0], tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]
    out = np.zeros(len(points), bool)
    for di in dirs:
        pv = np.cross(di, e2)                         # (m,3)
        det = np.einsum("ij,ij->i", e1, pv)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1), 0)
        for s in range(0, len(points), chunk):
            P = points[s:s + chunk][:, None, :]       # (k,1,3)
            tv = P - v0[None]                         # (k,m,3)
            u = np.einsum("kmj,mj->km", tv, pv) * inv
            qv = np.cross(tv, e1[None])
            v = np.einsum("kmj,j->km", qv, di) * inv
            t = np.einsum("kmj,mj->km", qv, e2) * inv
            hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-4)
            out[s:s + chunk] |= ~hit.any(1)
    return out


def inflate(human, f=1.08):
    c = (human.max(0) + human.min(0)) / 2
    return c + (human - c) * f


def ray_search(who, work, skel, human_npy, hk_list, dy_list, dz_list, step=6, ndir=36):
    """head scale (x the character's K) / offset with no exposed human-head point; lowest head top among those"""
    import kh_fbx, kh_party_model as M
    ch = M.CHARS[who]
    d = kh_fbx.load(f"{work}/{ch['fbx']}")
    dsr, _ = M.load_dsr(skel)
    ch = dict(ch); ch["head_k"], ch["head_offset"] = 1.0, (0, 0, 0)
    M.CHARS[who + "_probe"] = ch
    pos, wts, K = M.fit(ch, d, dsr)
    T, Hw = [], []
    for mi, m in enumerate(d["meshes"]):
        for a, b, c, uv, tex in m["tris"]:
            T.append(pos[mi][[a, b, c]]); Hw.append([wts[mi][i].get("Head", 0) for i in (a, b, c)])
    T, Hw = np.array(T), np.array(Hw)
    keep = T[:, :, 1].max(1) > 1.25
    T, Hw = T[keep], Hw[keep]
    head = Hw > 0.5
    human = inflate(np.load(human_npy))[::step]
    dirs = directions(ndir)
    hd = dsr["Head"]
    res = []
    for hk in hk_list:
        for dy in dy_list:
            for dz in dz_list:
                Tq = T.copy()
                Tq[head] = hd + hk * (T[head] - hd) + np.array([0, dy, dz])
                e = exposed(human, Tq, dirs).mean()
                res.append((e, Tq[:, :, 1].max(), hk, dy, dz))
    res.sort()
    return res
