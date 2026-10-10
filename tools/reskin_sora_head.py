"""SoraSouls – fix the player's face poking through Sora's head (v47, v48, v54-v57).

Cause (found 2026-10-07, mesh analysis of the deployed HD_A_9550): of Sora's head part, only the hair spikes (167
vertices) were skinned to the Head bone – his face and most of the head (994 vertices, y 1.45-1.89 m) followed the
NECK bone. The player's own FaceGen face follows the Head bone, so whenever the head turns or tilts relative to the
neck (guarding tilts it most) the two separate and the face pokes out. v45 (HideFlag0) and v46 (face scale) treated the
symptom and are reverted.
Fix: every Neck vertex above the head joint (y 1.532 in bind pose, tools/dsr_c0000_skeleton.json) moves to the Head
bone, with a soft blend band BLEND_LOW..BLEND_HIGH (Neck -> Head weights) so the neck seam bends instead of tearing.
Vertices below the band keep Neck/Spine1. Positions, normals and UVs are untouched; only bone indices/weights change.
Usage: python reskin_sora_head.py <mod parts dir (input)> <out parts dir>
"""
import os, sys
import numpy as np
from soulstruct.containers import Binder
from soulstruct.flver import FLVER

HEAD_JOINT_Y = 1.532
# v47 used 1.50-1.56: that band cut through Sora's jaw/lower face (his head part widens from y 1.48 – mesh profile:
# neck x +-0.045 at 1.44-1.47, jaw x +-0.09 from 1.48), so the lower face bent with the neck = "warped, worse when
# guarding". v48: blend only on the neck itself, everything from the jaw up is rigid on Head.
BLEND_LOW, BLEND_HIGH = 1.445, 1.475
# v54 (in-game after v53: "neck missing some textures when guarding"): with everything above 1.475 rigid on Head,
# the neck tube left the body's collar (BD Neck vertices 1.476-1.511) when the head tilted. The neck tube itself
# (|x| <= 0.055, behind the chin z > -0.09, below the head joint) now blends Neck -> Head gradually over 1.45-1.53;
# the face/jaw keep the v48 rule.
NECK_HALF_WIDTH, NECK_FRONT_Z, NECK_TOP, NECK_BLEND = 0.048, -0.09, 1.56, (1.50, 1.56)
# v56 (in-game v55: neck gap gone, face hidden, but the RIGHT jaw warped when guarding): the tube box (|x| <= 0.055,
# z > -0.09) still caught jaw-corner vertices (|x| 0.05-0.055, z ~ -0.086; the mesh is not perfectly mirrored there, so
# mostly on the right). The neck ring itself is |x| <= 0.047, so only the width is tightened (the throat under the chin, z to -0.08, keeps
# blending so the front of the seam stays closed).
# v55 (in-game v54: neck gap still there): Sora's BODY part has its own short neck ring (BD vertices skinned rigidly to
# Neck at y 1.476-1.511) that shares exact positions with head-part vertices. Those shared seam vertices now copy the
# body's weights (Neck 1.0) and the head part's neck blends to Head only above the seam (1.50-1.56).
SEAM_FADE = 0.035
NAMES = ("HD_A_9550.partsbnd.dcx", "HD_A_9550_M.partsbnd.dcx")


def reskin(data, seam=None):
    f = FLVER.from_bytes(data)
    names = [b.name for b in f.bones]
    neck, head = names.index("Neck"), names.index("Head")
    seam_pts = np.array(sorted(seam)) if seam else None
    stats = {"head": 0, "blend": 0, "kept": 0}
    for m in f.meshes:
        local = list(m.bone_indices)
        if neck not in local:
            continue
        if head not in local:
            local.append(head)
            m.bone_indices = local
        ln, lh = local.index(neck), local.index(head)
        v = m.vertices
        for i in range(len(v)):
            if v["bone_weights"][i, 1] > 0 or v["bone_indices"][i, 0] != ln:
                continue                                   # only rigid Neck vertices are touched
            x, y, z = (float(c) for c in v["position"][i])
            key = (round(x, 4), round(y, 4), round(z, 4))
            if seam and key in seam:
                stats["seam"] = stats.get("seam", 0) + 1
                continue                                   # keep Neck 1.0 = identical to the body's seam vertex
            ramp = lambda a, lo, hi: min(1.0, max(0.0, (a - lo) / (hi - lo)))
            # v57: no hard box any more – a hard edge left neighbouring vertices on different bones under the jaw
            # (warp under the right jaw, v56). "Neck-ness" s fades smoothly from 1 inside the neck ring (ellipse
            # |x| 0.047 x |z| 0.062 around z = -0.004) to 0 at 1.6x that size, and only below NECK_TOP.
            r = ((x / 0.047) ** 2 + ((z + 0.004) / 0.062) ** 2) ** 0.5
            s = (1.0 - ramp(r, 1.0, 1.6)) * (1.0 - ramp(y, NECK_TOP - 0.02, NECK_TOP + 0.02))
            t_neck = ramp(y, *NECK_BLEND)                  # head weight inside the neck ring
            t_head = ramp(y, BLEND_LOW, BLEND_HIGH)        # head weight elsewhere (v48 rule)
            t = s * t_neck + (1.0 - s) * t_head
            # v60 (in-game v59: "a tiny scar under Sora's right jaw"): the body's neck ring has one extra seam vertex on
            # the right (x -0.045, y 1.511) that must stay Neck 1.0; its neighbours jumped to ~0.2-0.4 Head right next
            # to it and the strip between them creased. Head weight now also fades in with the distance to the
            # nearest seam vertex (0 at the seam, full at SEAM_FADE m), on both sides alike.
            if seam_pts is not None and len(seam_pts):
                dmin = float(np.min(np.linalg.norm(seam_pts - np.array([x, y, z]), axis=1)))
                t *= min(1.0, dmin / SEAM_FADE)
            t = round(t, 3)
            if t == 0.0:
                stats["kept"] += 1
            elif t == 1.0:
                v["bone_indices"][i, 0] = lh
                stats["head"] += 1
            else:
                v["bone_indices"][i, 0], v["bone_indices"][i, 1] = lh, ln
                v["bone_weights"][i, 0], v["bone_weights"][i, 1] = t, 1.0 - t
                stats["blend"] += 1
    # v62 (in-game v61: "a warped model under the right jaw that gets more warped when guarding"; the left side is
    # fine): weights are made mirror-symmetric. Every head-part vertex whose mirror position (x -> -x) also exists gets
    # the same Head share as its partner: the smaller one if either is a body seam vertex (those must stay on Neck),
    # otherwise the average. The right side then bends exactly like the left.
    stats["mirrored"] = symmetrize(f, names, seam)
    return f.to_bytes(), stats


