"""SoraSouls – fit Sora's arms to the DSR skeleton and smooth the joints (v49). User choice 2026-10-07: "Fit + smooth".

Findings (mesh analysis of the deployed BD_A_9550 / AM_A_9550, 2026-10-07):
  * Every arm vertex had ONE bone (rigid): no blending at shoulder, elbow or wrist, twist bones unused.
  * Sora's arm is shorter than the DSR skeleton: his geometric elbow (UpperArm|Forearm boundary) is at |x| 0.389,
    the game's elbow joint at 0.453; his wrist (Forearm|Hand gap 0.509..0.562) at ~0.535, the game's at 0.684. So the
    game bent his arm in the wrong places -> "flat/weird, extra weird when guarding".
Fix, bind pose (arms straight along +-X at y ~1.39):
  1. Stretch along X only: shoulder (0.17) fixed, Sora elbow 0.389 -> 0.453 (upper arm x1.29); forearm x0.77,
     wrist 3 cm further out, glove + fingers x0.9 (v51, see stretch()). Applied to every vertex skinned to a clavicle/arm/hand/finger
     bone, in both parts, so the BD|AM seam stays closed.
  2. Weights like the vanilla Knight set (BD/AM_A_9550 profile): clavicle -> upper arm crossfade 0.15-0.27, upper-arm
     twist share fading out by 0.40, elbow crossfade 0.41-0.50, forearm twist share rising 0.47-0.66, wrist crossfade
     0.64-0.70 with a little ForeTwist on the wrist. Finger vertices keep their rigid finger bones (only shifted).
Usage: python fit_sora_arms.py <mod parts dir (input)> <out parts dir>
"""
import os, sys
import numpy as np
from soulstruct.containers import Binder
from soulstruct.flver import FLVER

SHOULDER, SORA_ELBOW, SORA_WRIST = 0.17, 0.389, 0.535
DSR_ELBOW, DSR_WRIST = 0.453, 0.684
PARTS = ("BD_A_9550", "AM_A_9550")
# v50 (in-game v49: "left elbow and fingers acting funny", a long sliver from the left hand to the floor): adding blend
# bones grew the AM mesh's bone palette from 19 to 22 entries and only vertices using palette slots 20/21 (L_ForeTwist,
# L_UpperArm) broke – the game evidently handles at most 20 per mesh (vanilla parts use <= 12). Meshes whose palette
# exceeds MAX_PALETTE are now split into a right-side and a left-side mesh (arms never share triangles).
# v52 (in-game v51: left elbow STILL broken although the data is mirror-perfect and the usage flag was cleared):
# the vanilla AM part never uses L_UpperArm (it does use R_UpperArm) – the game evidently does not drive that bone for
# the arms part, whatever the flag says. Bones the vanilla part of the same slot never uses are not used here either;
# their weight goes to the replacement bone (left elbow on the AM side = forearm only, like vanilla).
FORBIDDEN = {"AM_A_9550": {"L_UpperArm": "L_Forearm", "LUpArmTwist": "L_Forearm", "RUpArmTwist": "R_UpperArm"}}
MAX_PALETTE = 12   # vanilla parts never exceed 12; the exact engine limit is unknown


HAND_SHIFT, HAND_SCALE = 0.03, 0.9   # v51 (in-game v50: "fingers too long"): was +0.064 shift, unscaled


def stretch(a):
    """Upper arm stretched so Sora's elbow lands on the game's elbow (x1.29). v51: the forearm is shortened to x0.77 so
    his wrist only moves out 3 cm (v49/v50 moved the whole hand 6.4 cm), and glove + fingers are scaled to 0.9 along
    the arm from his wrist (user: fingers looked too long). A full wrist fit would push his fingertips ~17 cm past the
    game's: his KH2 glove is much longer than a DSR hand, so the wrist hinge sits inside the glove."""
    if a <= SHOULDER:
        return a
    if a <= SORA_ELBOW:
        return SHOULDER + (a - SHOULDER) * (DSR_ELBOW - SHOULDER) / (SORA_ELBOW - SHOULDER)
    wrist_out = SORA_WRIST + HAND_SHIFT
    if a <= SORA_WRIST:
        return DSR_ELBOW + (a - SORA_ELBOW) * (wrist_out - DSR_ELBOW) / (SORA_WRIST - SORA_ELBOW)
    return wrist_out + (a - SORA_WRIST) * HAND_SCALE


def ramp(a, lo, hi):
    return min(1.0, max(0.0, (a - lo) / (hi - lo)))


def arm_weights(a, side):
    s = side
    cl, ua, ut, fa, ft, h = (f"{s}_Clavicle", f"{s}_UpperArm", f"{s}UpArmTwist", f"{s}_Forearm", f"{s}_ForeTwist",
                             f"{s}_Hand")
    c = ramp(a, 0.15, 0.27)
    # v53 (in-game v52: a tiny piece of the left elbow missing): AM's left elbow vertices are forearm-only (v52), so the
    # BD vertices on the same seam (|x| >= 0.45) must be too, or the seam opens when the elbow bends. Left elbow blend
    # therefore finishes by 0.45 (right side keeps 0.41-0.50).
    e = ramp(a, 0.38, 0.45) if side == "L" else ramp(a, 0.41, 0.50)
    wr = ramp(a, 0.64, 0.70)
    upper = c * (1 - e)
    t1 = 1 - ramp(a, 0.20, 0.40)
    fz = e * (1 - wr)
    t2 = ramp(a, 0.47, 0.66)
    hand = wr
    ht = 0.5 * (1 - ramp(a, 0.67, 0.72)) if hand > 0 else 0.0
    w = {cl: 1 - c, ut: upper * t1, ua: upper * (1 - t1), fa: fz * (1 - t2), ft: fz * t2 + hand * ht, h: hand * (1 - ht)}
    w = {k: v for k, v in w.items() if v > 0.01}
    top = sorted(w.items(), key=lambda kv: -kv[1])[:4]
    tot = sum(v for _, v in top)
    return [(k, v / tot) for k, v in top]


