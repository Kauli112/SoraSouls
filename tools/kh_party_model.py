"""SoraSouls – fit a KH2 party member (Donald P_EX020 / Goofy P_EX030) onto the DSR human skeleton and build an armor
set (HD / BD / AM / LG_M parts) for him (v100). Converter-based: reads the user's own OpenKH FBX export + textures and
the user's own SoraSouls Sora parts (as format templates); nothing from KH2 or DSR is shipped.

User choice 2026-10-09: "Keep KH shapes". The DSR animations drive a human-sized skeleton, so the character is scaled
up uniformly (factor K: his pelvis->neck length = the human's) – head, body, hands and feet keep their KH shapes at that
size – and the limbs stretch the rest of the way to the human joints:
  * torso  – piecewise along the spine chain (KH pelvis/spine/chest/neck/head joints -> DSR Pelvis/Spine/Spine1/Neck/
             Head) by height; sideways/forward offsets scaled by K. Weights by height along the chain (blended at joints).
  * head   – rigid at the DSR Head joint (scale K), weight Head.
  * arms   – arc-length along the KH shoulder->elbow->wrist chain mapped onto [the torso-mapped shoulder, DSR UpperArm,
             Forearm, Hand]; offsets around the arm scaled by K. Weights by position along the DSR arm (blended).
  * hands  – rigid at DSR Hand (scale K); KH finger weights -> DSR finger bones.
  * legs   – the same along hip->knee->ankle onto [torso-mapped hip, DSR Calf, DSR Foot]; weights Thigh / Calf.
  * feet   – rigid at DSR Foot (scale K sideways/forward); below the ankle stretched down to the ground.
Vertices weighted to several regions blend the regions' results by weight, so seams meet at the shared joints.
Usage: python kh_party_model.py <donald|goofy> <work dir with fbx/png> <Sora parts dir> <out parts dir> [preview dir]
"""
import io, os, sys, json
import numpy as np
from PIL import Image
import kh_fbx

DSR_SKELETON = "dsr_c0000_skeleton.json"

# ---- per character -----------------------------------------------------------------------------------------------
# region anchors: KH bone -> region; other bones inherit from their nearest anchored ancestor
CHARS = {
    "donald": dict(
        fbx="P_EX020.fbx", model=9560, tex_prefix="DONALD",
        # v104 (in-game v103: the human face shows in Donald's open beak and through Goofy's face): the helmet's face
        # scale (party.FACE_SCALE) squashes the hidden human head via the Head bone; the KH2 head is put on the Neck
        # bone instead so it is not squashed with it (it no longer tilts separately from the neck)
        head_on_neck=False,   # v106: back on Head – the hidden human head turns with Head, so the KH2 head must too
        regions={0: "torso", 3: "torso", 4: "tail", 12: "legL", 17: "footL", 21: "legR", 26: "footR", 30: "torso",
                 42: "armL", 54: "handL", 67: "torso", 70: "torso", 73: "torso", 77: "head", 119: "armR",
                 131: "handR", 144: "torso", 147: "torso", 149: "torso", 152: "torso", 155: "torso"},
        spine=[(2, "Pelvis"), (34, "Spine"), (38, "Spine1"), (74, "Neck"), (79, "Head")],
        head=79,
        arm={"L": [46, 47, 50, 53], "R": [123, 124, 127, 130]},
        leg={"L": [13, 14, 17], "R": [22, 23, 26]},
        toe={"L": [20], "R": [29]},
        # KH2 bind-pose cloth that the KH2 animations fold into place; Dark Souls has no cloth animation for it, so
        # it is folded once here: (bone, axis, degrees) about that bone's joint. Bone 72 = sailor collar flap, flat
        # backwards in the bind pose -> down onto his back.
        # v106 (in-game v105: the human face shows in his open beak): lower beak (bone 91 chain) closed by 24 deg
        bind_fix=[(72, "x", -80.0), (91, "x", -24.0)],
        # v101 (in-game v100: "Donald's back shirt is stretching"): the folded collar followed the neck bone in part
        # -> pinned to the upper back
        rigid={72: "Spine1"},
        # v101 (in-game v100: "Donald's legs are too long"): his body sits this much below the human hip joint (the
        # spine chain's pelvis/spine points drop; the top of each leg is weighted to the pelvis so it stays attached)
        pelvis_drop=0.22,
        # v108 tried a stockier shape (drop 0.30, torso_scale (1.22, 1.15), leg_thick 1.5, tail_k 0.8); in-game v108:
        # "doesn't look better" -> v109 back to the v107 shape (the options stay available, neutral by default)
        K=1.35,
        # v106 (in-game v105: human face shows; "Donald is still too tall"): head_cover.py search – the smallest/lowest
        # head that still encloses the hidden human head (99.6 %): x0.9 and 12 cm lower -> hat top ~1.76 m (was 1.91)
        head_k=0.9,
        head_offset=(0.0, -0.12, 0.0),
        # v107 (in-game v106: the human face still shows through his forehead): closed inner cap around the hidden
        # human head in his own feather colour (see add_head_shell)
        head_shell=dict(tex="Texture0000", uv=(0.369, 0.402)),      # user-visible size: v100 preview, 1.76 (pelvis->neck match) made him ~2.0 m tall
        fingers={56: "L_Finger0", 57: "L_Finger01", 59: "L_Finger1", 60: "L_Finger11", 62: "L_Finger2",
                 63: "L_Finger21", 65: "L_Finger2", 66: "L_Finger21",
                 133: "R_Finger0", 134: "R_Finger01", 136: "R_Finger1", 137: "R_Finger11", 139: "R_Finger2",
                 140: "R_Finger21", 142: "R_Finger2", 143: "R_Finger21"},
    ),
    "goofy": dict(
        fbx="P_EX030.fbx", model=9570, tex_prefix="GOOFY",
        # v104 (in-game v103: the human face shows in Donald's open beak and through Goofy's face): the helmet's face
        # scale (party.FACE_SCALE) squashes the hidden human head via the Head bone; the KH2 head is put on the Neck
        # bone instead so it is not squashed with it (it no longer tilts separately from the neck)
        head_on_neck=False,   # v106: back on Head – the hidden human head turns with Head, so the KH2 head must too
        regions={0: "torso", 13: "armL", 27: "handL", 44: "torso", 50: "head", 87: "armR", 101: "handR",
                 118: "torso", 120: "torso", 122: "torso", 129: "legL", 136: "footL", 140: "torso", 142: "legR",
                 149: "footR", 153: "torso"},
        spine=[(2, "Pelvis"), (3, "Spine"), (9, "Spine1"), (46, "Neck"), (50, "Head")],
        head=50,
        arm={"L": [17, 18, 23, 26], "R": [91, 92, 97, 100]},
        leg={"L": [130, 131, 136], "R": [143, 144, 149]},
        toe={"L": [139], "R": [152]},
        # ears stick out sideways in the KH2 bind pose -> fold them down (whole ear about its root joint)
        bind_fix=[(62, "z", -80.0), (77, "z", 80.0)],
        K=None,      # natural size: pelvis->neck match (~0.91)
        # v102 (in-game v100: "Goofy's narrow face is showing the head underneath"): head drawn larger than the body
        # so it covers the human head inside it
        # v106: head_cover.py search (99.5 % of the human head enclosed): x1.1, 2 cm up, 3 cm back
        head_k=1.4,                                                  # v107: ray search (13 % of the cap visible)
        head_offset=(0.0, 0.0, 0.0),
        head_shell=dict(tex="Texture0002", uv=(0.553, 0.645)),      # v107: black (his head colour)
        # v103 (in-game v102: human head still shows through): his helmet row squashes the hidden human head with the
        # armor face scale (party.FACE_SCALE: the game scales the Head bone along its local X/Z = world up / depth
        # – the Head bind rotation maps local X -> +Y, Z -> -Z). Everything on the Head bone is squashed too, so his
        # own head is pre-stretched by the inverse, per vertex by its Head weight.
        face_scale=None,   # v104: head rides Neck (head_on_neck), no pre-stretch needed
        fingers={29: "L_Finger0", 30: "L_Finger01", 31: "L_Finger02", 33: "L_Finger1", 34: "L_Finger11",
                 35: "L_Finger12", 37: "L_Finger2", 38: "L_Finger21", 39: "L_Finger22", 41: "L_Finger2",
                 42: "L_Finger21", 43: "L_Finger22",
                 103: "R_Finger0", 104: "R_Finger01", 105: "R_Finger02", 107: "R_Finger1", 108: "R_Finger11",
                 109: "R_Finger12", 111: "R_Finger2", 112: "R_Finger21", 113: "R_Finger22", 115: "R_Finger2",
                 116: "R_Finger21", 117: "R_Finger22"},
    ),
}
PIECE = {"Head": "HD", "Neck": "HD"}
for s in ("L_", "R_"):
    for b in ("Forearm", "Hand", "Finger0", "Finger01", "Finger02", "Finger1", "Finger11", "Finger12", "Finger2",
              "Finger21", "Finger22"):
        PIECE[s + b] = "AM"
    for b in ("Thigh", "Calf", "Foot", "Toe0"):
        PIECE[s + b] = "LG"