def symmetrize(f, names, seam):
    head = names.index("Head")
    neck = names.index("Neck")
    entries = {}
    for m in f.meshes:
        local = list(m.bone_indices)
        if head not in local or neck not in local:
            continue
        lh, ln = local.index(head), local.index(neck)
        v = m.vertices
        for i in range(len(v)):
            bones = {int(v["bone_indices"][i, k]) for k in range(4) if v["bone_weights"][i, k] > 0}
            if not bones <= {lh, ln}:
                continue
            hw = float(sum(v["bone_weights"][i, k] for k in range(4) if v["bone_weights"][i, k] > 0 and v["bone_indices"][i, k] == lh))
            k3 = tuple(round(float(c), 3) for c in v["position"][i])
            entries.setdefault(k3, []).append((m, i, lh, ln, hw))
    changed = 0
    for k3, lst in entries.items():
        if k3[0] >= 0:
            continue
        mk = (round(-k3[0], 3), k3[1], k3[2])
        if mk not in entries:
            continue
        a, b = lst[0][4], entries[mk][0][4]
        if abs(a - b) < 0.02:
            continue
        is_seam = seam and any(abs(sx - k3[0]) < 6e-4 and abs(sy - k3[1]) < 6e-4 and abs(sz - k3[2]) < 6e-4
                               for (sx, sy, sz) in seam) or seam and any(abs(sx - mk[0]) < 6e-4 and abs(sy - mk[1]) < 6e-4
                                                                         and abs(sz - mk[2]) < 6e-4 for (sx, sy, sz) in seam)
        t = min(a, b) if is_seam else (a + b) / 2
        for (m, i, lh, ln, _) in lst + entries[mk]:
            v = m.vertices
            v["bone_indices"][i] = 0
            v["bone_weights"][i] = 0.0
            if t >= 0.999:
                v["bone_indices"][i, 0], v["bone_weights"][i, 0] = lh, 1.0
            elif t <= 0.001:
                v["bone_indices"][i, 0], v["bone_weights"][i, 0] = ln, 1.0
            else:
                v["bone_indices"][i, 0], v["bone_indices"][i, 1] = lh, ln
                v["bone_weights"][i, 0], v["bone_weights"][i, 1] = t, 1.0 - t
        changed += 1
    return changed


def body_seam(src_dir):
    """Positions of body-part (BD_A_9550) vertices skinned to Neck."""
    b = Binder.from_path(os.path.join(src_dir, "BD_A_9550.partsbnd.dcx"))
    f = FLVER.from_bytes(next(e for e in b.entries if e.name.lower().endswith(".flver")).data)
    names = [x.name for x in f.bones]
    seam = set()
    for m in f.meshes:
        loc = [names[i] for i in m.bone_indices]
        for p, bi, w in zip(m.vertices["position"], m.vertices["bone_indices"], m.vertices["bone_weights"]):
            if loc[bi[0]] == "Neck" and w[0] > 0.99:
                seam.add((round(float(p[0]), 4), round(float(p[1]), 4), round(float(p[2]), 4)))
    return seam


def main(src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    seam = body_seam(src_dir)
    for name in NAMES:
        b = Binder.from_path(os.path.join(src_dir, name))
        for e in b.entries:
            if e.name.lower().endswith(".flver"):
                e.data, stats = reskin(bytes(e.data), seam)
                chk = FLVER.from_bytes(e.data)
                bn = [x.name for x in chk.bones]
                per = {}
                for m in chk.meshes:
                    loc = [bn[i] for i in m.bone_indices]
                    for row, w in zip(m.vertices["bone_indices"], m.vertices["bone_weights"]):
                        key = "+".join(loc[row[k]] for k in range(4) if w[k] > 0)
                        per[key] = per.get(key, 0) + 1
                print(f"{name}: {stats} -> skinning now {per}")
        b.write(os.path.join(out_dir, name))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