def process(data, part=None):
    f = FLVER.from_bytes(data)
    names = [b.name for b in f.bones]
    stats = {"stretched": 0, "reweighted": 0}
    for m in f.meshes:
        local = list(m.bone_indices)
        v = m.vertices
        new_local = list(local)
        for i in range(len(v)):
            bone = names[local[v["bone_indices"][i, 0]]]
            side = "R" if bone.startswith("R") else "L" if bone.startswith("L") else None
            if side is None or not any(t in bone for t in ("Clavicle", "Arm", "Fore", "Hand", "Finger")):
                continue
            x = float(v["position"][i, 0])
            a2 = stretch(abs(x))
            v["position"][i, 0] = a2 if x >= 0 else -a2
            stats["stretched"] += 1
            if "Finger" in bone or v["bone_weights"][i, 1] > 0:
                continue
            ws = arm_weights(a2, side)
            repl = FORBIDDEN.get(part, {})
            if any(k in repl for k, _ in ws):
                merged = {}
                for k, wv in ws:
                    merged[repl.get(k, k)] = merged.get(repl.get(k, k), 0.0) + wv
                ws = sorted(merged.items(), key=lambda kv: -kv[1])
            for k in range(4):
                if k < len(ws):
                    gi = names.index(ws[k][0])
                    if gi not in new_local:
                        new_local.append(gi)
                    v["bone_indices"][i, k] = new_local.index(gi)
                    v["bone_weights"][i, k] = ws[k][1]
                else:
                    v["bone_indices"][i, k] = 0
                    v["bone_weights"][i, k] = 0.0
            stats["reweighted"] += 1
        m.bone_indices = new_local
        if hasattr(m, "refresh_bounding_boxes"):
            m.refresh_bounding_boxes()
    split_by_side(f)
    # v51 (in-game v50: left elbow still broken): FLVER bones carry usage_flags; 1 = not used by this part, and the
    # game then does not drive that bone for the part. L_UpperArm was flagged 1 in AM (Sora's AM never used it, while
    # R_UpperArm had 5 vertices = flag 0 – which is why only the LEFT elbow broke). Clear the flag on every bone a
    # mesh now references.
    used = {int(i) for m in f.meshes for i in m.bone_indices}
    stats["unflagged"] = [f.bones[i].name for i in sorted(used) if f.bones[i].usage_flags & 1]
    for i in used:
        f.bones[i].usage_flags &= ~1
    stats["palettes"] = [len(m.bone_indices) for m in f.meshes]
    return f.to_bytes(), stats


def split_by_side(f):
    import copy
    names = [b.name for b in f.bones]
    out = []
    for m in f.meshes:
        if len(m.bone_indices) <= MAX_PALETTE:
            out.append(m)
            continue
        tris = m.face_sets[0].vertex_indices
        if len(m.face_sets) != 1 or tris.ndim != 2:
            raise RuntimeError("expected one triangle-list face set")
        side_of_tri = np.sign(m.vertices["position"][tris][:, :, 0].mean(1))
        for sgn in (-1.0, 1.0):
            sel_tris = tris[side_of_tri == sgn]
            used = np.unique(sel_tris)
            if not len(used):
                continue
            n = copy.deepcopy(m)
            remap = -np.ones(len(m.vertices), dtype=np.int64)
            remap[used] = np.arange(len(used))
            verts = m.vertices[used].copy()
            old_local = list(m.bone_indices)
            gl_used = sorted({int(old_local[verts["bone_indices"][i, k]]) for i in range(len(verts)) for k in range(4)
                              if verts["bone_weights"][i, k] > 0})
            for i in range(len(verts)):
                for k in range(4):
                    if verts["bone_weights"][i, k] > 0:
                        verts["bone_indices"][i, k] = gl_used.index(int(old_local[verts["bone_indices"][i, k]]))
                    else:
                        verts["bone_indices"][i, k] = 0
            n.vertex_arrays[0].array = verts
            n.bone_indices = gl_used
            n.face_sets[0].vertex_indices = remap[sel_tris].astype(tris.dtype)
            if len(gl_used) > MAX_PALETTE:
                raise RuntimeError(f"side mesh still has {len(gl_used)} bones")
            if hasattr(n, "refresh_bounding_boxes"):
                n.refresh_bounding_boxes()
            out.append(n)
    f.meshes = out


def main(src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for part in PARTS:
        for name in (f"{part}.partsbnd.dcx", f"{part}_M.partsbnd.dcx"):
            b = Binder.from_path(os.path.join(src_dir, name))
            for e in b.entries:
                if e.name.lower().endswith(".flver"):
                    e.data, stats = process(bytes(e.data), part)
                    print(name, stats)
            b.write(os.path.join(out_dir, name))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
