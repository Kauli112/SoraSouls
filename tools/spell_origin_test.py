"""SoraSouls – spell origin research, tests v38/v39: which BODY dummy poly do spells launch from?

Known (in-game 2026-10-05): moving the Keyblade's own dummies (WP_A_1311 dummy 110, WP_A_1312 dummy 120) to the tip
changed nothing – spells leave the casting HAND. The Bullet row has no dummy field (OriginType 0) and the cast TAEs
have no bullet event, so the origin must be a dummy of the player body model c0000.flver (chr/c0000.chrbnd.dcx).
c0000.flver has 201 dummies; the right-hand candidates sit on bone R_Weapon / R_Hand at the hand (bind pose: hand at
x -0.74, weapon axis = -Z; Kingdom Key tip = 0.77 m along it, from WP_A_0204 dummy 100). Body dummy 100 already sits
at the tip, so it is NOT the origin.

Test: three groups of right-hand dummies are moved to three different, easy-to-tell spots (bind pose):
  TIP   (z = -0.79, the Keyblade tip): 1, 18, 20, 22
  ABOVE (y + 0.5 m):                    24, 25, 99, 26
  BELOW (y - 0.4 m):                    43, 17, 55, 120, 45, 110, 111, 121
Where the spell appears tells which group holds the origin; the next test splits that group. Side effects of a moved
dummy (a weapon effect or trail out of place, an item-use effect) are expected and tell us more – note them.
In-place float patch of the dummy records (FLVER2: 0x40-byte records from 0x80, translate = first 3 floats,
reference id = int16 at +0x1C); all other bytes and binder entries stay identical (verified).
Usage: python spell_origin_test.py <vanilla c0000.chrbnd.dcx> <mod chr dir>
"""
import os, sys, struct
from soulstruct.containers import Binder

TIP_Z = -0.79
# v38 (in-game 2026-10-07): spells left the Keyblade TIP -> the origin is in the TIP group {1, 18, 20, 22}; the
# Keyblade itself also moved out of the hand (its attach point is in that group too); the cast glow stayed on the hand.
# v39 splits the TIP group: one dummy per spot, 1 stays. Spell spot = origin, Keyblade spot = attach point.
GROUPS = {"TIP": (18,), "ABOVE": (20,), "BELOW": (22,)}


def patch_flver(d):
    d = bytearray(d)
    if d[:6] != b"FLVER\0" or d[6:8] != b"L\0":
        raise RuntimeError("not a little-endian FLVER")
    count = struct.unpack_from("<i", d, 0x14)[0]
    moved = {}
    for k in range(count):
        o = 0x80 + 0x40 * k
        ref = struct.unpack_from("<h", d, o + 0x1C)[0]
        x, y, z = struct.unpack_from("<3f", d, o)
        for g, ids in GROUPS.items():
            if ref in ids:
                if ref in moved:
                    raise RuntimeError(f"dummy {ref} appears twice")
                new = (x, y, TIP_Z) if g == "TIP" else (x, y + 0.5, z) if g == "ABOVE" else (x, y - 0.4, z)
                struct.pack_into("<3f", d, o, *new)
                moved[ref] = (g, (round(x, 3), round(y, 3), round(z, 3)), tuple(round(v, 3) for v in new))
    missing = [i for ids in GROUPS.values() for i in ids if i not in moved]
    if missing:
        raise RuntimeError(f"dummies not found: {missing}")
    return bytes(d), moved


def main(src, out_dir):
    van = {e.entry_id: bytes(e.data) for e in Binder.from_path(src).entries}
    b = Binder.from_path(src)
    e = [x for x in b.entries if x.name.endswith(".flver")][0]
    e.data, moved = patch_flver(bytes(e.data))
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, os.path.basename(src))
    b.write(out)
    chk = {x.entry_id: bytes(x.data) for x in Binder.from_path(out).entries}
    assert [i for i in chk if chk[i] != van[i]] == [e.entry_id]
    a, c = van[e.entry_id], chk[e.entry_id]
    assert len(a) == len(c) and sum(1 for i in range(len(a)) if a[i] != c[i]) <= 12 * len(moved)
    for ref, (g, old, new) in sorted(moved.items()):
        print(f"dummy {ref:3d} {g:5s} {old} -> {new}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
