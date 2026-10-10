"""SoraSouls – spells from the Keyblade tip (v40). User choice 2026-10-07: "Tip, Keyblade only".

Findings (tools/spell_origin_test.py, v38/v39 in-game): body dummy 1 of c0000.flver (bone R_Weapon, at the right
hand) is BOTH the right-hand spell origin AND the point the right-hand weapon model is attached to.
So this moves dummy 1 forward along the weapon axis to the Kingdom Key's tip (bind pose -Z, TIP_SHIFT m) and moves the
Kingdom Key model (WP_A_0204: mesh + all its dummies, weapon axis -Y) back by the same distance, so the Keyblade still
sits in Sora's hand while spells leave its tip. Hit/trail dummies move with the mesh, so attacks stay aligned.
Trade-off (accepted): every OTHER right-hand weapon model now sits TIP_SHIFT m in front of the hand.
The collapsed sheath model WP_A_0204_1.flver is left alone.
In-game v40 (2026-10-07): spells left the tip and casting was fixed, BUT the Keyblade's TIP sat in Sora's hand – the
model was displaced by exactly the mesh shift, i.e. moving body dummy 1 did NOT move the weapon. So dummy 1 is only
the spell origin (the v38 "Keyblade out of the hand" came from the other moved dummies, 18/20/22 together).
v41: SHIFT_WEAPON = False – the Kingdom Key model stays untouched, only dummy 1 moves (other weapons unaffected).
Usage: python spell_tip.py <vanilla c0000.chrbnd.dcx> <mod WP_A_0204.partsbnd.dcx> <out mod dir>
"""
import os, sys, struct
import numpy as np
from soulstruct.containers import Binder
from soulstruct.flver import FLVER

TIP_SHIFT = 0.76   # m: Kingdom Key dummy 100 (tip) is 0.77 m out along -Y; body dummy 1 sits 0.03 m off the hand
DUMMY = 1
SHIFT_WEAPON = False   # v40 True (wrong: weapon is not attached at dummy 1)


def patch_body(src, out_dir):
    van = {e.entry_id: bytes(e.data) for e in Binder.from_path(src).entries}
    b = Binder.from_path(src)
    e = next(x for x in b.entries if x.name.endswith(".flver"))
    d = bytearray(e.data)
    n = struct.unpack_from("<i", d, 0x14)[0]
    hits = [0x80 + 0x40 * k for k in range(n) if struct.unpack_from("<h", d, 0x80 + 0x40 * k + 0x1C)[0] == DUMMY]
    if len(hits) != 1:
        raise RuntimeError(f"expected one body dummy {DUMMY}, found {len(hits)}")
    x, y, z = struct.unpack_from("<3f", d, hits[0])
    fx, fy, fz = struct.unpack_from("<3f", d, hits[0] + 0x10)
    if abs(fx) > 1e-6 or abs(fy) > 1e-6 or fz >= 0:
        raise RuntimeError("dummy 1 forward vector is not -Z – weapon axis assumption broken")
    struct.pack_into("<3f", d, hits[0], x, y, z - TIP_SHIFT)
    e.data = bytes(d)
    os.makedirs(os.path.join(out_dir, "chr"), exist_ok=True)
    out = os.path.join(out_dir, "chr", os.path.basename(src))
    b.write(out)
    chk = {x.entry_id: bytes(x.data) for x in Binder.from_path(out).entries}
    assert [i for i in chk if chk[i] != van[i]] == [e.entry_id]
    a, c = van[e.entry_id], chk[e.entry_id]
    assert len(a) == len(c) and [i for i in range(len(a)) if a[i] != c[i]][-1] < hits[0] + 12
    print(f"body dummy {DUMMY}: z {z:.3f} -> {z - TIP_SHIFT:.3f}  ({out})")


def patch_weapon(src, out_dir):
    b = Binder.from_path(src)
    done = 0
    for e in b.entries:
        if not e.path.lower().endswith("wp_a_0204.flver"):
            continue
        f = FLVER.from_bytes(e.data)
        tip_before = next(dm for dm in f.dummies if dm.reference_id == 100).translate[1]
        for m in f.meshes:
            m.vertices["position"][:, 1] += TIP_SHIFT
            if hasattr(m, "refresh_bounding_boxes"):
                m.refresh_bounding_boxes()
        for dm in f.dummies:
            t = list(dm.translate); t[1] += TIP_SHIFT; dm.translate = type(dm.translate)(t) if not isinstance(dm.translate, list) else t
        e.data = f.to_bytes()
        chk = FLVER.from_bytes(e.data)
        tip_after = next(dm for dm in chk.dummies if dm.reference_id == 100).translate[1]
        ys = np.concatenate([m.vertices["position"][:, 1] for m in chk.meshes])
        print(f"WP_A_0204.flver: tip y {tip_before:.3f} -> {tip_after:.3f}, mesh y {ys.min():.3f}..{ys.max():.3f}")
        done += 1
    if done != 1:
        raise RuntimeError("WP_A_0204.flver not found")
    os.makedirs(os.path.join(out_dir, "parts"), exist_ok=True)
    out = os.path.join(out_dir, "parts", os.path.basename(src))
    b.write(out)
    print("wrote", out)


if __name__ == "__main__":
    patch_body(sys.argv[1], sys.argv[3])
    if SHIFT_WEAPON:
        patch_weapon(sys.argv[2], sys.argv[3])