PARTS = {"HD": "HD_A", "BD": "BD_A", "AM": "AM_A", "LG": "LG_M"}
# v103 (in-game v102 screenshot: both left arms stretched to the floor): in the user's 9550 parts not every skeleton
# bone is usable – the AM part's L_Clavicle / L_UpperArm (and both Finger01) don't line up with the animated
# skeleton (blender_swap_sora.py: "Knight AM has no usable L_UpperArm; BD rigs both upper arms"). Each part may only use
# the bones Sora's working parts use; triangles move to a part that has all their bones, otherwise an unsafe bone is
# replaced by its nearest safe relative in the skeleton.
SAFE = {
    "HD": {"Spine1", "Neck", "Head"},
    "BD": {"Pelvis", "R_Thigh", "L_Thigh", "Spine", "Spine1", "R_Clavicle", "R_UpperArm", "R_Forearm", "RUpArmTwist",
           "L_Clavicle", "L_UpperArm", "L_Forearm", "LUpArmTwist", "Neck"},
    "AM": {"R_UpperArm", "R_Forearm", "R_Hand", "R_Finger0", "R_Finger02", "R_Finger1", "R_Finger11", "R_Finger12",
           "R_Finger2", "R_Finger21", "R_Finger22", "R_ForeTwist", "L_Forearm", "L_Hand", "L_Finger0", "L_Finger02",
           "L_Finger1", "L_Finger11", "L_Finger12", "L_Finger2", "L_Finger21", "L_Finger22", "L_ForeTwist"},
    "LG": {"Pelvis", "R_Thigh", "R_Calf", "R_Foot", "R_Toe0", "L_Thigh", "L_Calf", "L_Foot", "L_Toe0"},
}
PIECE_ORDER = ("BD", "AM", "LG", "HD")
BLEND = 0.04          # m: weight blend half-width at limb / spine joints


def conv(v):
    """KH (cm, faces +Z) -> DSR (m, faces -Z); x kept (L_ bones on +X as for Sora)."""
    v = np.asarray(v, float)
    return v * np.array([0.01, 0.01, -0.01])


def load_dsr(path):
    sk = json.load(open(path))
    return {b["name"]: np.array(b["head"], float) for b in sk}, sk


def polyline(points):
    seg = np.linalg.norm(np.diff(points, axis=0), axis=1)
    return np.concatenate([[0], np.cumsum(seg)])


def along(points, cum, s):
    """point on a polyline at arc length s (clamped)"""
    s = np.clip(s, 0, cum[-1])
    i = np.clip(np.searchsorted(cum, s, side="right") - 1, 0, len(points) - 2)
    t = (s - cum[i]) / max(cum[i + 1] - cum[i], 1e-9)
    return points[i] + t * (points[i + 1] - points[i]), i, t


def project(points, cum, p):
    """arc-length parameter of the closest point on the polyline to p, and the offset from it"""
    best = (1e9, 0.0, None)
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        d = b - a; L2 = d @ d
        t = np.clip((p - a) @ d / L2, 0, 1) if L2 > 0 else 0.0
        if i == 0 and (p - a) @ d < 0:
            t = (p - a) @ d / L2                     # allow before the start (shoulder / hip side)
        if i == len(points) - 2 and (p - a) @ d > L2:
            t = (p - a) @ d / L2                     # and past the end
        q = a + t * d
        dist = np.linalg.norm(p - q)
        if dist < best[0]:
            best = (dist, cum[i] + t * np.sqrt(L2), p - q)
    return best[1], best[2]


