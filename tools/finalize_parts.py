"""Post-process Soulstruct-exported PARTSBNDs for DSR (run outside Blender with the soulstruct library).

1. TPF texture 'format' byte: the exporter writes 1 for every texture; vanilla DSR uses 0 for DXT1.
   Set it from the DDS fourCC (DXT1 -> 0, DXT5 -> 5) so it matches vanilla conventions.
2. Armor parts are written twice: <stem>.partsbnd.dcx and <stem>_M.partsbnd.dcx (vanilla _M binders are
   byte-identical except the FLVER entry is named <stem>_M.flver). Weapons (WP_*) have no _M variant in DSR.
Usage: python finalize_parts.py <exported parts dir> <mod parts dir>
"""
import sys, os
from soulstruct.containers import Binder
from soulstruct.containers.tpf import TPF

FOURCC_TO_FORMAT = {b"DXT1": 0, b"DXT5": 5}

def main(src, dst):
    os.makedirs(dst, exist_ok=True)
    for name in sorted(os.listdir(src)):
        if not name.endswith(".partsbnd.dcx"):
            continue
        stem = name[: -len(".partsbnd.dcx")]
        b = Binder.from_path(os.path.join(src, name))
        te = next(e for e in b.entries if e.path.endswith(".tpf"))
        tpf = TPF.from_bytes(te.data)
        for t in tpf.textures:
            t.format = FOURCC_TO_FORMAT[bytes(t.data[84:88])]
        te.set_from_binary_file(tpf)
        b.write(os.path.join(dst, name))
        if stem.startswith("WP_"):
            print("wrote", name, [(t.stem, t.format) for t in tpf.textures])
            continue
        fe = next(e for e in b.entries if e.path.endswith(stem + ".flver"))
        fe.path = fe.path[: -len(".flver")] + "_M.flver"
        b.write(os.path.join(dst, stem + "_M.partsbnd.dcx"))
        print("wrote", name, "and", stem + "_M.partsbnd.dcx", [(t.stem, t.format) for t in tpf.textures])

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
