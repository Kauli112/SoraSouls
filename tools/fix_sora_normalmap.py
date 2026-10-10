"""SoraSouls – fix Sora's normal map (v59). User 2026-10-07: "his face is two different colors".

Finding: every Sora part uses the texture SORA_n as g_Bumpmap, and SORA_n was pure BLACK (R=G=B=0, a 64x64 DXT1
written by the original conversion as "flat"). DSR reads a normal map's red/green as the surface tilt with 128 =
neutral (vanilla HD_A_9550_n: mean R 126.5, G 128.8). A value of 0 means "tilted fully to one side", so every surface
was lit as if bent along its tangent direction – the two halves of the face have differently oriented tangents, so one
half came out lit and the other dark, split along a hard line. v58's smoothed vertex normals could not help.
Fix: SORA_n becomes a truly flat normal map (R=G=128 within DXT1's 5/6-bit precision, B 0 like vanilla), in every
Sora part binder. Nothing else in the binders changes.
Usage: python fix_sora_normalmap.py <parts dir (input)> <out parts dir>
"""
import os, sys, struct
from soulstruct.containers import Binder
from soulstruct.containers.tpf import TPF

PARTS = ("HD_A_9550", "BD_A_9550", "AM_A_9550", "LG_M_9550", "LG_F_9550")
SIZE = 64


def flat_dxt1(size=SIZE):
    """DDS (DXT1) where every texel is RGB565 (16, 32, 0) = (132, 130, 0) ~ neutral normal."""
    c = (16 << 11) | (32 << 5) | 0
    block = struct.pack("<HHI", c, c, 0)
    blocks = (size // 4) * (size // 4)
    header = bytearray(128)
    header[0:4] = b"DDS "
    struct.pack_into("<7I", header, 4, 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000, size, size, blocks * 8, 0, 1)
    struct.pack_into("<2I4s", header, 76, 32, 0x4, b"DXT1")          # pixel format: FOURCC
    struct.pack_into("<I", header, 108, 0x1000)                      # caps: texture
    return bytes(header) + block * blocks


def main(src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    new = flat_dxt1()
    for part in PARTS:
        for name in (f"{part}.partsbnd.dcx", f"{part}_M.partsbnd.dcx"):
            path = os.path.join(src_dir, name)
            if not os.path.exists(path):
                continue
            b = Binder.from_path(path)
            te = next(e for e in b.entries if e.name.lower().endswith(".tpf"))
            tpf = TPF.from_bytes(te.data)
            hit = 0
            for t in tpf.textures:
                if t.stem == "SORA_n":
                    t.data = new
                    t.format = 0          # DXT1, as tools/finalize_parts.py sets it
                    hit += 1
            if hit != 1:
                raise RuntimeError(f"{name}: SORA_n found {hit} times")
            te.set_from_binary_file(tpf)
            b.write(os.path.join(out_dir, name))
            print(f"{name}: SORA_n replaced with a flat normal map")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