def chain_weights(cum_dsr, s, names):
    """bone weights at arc length s along a DSR chain whose segment i belongs to names[i]; blended at joints"""
    w = {}
    i = int(np.clip(np.searchsorted(cum_dsr, s, side="right") - 1, 0, len(names) - 1))
    w[names[i]] = 1.0
    for j in (i, i + 1):                              # joint j sits at cum_dsr[j]
        if 0 < j < len(names):
            d = s - cum_dsr[j]
            if abs(d) < BLEND:
                f = 0.5 + 0.5 * d / BLEND             # 0 -> previous bone, 1 -> next bone
                w = {names[j - 1]: 1 - f, names[j]: f}
    return w


def fit(ch, d, dsr):
    B = d["bones"]
    idx = {o: int(b["name"][4:]) for o, b in B.items()}
    byi = {i: o for o, i in idx.items()}
    parent = {idx[o]: (idx[b["parent"]] if b["parent"] else -1) for o, b in B.items()}
    J = {i: conv(d["link"][o][:3, 3] if o in d["link"] else B[o]["glob"][:3, 3]) for o, i in idx.items()}

    def region(i):
        while i not in ch["regions"] and i >= 0:
            i = parent[i]
        return ch["regions"].get(i, "torso")

    # uniform scale K: pelvis -> neck
    sp = ch["spine"]
    kh_pel, kh_neck = J[sp[0][0]], J[sp[3][0]]
    K = (dsr["Neck"][1] - dsr["Pelvis"][1]) / (kh_neck[1] - kh_pel[1])
    if ch.get("K"):
        K = ch["K"]                                   # chosen size (the spine still spans the human pelvis->neck)
    kh_y = np.array([J[i][1] for i, _ in sp])
    kh_c = np.array([J[i] for i, _ in sp])
    ds_c = np.array([dsr[n] for _, n in sp])
    ho = np.array(ch.get("head_offset", (0, 0, 0)))    # v106: neck + head points move with the head (no fold)
    ds_c[-1] = ds_c[-1] + ho; ds_c[-2] = ds_c[-2] + ho
    drop = ch.get("pelvis_drop", 0.0)
    if drop:
        ds_c[0][1] -= drop; ds_c[1][1] -= drop * 0.5
    sp_names = [n for _, n in sp]
    cum_sp = polyline(ds_c)

    def torso_map(p):
        y = p[1]
        if y <= kh_y[0]:
            c_kh, c_ds = kh_c[0] + np.array([0, y - kh_y[0], 0]), ds_c[0] + np.array([0, K * (y - kh_y[0]), 0])
            s = 0.0 + K * (y - kh_y[0])
        elif y >= kh_y[-1]:
            c_kh, c_ds = kh_c[-1] + np.array([0, y - kh_y[-1], 0]), ds_c[-1] + np.array([0, K * (y - kh_y[-1]), 0])
            s = cum_sp[-1] + K * (y - kh_y[-1])
        else:
            i = int(np.searchsorted(kh_y, y, side="right") - 1)
            t = (y - kh_y[i]) / (kh_y[i + 1] - kh_y[i])
            c_kh = kh_c[i] + t * (kh_c[i + 1] - kh_c[i]); c_ds = ds_c[i] + t * (ds_c[i + 1] - ds_c[i])
            s = cum_sp[i] + t * (cum_sp[i + 1] - cum_sp[i])
        off = p - c_kh; off[1] = 0
        tsx, tsz = ch.get("torso_scale", (1.0, 1.0))    # v108
        off[0] *= tsx; off[2] *= tsz
        return c_ds + K * off, s

    def torso_weights(s):
        names = sp_names[:-1]                         # bones Pelvis..Neck own the segments; above the Head joint: Head
        if s >= cum_sp[-1] - BLEND:
            f = np.clip((s - (cum_sp[-1] - BLEND)) / (2 * BLEND), 0, 1)
            return {"Neck": 1 - f, "Head": f} if f < 1 else {"Head": 1.0}
        return chain_weights(cum_sp, s, names)

    limbs = {}
    for side in ("L", "R"):
        a = ch["arm"][side]
        kh_pts = np.array([J[i] for i in a])
        start = torso_map(kh_pts[0].copy())[0]
        ds_pts = np.array([start, dsr[f"{side}_UpperArm"], dsr[f"{side}_Forearm"], dsr[f"{side}_Hand"]])
        limbs["arm" + side] = dict(kh=kh_pts, kc=polyline(kh_pts), ds=ds_pts, dc=polyline(ds_pts),
                                   names=[f"{side}_Clavicle", f"{side}_UpperArm", f"{side}_Forearm"], end=f"{side}_Hand")
        l = ch["leg"][side]
        kh_pts = np.array([J[i] for i in l])
        start = torso_map(kh_pts[0].copy())[0]
        ds_pts = np.array([start, dsr[f"{side}_Calf"], dsr[f"{side}_Foot"]])
        limbs["leg" + side] = dict(kh=kh_pts, kc=polyline(kh_pts), ds=ds_pts, dc=polyline(ds_pts),
                                   names=[f"{side}_Thigh", f"{side}_Calf"], end=f"{side}_Foot",
                                   hip_band=0.12 if ch.get("pelvis_drop") else 0.0, thick=ch.get("leg_thick", 1.0))

    def limb_map(L, p):
        s_kh, off = project(L["kh"], L["kc"], p)
        f = s_kh / L["kc"][-1]
        s_ds = f * L["dc"][-1]
        q, seg, t = along(L["ds"], L["dc"], s_ds)
        # direction change between the KH segment and the DSR segment (both T-pose: small) – rotate the offset
        kd = L["kh"][min(seg + 1, len(L["kh"]) - 1)] - L["kh"][seg]
        dd = L["ds"][seg + 1] - L["ds"][seg]
        R = rot_between(kd, dd)
        extra = 0.0
        if s_kh < 0 or s_kh > L["kc"][-1]:            # beyond the ends: keep the overhang at scale K
            extra = (s_kh - np.clip(s_kh, 0, L["kc"][-1])) * K
            q = q + extra * dd / (np.linalg.norm(dd) + 1e-12)
        w = chain_weights(L["dc"], np.clip(s_ds, 0, L["dc"][-1]), L["names"])
        if L.get("hip_band") and s_ds < L["hip_band"]:   # dropped body: top of the leg rides with the pelvis
            f3 = np.clip(s_ds / L["hip_band"], 0, 1)
            w = {**{k: v * f3 for k, v in w.items()}, "Pelvis": 1 - f3}
        if s_ds >= L["dc"][-1] - BLEND:               # into the hand / foot
            f2 = np.clip((s_ds - (L["dc"][-1] - BLEND)) / BLEND, 0, 1)
            w = {**{k: v * (1 - f2) for k, v in w.items()}, L["end"]: f2}
        return q + K * L.get("thick", 1.0) * (R @ off), w

    hd = J[ch["head"]]
    tail_root = [torso_map(J[next(b for b, r in ch["regions"].items() if r == "tail")].copy())[0]] \
        if "tail" in ch["regions"].values() else [None]
    fixes = []
    for b, axis, deg in ch.get("bind_fix", []) + (fist_fixes(ch) if FIST else []):
        a = np.radians(deg); c, s_ = np.cos(a), np.sin(a)
        R = {"x": np.array([[1, 0, 0], [0, c, -s_], [0, s_, c]]),
             "y": np.array([[c, 0, s_], [0, 1, 0], [-s_, 0, c]]),
             "z": np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]])}[axis]
        pivot = d["link"][byi[b]][:3, 3] if byi[b] in d["link"] else B[byi[b]]["glob"][:3, 3]
        sub = {b}
        grew = True
        while grew:                                   # the whole subtree (an ear is a chain of bones)
            grew = False
            for i, pi in parent.items():
                if pi in sub and i not in sub:
                    sub.add(i); grew = True
        fixes.append(({byi[i] for i in sub}, R, pivot))
    rigid = {}
    for b, name in ch.get("rigid", {}).items():
        sub = {b}; grew = True
        while grew:
            grew = False
            for i, pi in parent.items():
                if pi in sub and i not in sub:
                    sub.add(i); grew = True
        rigid[frozenset(byi[i] for i in sub)] = name
    out_pos, out_w = [], []
    for m in d["meshes"]:
        P = np.empty((len(m["V"]), 3)); Wd = []
        for vi, (v, wts) in enumerate(zip(m["V"], m["W"])):
            for bo, R, pivot in fixes:                # KH space (cm), before the axis conversion
                w = sum(ww for o, ww in wts.items() if o in bo)
                if w > 0:
                    v = (1 - w) * v + w * (pivot + R @ (v - pivot))
            p = conv(v)
            acc, accw, tot = np.zeros(3), {}, 0.0
            reg_w = {}
            for o, ww in wts.items():
                reg_w.setdefault(region(idx[o]), []).append((idx[o], ww))
            for reg, lst in reg_w.items():
                rw = sum(w for _, w in lst)
                if reg in ("torso", "tail"):
                    q, s = torso_map(p.copy())
                    bw = {"Pelvis": 1.0} if reg == "tail" else torso_weights(s)
                    if reg == "tail" and ch.get("tail_k"):  # v108: tail scaled about its root
                        tr = tail_root[0]
                        q = tr + ch["tail_k"] * (q - tr)
                elif reg == "head":
                    q = dsr["Head"] + K * ch.get("head_k", 1.0) * (p - hd) + np.array(ch.get("head_offset", (0, 0, 0)))
                    bw = {"Head": 1.0}
                elif reg.startswith(("arm", "leg")):
                    q, bw = limb_map(limbs[reg], p)
                elif reg.startswith("hand"):
                    side = reg[-1]
                    q = dsr[f"{side}_Hand"] + K * (p - J[ch["arm"][side][-1]])
                    bw = {}
                    for i, w in lst:
                        # v112 (in-game v111 screenshot: both gloves broken into spiky shards): the human grip pose
                        # bends KH2 finger geometry around human finger joints that sit elsewhere -> gloves ride the
                        # hand bone only (KH2 bind-pose glove shape kept)
                        n = f"{side}_Hand" if RIGID_HANDS else ch["fingers"].get(i, f"{side}_Hand")
                        bw[n] = bw.get(n, 0) + w
                elif reg.startswith("foot"):
                    side = reg[-1]
                    ank = J[ch["leg"][side][-1]]
                    rel = p - ank
                    q = dsr[f"{side}_Foot"] + K * rel
                    if rel[1] < 0:                    # below the ankle: stretch down to the ground
                        q[1] = dsr[f"{side}_Foot"][1] * (p[1] / max(ank[1], 1e-6))
                    bw = {}
                    for i, w in lst:
                        n = f"{side}_Toe0" if i in ch["toe"][side] else f"{side}_Foot"; bw[n] = bw.get(n, 0) + w
                tb = sum(bw.values())
                acc += rw * q; tot += rw
                for n, w in bw.items():
                    accw[n] = accw.get(n, 0) + rw * w / tb
            P[vi] = acc / tot
            wd = {n: w / tot for n, w in accw.items()}
            if ch.get("head_on_neck") and "Head" in wd:   # v104: KH2 head rides the Neck bone (see CHARS)
                wd["Neck"] = wd.get("Neck", 0.0) + wd.pop("Head")
            for rb, rname in rigid.items():
                if sum(ww for o, ww in wts.items() if o in rb) > 0.5:
                    wd = {rname: 1.0}
            Wd.append(wd)
        fs = ch.get("face_scale")
        if fs:
            hj = dsr["Head"]
            for vi, wd in enumerate(Wd):
                w = wd.get("Head", 0.0)
                if w > 0:
                    c = 1.0 / (1.0 - w + w * fs)          # undo the in-game squash for this vertex's Head share
                    P[vi, 1] = hj[1] + (P[vi, 1] - hj[1]) * c
                    P[vi, 2] = hj[2] + (P[vi, 2] - hj[2]) * c
        out_pos.append(P); out_w.append(Wd)
    if GLOVE_TO_GRIP:
        glove_to_grip(out_pos, out_w, dsr)
    return out_pos, out_w, K


