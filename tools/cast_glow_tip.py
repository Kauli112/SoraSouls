"""SoraSouls – cast glow at the Keyblade tip (v42, v43).

Facts (a00.tae, tools/tae32.py, 2026-10-07):
  * Release animations fire the spell with TAE event 64, first int = body dummy: 1 for the right hand (65xx),
    3 for the left (64xx). That is why moving body dummy 1 to the tip (tools/spell_tip.py, v41) moved the spells.
  * The wind-up glow is TAE event 114 (int sfx id 200, int16 0, int16 body dummy): right-hand wind-ups 63xx use
    dummy 24 (6318 uses 22), a few 65xx releases also 24; left-hand 62xx use 23/27.
This repoints every right-hand cast glow (event 114 in 63xx/65xx, dummy 22 or 24) to dummy 1, which already sits at
the Keyblade tip – no other dummy has to move. Same-size in-place patch of one int16 per event; everything else in
c0000.anibnd stays identical (verified).
Usage: python cast_glow_tip.py <vanilla c0000.anibnd.dcx> <mod chr dir>
"""
import os, sys, struct
from soulstruct.containers import Binder
from tae32 import TAE32

# v43 (in-game 2026-10-07: "glow starts at the tip then teleports back to the hand at the end"): the release anims
# re-spawn the glow with event 115 (same payload, dummy 24/22), and 6510 flashes sfx 201 at hand dummy 18 -> both added.
GLOW_EVENTS, FROM_DUMMIES, TO_DUMMY = (114, 115), (18, 22, 24), 1


def patch_tae(data, name):
    t = TAE32.parse(data)
    out = bytearray(data)
    hits = []
    for a in t.animations:
        if not (6300 <= a.id < 6400 or 6500 <= a.id < 6600):
            continue
        for ev in a.events:
            if ev.type not in GLOW_EVENTS or ev.data_offset < 0:
                continue
            dmy = struct.unpack_from("<h", out, ev.data_offset + 6)[0]
            if dmy in FROM_DUMMIES:
                struct.pack_into("<h", out, ev.data_offset + 6, TO_DUMMY)
                hits.append((a.id, ev.type, dmy))
    if hits:
        chk = TAE32.parse(bytes(out))
        assert len(chk.animations) == len(t.animations)
        print(f"{name}: {len(hits)} glow events -> dummy {TO_DUMMY}: {hits}")
    return bytes(out), len(hits)


def main(src, out_dir):
    van = {e.entry_id: bytes(e.data) for e in Binder.from_path(src).entries}
    b = Binder.from_path(src)
    changed = []
    for e in b.entries:
        if e.name.endswith(".tae"):
            new, n = patch_tae(bytes(e.data), e.name.split("\\")[-1])
            if n:
                e.data = new
                changed.append(e.entry_id)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, os.path.basename(src))
    b.write(out)
    chk = {x.entry_id: bytes(x.data) for x in Binder.from_path(out).entries}
    diff = [i for i in chk if chk[i] != van[i]]
    assert diff == changed, (diff, changed)
    for i in diff:
        assert len(chk[i]) == len(van[i])
    print(f"wrote {out}: {len(diff)} TAE entries changed, {len(chk) - len(diff)} identical")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
