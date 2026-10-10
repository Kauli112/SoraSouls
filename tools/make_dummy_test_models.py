"""SoraSouls – animation research experiment 2: which weapon dummy does a spell cast fire from?

In-game (v20): both hybrid Keyblades cast with the right arm, but the spell leaves the HAND, not the tip, although
dummy 100 sits at the tip. Dummies 110 and 120 sit at the grip on both the Keyblade and the Sorcerer's Catalyst, so
the cast probably uses one of them. This builds two copies of our Keyblade (mod WP_A_0204) with ONE grip dummy moved
to the tip position of dummy 100:
  WP_A_1311 (Hybrid A): dummy 110 -> tip      WP_A_1312 (Hybrid B): dummy 120 -> tip
Only the test models change; the real Keyblade WP_A_0204 is untouched.
Usage: python make_dummy_test_models.py <mod WP_A_0204.partsbnd.dcx> <out dir>
"""
import os, sys, copy
from soulstruct.containers import Binder
from soulstruct.flver import FLVER

TESTS = {"WP_A_1311": 110, "WP_A_1312": 120}


def main(src, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for new_name, moved in TESTS.items():
        b = Binder.from_path(src)
        for e in b.entries:
            if e.path.lower().endswith(".flver"):
                f = FLVER.from_bytes(e.data)
                if not any(d.reference_id == 100 for d in f.dummies):
                    e.path = e.path.replace("WP_A_0204", new_name)
                    continue   # the collapsed sheath model has no tip dummy
                tip = next(d for d in f.dummies if d.reference_id == 100).translate
                n = 0
                for d in f.dummies:
                    if d.reference_id == moved:
                        d.translate = copy.deepcopy(tip); n += 1
                if n != 1:
                    raise RuntimeError(f"expected one dummy {moved}, found {n}")
                e.data = f.to_bytes()
            e.path = e.path.replace("WP_A_0204", new_name)
        out = os.path.join(out_dir, f"{new_name}.partsbnd.dcx")
        b.write(out)
        for x in Binder.from_path(out).entries:
            if x.path.lower().endswith(".flver"):
                chk = FLVER.from_bytes(x.data)
                print(new_name, x.path.split("\\")[-1], [(d.reference_id, [round(float(v), 3) for v in d.translate])
                                                         for d in chk.dummies if d.reference_id in (100, 110, 120)])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
