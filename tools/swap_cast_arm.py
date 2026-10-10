"""SoraSouls – seamless casting v2, step 1: Sora casts with his Keyblade (right) arm when casting from the
left-hand Keyblade Focus (L1).

Spell casts (decompiled c0000.esd): each magic anim type NN plays a wind-up 62NN/63NN (upper body) and a release
64NN/65NN (full body), arm chosen by "+ IsRightHandMagic()*100": 62xx/64xx = LEFT hand, 63xx/65xx = RIGHT hand.
v22 had this backwards (swapped 63xx <- 62xx); v23 swaps both phases the right way round.
HKX motion lives in chr/c0000_a00_md.anibnd.dcx. This writes a MOD copy of that binder in which every left-hand cast
motion a00_62NN / a00_64NN is replaced by its right-hand twin a00_63NN / a00_65NN (same NN). TAE events (timing, spell trigger) are untouched, and every other
animation stays byte-identical (verified). The vanilla file in the game folder is never modified.
Usage: python swap_cast_arm.py <vanilla c0000_a00_md.anibnd.dcx> <mod chr dir>
"""
import os, sys
from soulstruct.containers import Binder


def main(src, out_dir):
    vanilla = Binder.from_path(src)
    b = Binder.from_path(src)
    by_id = {e.entry_id: e for e in b.entries}
    swapped, missing = [], []
    for eid, e in by_id.items():
        if (6200 <= eid < 6300 or 6400 <= eid < 6500) and e.name.endswith(".hkx"):
            twin = by_id.get(eid + 100)
            if twin is None:
                missing.append(eid)
                continue
            e.data = bytes(twin.data)
            swapped.append(eid)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, os.path.basename(src))
    b.write(out)
    # verification: re-read, compare with vanilla
    chk = {e.entry_id: e for e in Binder.from_path(out).entries}
    van = {e.entry_id: e for e in vanilla.entries}
    assert set(chk) == set(van), "entry set changed"
    changed = sorted(i for i in chk if chk[i].data != van[i].data)
    assert changed == sorted(i for i in swapped if van[i].data != van[i + 100].data), "unexpected changes"
    assert all(chk[i].data == van[i + 100].data for i in swapped), "swap mismatch"
    print(f"wrote {out}: swapped {len(swapped)} left-hand casts {swapped[:6]}..., no right-hand twin for {missing}, "
          f"{len(changed)} entries differ from vanilla, {len(chk) - len(changed)} identical")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
