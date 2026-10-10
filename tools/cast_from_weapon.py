"""SoraSouls – spells from the CURRENT Keyblade's tip (v68 experiment). User 2026-10-08: "the spells are coming from
the tip of where the Kingdom Key is, not the tip of the current Keyblade".

Why: since v41 the right-hand cast origin is BODY dummy 1, moved to the Kingdom Key's tip (0.76 m) – one fixed point,
but the Keyblades are 0.85-1.4 m long. Every Keyblade model has its own tip dummy 100 (make_keyblades.py scales it).
Experiment: point the right-hand cast event (TAE 64, first int 1) and the cast glow (114/115, int16 dummy 1) at
10100 – the "right-hand weapon dummy 100" form (weapon dummies = 10000 + id). That this form works in DSR is NOT
known; in-game test decides. If spells then come from the wrong place, revert to the previous anibnd.
Same-size in-place patch; only anims 63xx/65xx; everything else in c0000.anibnd stays identical (verified).
Usage: python cast_from_weapon.py <current mod c0000.anibnd.dcx> <out dir>
"""
import os, struct, sys
from soulstruct.containers import Binder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tae32 import TAE32

FROM, TO = 1, 10100


def patch(data):
    t = TAE32.parse(data)
    out = bytearray(data)
    hits = []
    for a in t.animations:
        if not (6300 <= a.id < 6400 or 6500 <= a.id < 6600):
            continue
        for ev in a.events:
            if ev.data_offset < 0:
                continue
            if ev.type == 64 and struct.unpack_from("<i", out, ev.data_offset)[0] == FROM:
                struct.pack_into("<i", out, ev.data_offset, TO); hits.append((a.id, 64))
            elif ev.type in (114, 115) and struct.unpack_from("<h", out, ev.data_offset + 6)[0] == FROM:
                struct.pack_into("<h", out, ev.data_offset + 6, TO); hits.append((a.id, ev.type))
    return bytes(out), hits


def main(src, out_dir):
    b = Binder.from_path(src)
    van = {e.entry_id: bytes(e.data) for e in b.entries}
    changed = []
    for e in b.entries:
        if e.name.endswith(".tae"):
            new, hits = patch(bytes(e.data))
            if hits:
                e.data = new; changed.append(e.entry_id)
                print(e.name.split("\\")[-1], len(hits), "events ->", TO, sorted(set(hits)))
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, os.path.basename(src))
    b.write(out)
    chk = {x.entry_id: bytes(x.data) for x in Binder.from_path(out).entries}
    diff = [i for i in chk if chk[i] != van[i]]
    assert diff == changed and all(len(chk[i]) == len(van[i]) for i in diff)
    print(f"wrote {out}: {len(diff)} TAE entries changed")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