# v114 (in-game v113 screenshot: "the weapon sits in their wrists, not their hands"): the game attaches weapons at the
# human L/R_Weapon bone (6 cm past the hand joint); the KH2 glove is bigger, so its fist sat ~9-10 cm further out. Each
# glove slides back along the arm (vertices move by their share of the Hand weight) until the fist's centre lies on the
# Weapon bone; the cuff slides into the sleeve.
GLOVE_TO_GRIP = True


def glove_to_grip(pos, wts, dsr):
    for s in "LR":
        hand, grip = dsr[f"{s}_Hand"], dsr[f"{s}_Weapon"]
        P = np.vstack([p[[i for i, w in enumerate(wl) if w.get(f"{s}_Hand", 0) > 0.99]] for p, wl in zip(pos, wts)])
        reach = np.abs(P[:, 0] - hand[0])
        far = P[reach > 0.6 * reach.max()]
        centre = (far.max(0) + far.min(0)) / 2
        shift = np.array([grip[0] - centre[0], 0.0, 0.0])          # along the arm only (T-pose: arm = X)
        for p, wl in zip(pos, wts):
            for i, w in enumerate(wl):
                h = w.get(f"{s}_Hand", 0.0)
                if h > 0:
                    p[i] += h * shift
        print(f"  glove {s}: moved {shift[0]:+.3f} m along the arm to the weapon grip")


