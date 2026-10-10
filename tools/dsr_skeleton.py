"""SoraSouls – write work/dsr_c0000_skeleton.json from the player's own c0000.chrbnd.dcx, no Blender (v124).

The file used to come out of Blender (Soulstruct add-on import of c0000). kh_party_model.py reads each bone's name,
parent and head (world position); blender_fit_sora.py also reads rot (world rotation, columns = bone axes).
FLVER bones store local translate / rotate (Euler radians) / scale; world = parent world @ T @ R @ S with
R = Ry @ Rz @ Rx (x applied first, then z, then y). Checked 2026-10-10 against the Blender-made file: every head
within 1.5e-7 m (float32 precision).
Usage: python dsr_skeleton.py <c0000.chrbnd.dcx> <out .json>
"""
import json, sys
import numpy as np
from soulstruct.containers import Binder
from soulstruct.flver import FLVER


def _rot(axis, a):
    c, s = np.cos(a), np.sin(a)
    return {"x": np.array([[1, 0, 0], [0, c, -s], [0, s, c]]),
            "y": np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]]),
            "z": np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])}[axis]


def skeleton(chrbnd):
    b = Binder.from_path(chrbnd)
    f = FLVER.from_bytes(next(e for e in b.entries if e.path.lower().endswith(".flver")).data)
    world = {}

    def W(i):
        if i not in world:
            bn = f.bones[i]
            rx, ry, rz = (float(v) for v in bn.rotate)
            M = np.eye(4)
            M[:3, :3] = _rot("y", ry) @ _rot("z", rz) @ _rot("x", rx) * np.array([float(v) for v in bn.scale])
            M[:3, 3] = [float(v) for v in bn.translate]
            p = bn.parent_bone_index
            world[i] = W(p) @ M if p >= 0 else M
        return world[i]

    out = []
    for i, bn in enumerate(f.bones):
        M = W(i)
        R = M[:3, :3] / np.linalg.norm(M[:3, :3], axis=0)
        out.append(dict(name=bn.name, parent=bn.parent_bone_index, head=M[:3, 3].tolist(), rot=R.tolist()))
    return out


if __name__ == "__main__":
    import logging
    logging.disable(logging.WARNING)
    with open(sys.argv[2], "w", encoding="utf-8") as fp:
        json.dump(skeleton(sys.argv[1]), fp, indent=1)
    print("wrote", sys.argv[2])
