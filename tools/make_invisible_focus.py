"""SoraSouls – build the invisible left-hand casting focus model.

Copies the Sorcerer's Catalyst part (WP_A_0910) to a new, unused model id (WP_A_1309), collapses every vertex onto
the grip so nothing is drawn, and keeps all dummies (dummy 100 = spell origin, ~53 cm out from the hand).
Vanilla files are only read. Usage: python make_invisible_focus.py <WP_A_0910.partsbnd.dcx> <out dir>
"""
import os, sys
from soulstruct.containers import Binder
from soulstruct.flver import FLVER

SRC_MODEL, NEW_MODEL = "WP_A_0910", "WP_A_1309"


def main(src, out_dir):
    b = Binder.from_path(src)
    for e in b.entries:
        if e.path.lower().endswith(".flver"):
            f = FLVER.from_bytes(e.data)
            for m in f.meshes:
                m.vertices["position"][:] = 0.0
                m.refresh_bounding_boxes() if hasattr(m, "refresh_bounding_boxes") else None
            e.data = f.to_bytes()
        e.path = e.path.replace(SRC_MODEL, NEW_MODEL)
    out = os.path.join(out_dir, f"{NEW_MODEL}.partsbnd.dcx")
    os.makedirs(out_dir, exist_ok=True)
    b.write(out)
    # read-back check
    chk = Binder.from_path(out)
    fl = FLVER.from_bytes(next(e for e in chk.entries if e.path.lower().endswith(".flver")).data)
    span = max(float(abs(m.vertices["position"]).max()) for m in fl.meshes)
    print("wrote", out, [e.path for e in chk.entries], "max |vertex| =", span,
          "dummies", sorted({d.reference_id for d in fl.dummies}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