# v113 (in-game v112: "the gloves look clean but their hands are open, not holding their items"): with RIGID_HANDS the
# gloves keep the KH2 bind pose (open, palm down, fingers along the arm). The KH2 fingers are curled into a fist once
# here, about their own KH2 joints: fingers about the forearm's side axis (KH2 Z; left hand points +X -> negative
# angle curls down, right hand mirrored), thumbs about KH2 X towards the palm. Tips first, so each joint turns about
# its rest position before its parent moves it.
FIST = True
FIST_DEG = {0: 65.0, 1: 70.0, 2: 50.0}          # finger segment -> degrees
THUMB_DEG = {0: 25.0, 1: 30.0, 2: 20.0}


def fist_fixes(ch):
    out = []
    for b, name in ch.get("fingers", {}).items():
        side, num = name[0], name.split("Finger")[1]
        seg = len(num) - 1
        if num[0] == "0":
            out.append((seg, b, "x", THUMB_DEG[seg]))
        else:
            out.append((seg, b, "z", -FIST_DEG[seg] if side == "L" else FIST_DEG[seg]))
    seen, res = set(), []
    for seg, b, axis, deg in sorted(out, key=lambda t: -t[0]):
        if b not in seen:
            seen.add(b); res.append((b, axis, deg))
    return res


def rot_between(a, b):
    a = a / (np.linalg.norm(a) + 1e-12); b = b / (np.linalg.norm(b) + 1e-12)
    v = np.cross(a, b); c = a @ b
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3) if c > 0 else -np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx * (1 / (1 + c))




# ---- v107 inner head cap --------------------------------------------------------------------------------------------
# In-game v106: the human face still showed through Donald's forehead and Goofy's face. Ray tests (head_cover.py) found
# the KH2 heads are open in places (between eyes / hat / snout) and Goofy's is narrower than a human skull, so no size
# or offset hides it. Every Dark Souls human renders the shared FaceGen face (FG_A_0000) + back of head (FC_*); this
# adds a closed convex cap 4 % larger than that head (measured from the user's own FG_A_0000 / FC_M_0000 / FC_A_9000),
# on the Head bone, painted with a flat patch of the character's head colour – where the KH2 head has a gap you see
# his colour instead of a human face.
SHELL_INFLATE = 1.04
RIGID_HANDS = True     # v112, see fit()


def human_head_points(game_parts):
    from soulstruct.containers import Binder
    from soulstruct.flver import FLVER
    pts = []
    for n in ("FC_M_0000", "FG_A_0000", "FC_A_9000"):
        b = Binder.from_path(os.path.join(game_parts, n + ".partsbnd.dcx"))
        f = FLVER.from_bytes(next(e for e in b.entries if e.path.endswith(".flver")).data)
        for m in f.meshes[:2]:
            pts.append(np.asarray(m.vertices["position"], float))
    return np.vstack(pts)


def add_head_shell(ch, d, pos, wts, human):
    from scipy.spatial import ConvexHull
    cfg = ch.get("head_shell")
    if not cfg:
        return 0
    c = (human.max(0) + human.min(0)) / 2
    pts = c + (human - c) * SHELL_INFLATE
    hull = ConvexHull(pts)
    used = np.unique(hull.simplices)
    remap = {int(v): i for i, v in enumerate(used)}
    V = pts[used]
    uv = np.array([cfg["uv"]] * 3)
    tris = []
    for s_ in hull.simplices:
        a, b, c3 = (remap[int(x)] for x in s_)
        n = np.cross(V[c3] - V[a], V[b] - V[a])        # front-face rule used everywhere in this tool
        if n @ (V[[a, b, c3]].mean(0) - c) < 0:
            b, c3 = c3, b
        tris.append((a, b, c3, uv, cfg["tex"]))
    d["meshes"].append(dict(name="head_shell", V=V, tris=tris, W=[{} for _ in V]))
    pos.append(V.copy()); wts.append([{"Head": 1.0} for _ in V])
    return len(tris)


# ---- game files --------------------------------------------------------------------------------------------------------
MAX_MESH_BONES = 28          # FLVER0 per-mesh bone palette limit (soulstruct FLVER0_MAX_BONE_COUNT)
SMOOTH_DEG = 60.0
W_SIGN = -1.0                # tangent handedness convention of the user's DSR parts (see make_keyblades.py)


def corners(d, pos, wts):
    """per-triangle-corner arrays: P (n,3,3), UV (n,3,2) with v flipped for DSR, W (n,3) dicts, texture per tri"""
    P, UV, W, TX = [], [], [], []
    for mi, m in enumerate(d["meshes"]):
        for a, b, c, uv, tex in m["tris"]:
            P.append(pos[mi][[a, b, c]]); UV.append([(u, 1.0 - v) for u, v in uv])
            W.append([wts[mi][a], wts[mi][b], wts[mi][c]]); TX.append(tex)
    return np.array(P), np.array(UV), W, TX


