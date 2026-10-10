"""SoraSouls – give KH2 cut-out "cards" a little thickness (v66). User 2026-10-08: "give the blade a little thickness".

KH2 builds parts of some Keyblades (Ultima Weapon's blade) from flat faces whose shape is cut out by texture alpha.
Edge-on they are paper-thin lines. This turns each card into a thin solid:
  1. Card faces = triangles whose texture area contains transparent texels (alpha < 128).
  2. Each card face is split into two layers, pushed +h and -h along the vertex normal (the back layer faces
     backwards: normal flipped, winding reversed).
  3. Side walls: the alpha outline (marching squares at alpha 127.5 over the whole texture) is clipped to every card
     face whose UV triangle holds the segment's midpoint and mapped to 3D through that face's barycentrics; each
     segment becomes a quad from -h to +h (outline simplified to SIMPLIFY_TEXELS, specks dropped). Walls sample the texture one texel inside the opaque side (so they pass
     the alpha test and take the edge colour) and face outwards (towards the transparent side).
Only geometry is added; the material (alpha-tested P_Metal[DSB]_Edge) stays. Faces without transparent texels are
untouched, so the rest of the Keyblade is identical.
"""
import numpy as np
from matplotlib.path import Path
from skimage.measure import approximate_polygon, find_contours

ALPHA_CUT = 128
SIMPLIFY_TEXELS = 0.75   # outline simplification tolerance
MIN_CONTOUR_TEXELS = 3.0  # drop specks


def _bary(tri_uv, pts):
    a, b, c = tri_uv
    v0, v1, v2 = b - a, c - a, pts - a
    d = v0[0] * v1[1] - v1[0] * v0[1]
    if abs(d) < 1e-14:
        return None
    l1 = (v2[..., 0] * v1[1] - v1[0] * v2[..., 1]) / d
    l2 = (v0[0] * v2[..., 1] - v2[..., 0] * v0[1]) / d
    return np.stack([1 - l1 - l2, l1, l2], -1)


def _alpha_at(alpha, uv):
    h, w = alpha.shape
    x = np.clip((uv[..., 0] % 1.0) * w, 0, w - 1).astype(int)
    y = np.clip(uv[..., 1] * h, 0, h - 1).astype(int)
    return alpha[y, x]


def card_faces(U, alpha):
    h, w = alpha.shape
    tris = U.reshape(-1, 3, 2)
    out = np.zeros(len(tris), bool)
    for t, uv in enumerate(tris):
        px = uv * [w, h]
        x0, y0 = np.floor(px.min(0)).astype(int)
        x1, y1 = np.ceil(px.max(0)).astype(int)
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        pts = np.stack([gx.ravel(), gy.ravel()], 1)
        inside = Path(px).contains_points(pts, radius=-0.01) | Path(px[::-1]).contains_points(pts, radius=-0.01)
        if not inside.any():
            continue
        a = _alpha_at(alpha, pts[inside] / [w, h])
        out[t] = (a < ALPHA_CUT).any() and (a >= ALPHA_CUT).any()
    return out


MIN_GAP = 0.004   # v67: min distance kept between a card's layers and any other overlapping parallel face
MIN_HALF = 0.0015  # cards that would need thinner layers than this stay flat (as in the KH2 model)