def normals_tangents(P, UV):
    n_t = len(P)
    fn = np.cross(P[:, 2] - P[:, 0], P[:, 1] - P[:, 0])            # mirror rule (see make_keyblades.py)
    fu = fn / (np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12)
    keys = [tuple(np.round(p, 4)) for p in P.reshape(-1, 3)]
    acc = {}
    for i, k in enumerate(keys):
        acc.setdefault(k, []).append(i // 3)
    cl = np.cos(np.radians(SMOOTH_DEG))
    N = np.zeros((n_t * 3, 3))
    for i, k in enumerate(keys):
        own = fu[i // 3]
        sel = [t for t in acc[k] if fu[t] @ own >= cl]
        v = fn[sel].sum(0)
        N[i] = v / (np.linalg.norm(v) + 1e-12) if np.linalg.norm(v) > 1e-12 else own
    Pf, Uf = P.reshape(-1, 3), UV.reshape(-1, 2)
    T = np.zeros((n_t * 3, 4))
    for t in range(n_t):
        i0, i1, i2 = 3 * t, 3 * t + 1, 3 * t + 2
        e1, e2 = Pf[i1] - Pf[i0], Pf[i2] - Pf[i0]
        d1, d2 = Uf[i1] - Uf[i0], Uf[i2] - Uf[i0]
        det = d1[0] * d2[1] - d2[0] * d1[1]
        Tg = (e1 * d2[1] - e2 * d1[1]) / det if abs(det) > 1e-12 else np.array([1.0, 0, 0])
        Bg = (e2 * d1[0] - e1 * d2[0]) / det if abs(det) > 1e-12 else np.array([0, 1.0, 0])
        for i in (i0, i1, i2):
            n = N[i]; tt = Tg - n * (n @ Tg)
            if np.linalg.norm(tt) < 1e-9:
                tt = np.cross(n, [0, 1, 0]) if abs(n[1]) < 0.9 else np.cross(n, [1, 0, 0])
            tt /= np.linalg.norm(tt)
            w = 1.0 if np.cross(n, tt) @ Bg >= 0 else -1.0
            T[i] = (*(np.cross(n, tt) * w), W_SIGN * w)
    return N, T, fu


def top4(wd):
    it = sorted(wd.items(), key=lambda t: -t[1])[:4]
    tot = sum(w for _, w in it)
    return [(n, w / tot) for n, w in it]


def dxt(png, fmt):
    img = Image.open(png).convert("RGBA")
    buf = io.BytesIO(); img.save(buf, "DDS", pixel_format=fmt)
    return buf.getvalue()


# v103 (in-game v102 screenshot: long bars from sleeves / shirt to the floor): every Sora part only carries a correct
# bind pose for the bones it skins itself (measured against the c0000 skeleton: HD's arm bones 1.4 m off, BD's head /
# hands / calves / feet 0.6-1.9 m off, LG's upper body 1.2-2.3 m off); the game skins with these, so Donald/Goofy
# vertices blended onto such a bone were dragged away. Sora's AM part is right for every deforming bone (within
# 12 mm; only nubs, weapon and shoulder-pad dummies differ), so its local bone transforms are copied by name into
# every part (same name AND same parent only).
# v104: off – in-game v103 still stretched; the real cause is the bone usage flag (see SAFE / safe_bones)
BIND_FIX = False
DEFORM_SKIP = ("Nub", "Weapon", "Shoulderpad", "Wepon", "Shield", "_Po", "bag_", "Arm_Root")


def fix_bind_pose(f, am_bones):
    n = 0
    for b in f.bones:
        src = am_bones.get(b.name)
        if src is None or any(k in b.name for k in DEFORM_SKIP):
            continue
        parent = f.bones[b.parent_bone_index].name if b.parent_bone_index >= 0 else None
        if parent != src[3]:
            continue
        if tuple(b.translate) != src[0] or tuple(b.rotate) != src[1] or tuple(b.scale) != src[2]:
            b.translate, b.rotate, b.scale = src[0], src[1], src[2]
            n += 1
    return n


def build_parts(who, d, pos, wts, work, sora_parts, out_dir, report=print, skel_path=None):
    import copy
    from soulstruct.containers import Binder
    from soulstruct.containers.tpf import TPF
    from soulstruct.flver import FLVER
    from fix_sora_normalmap import flat_dxt1
    ch = CHARS[who]; model = ch["model"]; pre = ch["tex_prefix"]
    sk = json.load(open(skel_path)); sk_names = [b["name"] for b in sk]
    P, UV, W, TX = corners(d, pos, wts)
    N, T, fu = normals_tangents(P, UV)
    # sanity: front faces point away from the body axis (torso height band)
    c = P.mean(1); band = (c[:, 1] > 1.0) & (c[:, 1] < 1.35)
    out = ((c[band] * [1, 0, 1]) - [0, 0, -0.04]) * [1, 0, 1]
    frac = float(np.mean(np.sum(fu[band] * out, 1) > 0))
    report(f"{who}: {len(P)} triangles; torso faces pointing outward {frac:.0%}")
    if frac < 0.5:
        raise RuntimeError("faces point inward – winding rule does not match this model")
    # v104 (in-game v103: still stretched; Sora's parts only ever use bones whose FLVER usage flag is 0): a part's bone
    # with usage flag 1 is a placeholder the game does not bind – vertices weighted to it fall to the character's
    # origin (the long bars to the floor). SAFE = the flag-0 bones of each template part (read from the user's files).
    for pc_, prefix_ in PARTS.items():
        tb = Binder.from_path(os.path.join(sora_parts, f"{prefix_}_9550.partsbnd.dcx"))
        tf = FLVER.from_bytes(next(e for e in tb.entries if e.path.endswith(".flver")).data)
        SAFE[pc_] = {x.name for x in tf.bones if x.usage_flags == 0 and x.name in sk_names}
        # v108 (in-game v107: left-arm stretch back): v107 was built from an older Sora template whose AM marks
        # L_Clavicle/L_UpperArm as bound (flag 0) – the game doesn't bind them. Only the deployed mod copy is verified.
        if pc_ == "AM":
            fl_ = {x.name: x.usage_flags for x in tf.bones}
            assert fl_.get("L_UpperArm") == 1 and fl_.get("L_Clavicle") == 1, \
                f"{sora_parts}: not the verified Sora template (L_UpperArm/L_Clavicle must be flag 1)"
    report("  usable bones per part: " + "; ".join(f"{k} {len(v)}" for k, v in SAFE.items()))
    dsr_parent = {b["name"]: (sk_names[b["parent"]] if b["parent"] >= 0 else None) for b in sk}
    def substitute(n, pc):
        """nearest bone of SAFE[pc]: walk up the parents, then down to the first safe child"""
        p = n
        while p is not None:
            if p in SAFE[pc]:
                return p
            p = dsr_parent.get(p)
        kids = [c for c, pa in dsr_parent.items() if pa == n and c in SAFE[pc]]
        return kids[0] if kids else sorted(SAFE[pc])[0]
    piece, moved, swapped = [], 0, 0
    for t, wc in enumerate(W):
        votes = {}
        for wd in wc:
            n = max(wd.items(), key=lambda q: q[1])[0]
            pc = PIECE.get(n, "BD"); votes[pc] = votes.get(pc, 0) + 1
        pc = max(votes.items(), key=lambda q: q[1])[0]
        bones = {n for wd in wc for n, _ in top4(wd)}
        if not bones <= SAFE[pc]:
            alt = [q for q in PIECE_ORDER if bones <= SAFE[q]]
            if alt:
                pc = alt[0]; moved += 1
            else:
                new = []
                for wd in wc:
                    nd = {}
                    for n, w in wd.items():
                        m2 = n if n in SAFE[pc] else substitute(n, pc)
                        nd[m2] = nd.get(m2, 0) + w
                    new.append(nd)
                W[t] = new; swapped += 1
        piece.append(pc)
    report(f"  bone safety: {moved} triangles moved to another part, {swapped} with a bone substituted")
    os.makedirs(out_dir, exist_ok=True)
    written = []
    am = FLVER.from_bytes(next(e for e in Binder.from_path(os.path.join(sora_parts, "AM_A_9550.partsbnd.dcx")).entries
                               if e.path.endswith(".flver")).data)
    am_bones = {b.name: (tuple(b.translate), tuple(b.rotate), tuple(b.scale),
                         am.bones[b.parent_bone_index].name if b.parent_bone_index >= 0 else None) for b in am.bones}
    for pc, prefix in PARTS.items():
        tmpl_stem = f"{prefix}_9550"; stem = f"{prefix}_{model}"
        b = Binder.from_path(os.path.join(sora_parts, tmpl_stem + ".partsbnd.dcx"))
        fe = next(e for e in b.entries if e.path.endswith(".flver"))
        te = next(e for e in b.entries if e.path.endswith(".tpf"))
        f = FLVER.from_bytes(fe.data)
        fixed = fix_bind_pose(f, am_bones) if BIND_FIX else 0
        tm = f.meshes[0]
        bone_ix = {}
        for i, bn in enumerate(f.bones):
            bone_ix.setdefault(bn.name, i)
        tris = [t for t in range(len(P)) if piece[t] == pc]
        meshes = []
        for tex in sorted(set(TX[t] for t in tris)):
            group = [t for t in tris if TX[t] == tex]
            chunks, cur, cur_b = [], [], set()
            for t in group:
                tb = {n for wd in W[t] for n, _ in top4(wd)}
                if len(cur_b | tb) > MAX_MESH_BONES:
                    chunks.append(cur); cur, cur_b = [], set()
                cur.append(t); cur_b |= tb
            if cur:
                chunks.append(cur)
            for chunk in chunks:
                names = sorted({n for t in chunk for wd in W[t] for n, _ in top4(wd)}, key=lambda n: bone_ix[n])
                local = {n: i for i, n in enumerate(names)}
                v = np.zeros(len(chunk) * 3, dtype=tm.vertices.dtype)
                for k, t in enumerate(chunk):
                    for j in range(3):
                        r = 3 * k + j; i = 3 * t + j
                        v["position"][r] = P[t, j]; v["normal"][r] = N[i]; v["tangent_0"][r] = T[i]
                        v["uv_0"][r] = UV[t, j]
                        tw = top4(W[t][j])
                        bi = [local[n] for n, _ in tw] + [0] * (4 - len(tw))
                        bw = [w for _, w in tw] + [0.0] * (4 - len(tw))
                        v["bone_indices"][r] = bi; v["bone_weights"][r] = bw
                v["normal_w"], v["color_0"] = 127, 1.0
                key = np.round(np.hstack([v["position"], v["normal"], v["uv_0"], v["bone_weights"],
                                          v["bone_indices"].astype(float)]), 5)
                _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
                m = copy.deepcopy(tm)
                m.vertex_arrays[0].array = v[first]
                m.face_sets[0].vertex_indices = inv.reshape(-1, 3).astype(m.face_sets[0].vertex_indices.dtype)
                del m.face_sets[1:]
                assert set(names) <= SAFE[pc], (stem, set(names) - SAFE[pc])
                assert all(f.bones[bone_ix[n]].usage_flags == 0 for n in names), stem
                m.bone_indices = [bone_ix[n] for n in names]
                m.is_dynamic = True
                mat = copy.deepcopy(tm.material)
                mat.name = f"{pre}_{tex}"
                for tx in mat.textures:
                    if tx.texture_type == "g_Diffuse":
                        tx.path = f"{pre}_{tex}.tga"
                    elif tx.texture_type == "g_Specular":
                        tx.path = f"{pre}_s.tga"
                    elif tx.texture_type == "g_Bumpmap":
                        tx.path = f"{pre}_n.tga"
                m.material = mat
                m.refresh_bounding_boxes()
                meshes.append(m)
        f.meshes = meshes
        for bn in f.bones:
            bn.name = bn.name.replace(tmpl_stem, stem)
        if hasattr(f, "refresh_bounding_boxes"):
            f.refresh_bounding_boxes()
        tpf = TPF.from_bytes(te.data)
        diff = next(t for t in tpf.textures if t.format == 5)
        nrm = next(t for t in tpf.textures if t.stem.endswith("_n"))
        spec = next(t for t in tpf.textures if t.stem.endswith("_s") and t.stem.count("_") == 1)
        new = []
        for tex in sorted(set(TX[t] for t in tris)):
            x = copy.deepcopy(diff); x.stem = f"{pre}_{tex}"; x.data = dxt(os.path.join(work, tex + ".png"), "DXT5"); x.format = 5
            new.append(x)
        x = copy.deepcopy(nrm); x.stem = f"{pre}_n"; x.data = flat_dxt1(); x.format = 0; new.append(x)
        x = copy.deepcopy(spec); x.stem = f"{pre}_s"; new.append(x)        # Sora's flat specular, renamed
        tpf.textures = new
        fe.data = f.to_bytes()
        te.set_from_binary_file(tpf)
        for e in b.entries:
            e.path = e.path.replace(tmpl_stem, stem)
        b.write(os.path.join(out_dir, stem + ".partsbnd.dcx")); written.append(stem)
        fe.path = fe.path[: -len(".flver")] + "_M.flver"
        b.write(os.path.join(out_dir, stem + "_M.partsbnd.dcx"))
        if prefix == "LG_M":                          # legs exist per body type: female copy for Donald (Gender 0)
            for e in b.entries:
                e.path = e.path.replace("LG_M_", "LG_F_")
            fe.path = fe.path.replace("_M.flver", ".flver")
            b.write(os.path.join(out_dir, f"LG_F_{model}.partsbnd.dcx"))
            fe.path = fe.path[: -len(".flver")] + "_M.flver"
            b.write(os.path.join(out_dir, f"LG_F_{model}_M.partsbnd.dcx"))
        report(f"  {stem}: bind pose fixed on {fixed} bones; {len(meshes)} meshes, {sum(len(m.vertices) for m in meshes)} vertices, "
               f"{len(tris)} triangles, textures {[t.stem for t in new]}")
    return written


# ---- preview ---------------------------------------------------------------------------------------------------------
def triangles(d, pos, textures):
    """flat list of (3x3 positions, colour, mesh index, corner vertex ids, uvs)"""
    out = []
    for mi, m in enumerate(d["meshes"]):
        img = textures.get(m["tris"][0][4]) if m["tris"] else None
        for a, b, c, uv, tex in m["tris"]:
            im = textures.get(tex)
            col = (0.7, 0.7, 0.7)
            if im is not None:
                u, v = uv.mean(0); h, w = im.shape[:2]
                col = im[int(np.clip((1 - v % 1) * h, 0, h - 1)), int(np.clip((u % 1) * w, 0, w - 1)), :3] / 255.0
            out.append((pos[mi][[a, b, c]], col, mi, (a, b, c), uv))
    return out


def render(tris, path, title, views=(("front", 0), ("side", 90)), joints=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    fig, axes = plt.subplots(1, len(views), figsize=(6 * len(views), 9))
    light = np.array([0.3, 0.5, -0.8]); light /= np.linalg.norm(light)
    for ax, (name, yaw) in zip(np.atleast_1d(axes), views):
        r = np.radians(yaw)
        Ry = np.array([[np.cos(r), 0, np.sin(r)], [0, 1, 0], [-np.sin(r), 0, np.cos(r)]])
        polys, cols, depth = [], [], []
        for P, col, *_ in tris:
            Q = P @ Ry.T
            n = np.cross(Q[2] - Q[0], Q[1] - Q[0])          # front face normal (mirror rule, see module notes)
            nn = n / (np.linalg.norm(n) + 1e-12)
            if nn[2] > 0:                                    # camera looks along +z from -z (DSR front = -Z)
                continue
            shade = 0.45 + 0.55 * max(0.0, -(nn @ light))
            polys.append(Q[:, :2]); cols.append(np.clip(np.array(col) * shade, 0, 1)); depth.append(Q[:, 2].mean())
        order = np.argsort(depth)[::-1]
        ax.add_collection(PolyCollection([polys[i] for i in order], facecolors=[cols[i] for i in order],
                                         edgecolors=[cols[i] for i in order], linewidths=0.3, antialiased=False))
        if joints is not None:
            Jq = joints @ Ry.T
            ax.scatter(Jq[:, 0], Jq[:, 1], s=6, c="red", zorder=5)
        ax.set_xlim(-1.0, 1.0); ax.set_ylim(-0.05, 2.1); ax.set_aspect("equal"); ax.set_title(f"{title} – {name}")
        ax.axhline(0, color="#888", lw=0.5)
    fig.tight_layout(); fig.savefig(path, dpi=90); plt.close(fig)


def main_preview(who, work, skel_path, out_dir):
    ch = CHARS[who]
    d = kh_fbx.load(os.path.join(work, ch["fbx"]))
    dsr, sk = load_dsr(skel_path)
    pos, wts, K = fit(ch, d, dsr)
    textures = {f"Texture000{i}": np.asarray(Image.open(os.path.join(work, f"Texture000{i}.png")).convert("RGBA"))
                for i in range(3) if os.path.exists(os.path.join(work, f"Texture000{i}.png"))}
    tris = triangles(d, pos, textures)
    os.makedirs(out_dir, exist_ok=True)
    joints = np.array([dsr[n] for n in dsr])
    render(tris, os.path.join(out_dir, f"{who}_fit.png"), f"{who} on DSR skeleton (K={K:.2f})", joints=joints)
    posed = pose_test(pos, wts, dsr, sk)
    render(triangles(d, posed, textures), os.path.join(out_dir, f"{who}_posed.png"), f"{who} pose test")
    walked = pose_test(pos, wts, dsr, sk, walk=True)
    render(triangles(d, walked, textures), os.path.join(out_dir, f"{who}_walk.png"), f"{who} walk test")
    allp = np.vstack(pos)
    print(f"{who}: K={K:.3f} height {allp[:,1].max():.2f} m, lowest {allp[:,1].min():.3f} m, width {np.ptp(allp[:,0]):.2f} m")
    return d, pos, wts, K


def pose_test(pos, wts, dsr, sk, walk=False):
    """Linear-blend skinning test on the DSR skeleton: arms down 70 deg, left elbow 70 deg, right knee 60 deg."""
    names = [b["name"] for b in sk]; par = {b["name"]: (names[b["parent"]] if b["parent"] >= 0 else None) for b in sk}
    def rot(axis, deg):
        a = np.radians(deg); c, s_ = np.cos(a), np.sin(a)
        return {"x": np.array([[1, 0, 0], [0, c, -s_], [0, s_, c]]), "z": np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]])}[axis]
    local = {"L_UpperArm": rot("z", -70), "R_UpperArm": rot("z", 70), "L_Forearm": rot("x", 70), "R_Calf": rot("x", -60)}
    if walk:      # stride: left thigh forward, right thigh back + knee bend, head turned
        local = {"L_UpperArm": rot("z", -70), "R_UpperArm": rot("z", 70), "L_Thigh": rot("x", 30),
                 "R_Thigh": rot("x", -25), "R_Calf": rot("x", -45), "Neck": rot("x", 20)}
    world = {}
    def W(n):
        if n in world:
            return world[n]
        M = np.eye(4)
        if n in local:
            j = dsr[n]; T = np.eye(4); T[:3, :3] = local[n]; T[:3, 3] = j - local[n] @ j
            M = T
        world[n] = (W(par[n]) @ M) if par[n] else M
        return world[n]
    out = []
    for P, Wd in zip(pos, wts):
        Q = np.zeros_like(P)
        for i, (p, wd) in enumerate(zip(P, Wd)):
            for n, w in wd.items():
                Q[i] += w * (W(n)[:3, :3] @ p + W(n)[:3, 3])
        out.append(Q)
    return out


if __name__ == "__main__":
    # python kh_party_model.py <who> <work dir> <dsr skeleton json> <preview dir> [<Sora parts dir> <out parts dir>]
    d, pos, wts, K = main_preview(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    if len(sys.argv) > 6:
        if len(sys.argv) > 7:                         # v107: <game parts dir> for the human head cap
            n = add_head_shell(CHARS[sys.argv[1]], d, pos, wts, human_head_points(sys.argv[7]))
            print(f"  head cap: {n} triangles")
        build_parts(sys.argv[1], d, pos, wts, sys.argv[2], sys.argv[5], sys.argv[6], skel_path=sys.argv[3])