def _limits(P3, cards, half):
    """Per card face half-thickness. A layer must stay MIN_GAP away from every overlapping parallel face (other cards
    and their layers, and the rest of the model), or it z-fights (in-game v66 flicker)."""
    fn = np.cross(P3[:, 1] - P3[:, 0], P3[:, 2] - P3[:, 0])
    area = np.linalg.norm(fn, axis=1)
    fn /= area[:, None] + 1e-12
    hf = np.full(len(P3), half)
    lo, hi = P3.min(1), P3.max(1)
    is_card = np.zeros(len(P3), bool)
    is_card[cards] = True
    for i in cards:
        for j in range(len(P3)):
            if j == i or area[j] < 1e-9 or abs(np.dot(fn[i], fn[j])) < 0.99:
                continue
            g = abs(np.dot(fn[i], P3[j].mean(0) - P3[i, 0]))
            if g < 1e-5:
                continue                                          # same plane: neighbours of one surface
            reach = (2 * half if is_card[j] else half) + MIN_GAP
            if g >= reach:
                continue
            if ((lo[i] - g) > hi[j]).any() or ((lo[j] - g) > hi[i]).any():
                continue                                          # bounding boxes apart: no overlap
            lim = (g - MIN_GAP) / (2 if is_card[j] else 1)
            hf[i] = min(hf[i], lim)
            if is_card[j]:
                hf[j] = min(hf[j], lim)
    return hf


def _drop_fighting_walls(res, first_wall):
    """Remove wall quads lying within MIN_GAP/2 of an overlapping parallel face (model or an earlier wall): z-fighting."""
    P = res[0].reshape(-1, 3, 3)
    fn = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    area = np.linalg.norm(fn, axis=1)
    fn /= area[:, None] + 1e-12
    c = P.mean(1)
    bad = set()
    for w in range(first_wall, len(P)):
        own = first_wall + 2 * ((w - first_wall) // 2)              # this wall's two triangles
        others = np.array([j for j in range(w) if area[j] > 1e-9 and j != own
                           and (j < first_wall or (j - first_wall) // 2 not in bad)], int)
        if not len(others):
            continue
        par = np.abs(fn[others] @ fn[w]) > 0.99
        g = np.abs((c[others] - P[w, 0]) @ fn[w])
        for j in others[par & (g < MIN_GAP / 2)]:
            u = P[w, 1] - P[w, 0]
            u /= np.linalg.norm(u)
            v = np.cross(fn[w], u)
            tri = np.stack([(P[w] - P[w, 0]) @ u, (P[w] - P[w, 0]) @ v], 1)
            pts = np.stack([(q - P[w, 0]) @ u for q in np.vstack([P[j], c[j][None]])]), np.stack([(q - P[w, 0]) @ v for q in np.vstack([P[j], c[j][None]])])
            pts = np.stack(pts, 1)
            if (Path(tri).contains_points(pts) | Path(tri[::-1]).contains_points(pts)).any():
                bad.add((w - first_wall) // 2)
                break
    if not bad:
        return res, 0
    keep = np.ones(len(P), bool)
    for q in bad:
        keep[first_wall + 2 * q: first_wall + 2 * q + 2] = False
    return [r.reshape(len(P), 3, -1)[keep].reshape(-1, r.shape[-1]) for r in res], len(bad)


def thicken(P, N, T, U, alpha, half):
    """P, N, T, U: per-corner arrays (3 per triangle). Returns new arrays and a stats dict."""
    h, w = alpha.shape
    cards_mask = card_faces(U, alpha)
    P3, N3, T3, U3 = (x.reshape(len(x) // 3, 3, -1) for x in (P, N, T, U))
    # v67 (in-game v66: "the texture is flickering"): the KH2 model draws each card twice (front + back copy at the
    # same positions) -> their layers landed on top of each other. Keep one copy per card; the two layers cover
    # both sides anyway.
    seen, cards = set(), []
    for t in np.where(cards_mask)[0]:
        k = frozenset(tuple(np.round(p, 4)) for p in P3[t])
        if k not in seen:
            seen.add(k)
            cards.append(t)
    cards = np.array(cards, int)
    hf = _limits(P3, cards, half)
    flat = cards[hf[cards] < MIN_HALF]                            # stay as in KH2 (all original copies kept)
    cards = cards[hf[cards] >= MIN_HALF]
    cards_mask = cards_mask.copy()
    for t in flat:
        k = frozenset(tuple(np.round(p, 4)) for p in P3[t])
        for u in np.where(cards_mask)[0]:
            if frozenset(tuple(np.round(p, 4)) for p in P3[u]) == k:
                cards_mask[u] = False
    hpos = {}
    for t in cards:
        for p in P3[t]:
            k = tuple(np.round(p, 4))
            hpos[k] = min(hpos.get(k, half), hf[t])
    hc = np.array([[hpos[tuple(np.round(p, 4))] for p in P3[t]] for t in cards])[..., None]   # (n,3,1)
    out = [[P3[~cards_mask]], [N3[~cards_mask]], [T3[~cards_mask]], [U3[~cards_mask]]]
    # 1+2: two layers per card face
    cp, cn, ct, cu = P3[cards], N3[cards], T3[cards], U3[cards]
    out[0] += [cp + hc * cn, (cp - hc * cn)[:, ::-1]]
    out[1] += [cn, (-cn)[:, ::-1]]
    out[2] += [ct, ct[:, ::-1]]
    out[3] += [cu, cu[:, ::-1]]
    # 3: walls along the alpha outline
    n_before_walls = sum(len(o) for o in out[0])
    walls, done = 0, set()
    tex = 1.0 / np.array([w, h])
    for contour in find_contours(alpha.astype(np.float32), ALPHA_CUT - 0.5):
        if np.linalg.norm(np.diff(contour, axis=0), axis=1).sum() < MIN_CONTOUR_TEXELS:
            continue
        contour = approximate_polygon(contour, SIMPLIFY_TEXELS)
        uv = (contour[:, ::-1] + 0.5) * tex                     # (row, col) of texel centres -> uv
        for a, b in zip(uv[:-1], uv[1:]):
            if np.allclose(a, b):
                continue
            m = 0.5 * (a + b)
            d = b - a
            perp = np.array([-d[1], d[0]]) / np.linalg.norm(d)
            inward = perp if _alpha_at(alpha, m + perp * tex * 1.2) >= ALPHA_CUT else -perp
            for ci, t in enumerate(cards):
                bm = _bary(U3[t], m)
                if bm is None or (bm < -1e-4).any():
                    continue
                bab = _bary(U3[t], np.stack([a, b, m - inward * tex]))
                pa, pb, pout = bab @ P3[t]
                key = frozenset((tuple(np.round(pa, 3)), tuple(np.round(pb, 3))))
                if key in done:                                  # v67: same edge reached through two faces
                    continue
                done.add(key)
                na, nb = bab[0] @ N3[t], bab[1] @ N3[t]
                na, nb = na / np.linalg.norm(na), nb / np.linalg.norm(nb)
                ha, hb = float(bab[0] @ hc[ci, :, 0]), float(bab[1] @ hc[ci, :, 0])
                wn = pout - 0.5 * (pa + pb)
                wn = wn - na * np.dot(wn, na)
                if np.linalg.norm(wn) < 1e-12:
                    continue
                wn /= np.linalg.norm(wn)
                q = np.array([pa - ha * na, pb - hb * nb, pb + hb * nb, pa + ha * na])
                quv = np.array([a, b, b, a]) + inward * tex * 1.2
                tan = T3[t][0]
                for tri in ((0, 1, 2), (0, 2, 3)):
                    out[0].append(q[list(tri)][None])
                    out[1].append(np.repeat(wn[None, None], 3, 1))
                    out[2].append(np.repeat(tan[None, None], 3, 1))
                    out[3].append(quv[list(tri)][None])
                walls += 1
    res = [np.concatenate(o).reshape(-1, o[0].shape[-1]) for o in out]
    res, dropped = _drop_fighting_walls(res, n_before_walls)
    return res, {"walls_dropped": dropped, "card_faces": int(cards_mask.sum()), "unique_cards": len(cards), "wall_quads": walls,
                 "thinned_faces": int((hf[cards] < half).sum()), "left_flat": len(flat),
                 "min_half_mm": round(float(hf[cards].min()) * 1000, 2)}
