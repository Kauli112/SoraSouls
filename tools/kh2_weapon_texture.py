"""SoraSouls – extract the texture sheet of a KH2 weapon model (.mdlx) as PNG (v63).

Why: OpenKH's FBX export writes every texture as Texture0000.png, so exporting several Keyblades into one folder
leaves only the last one. This reads the texture straight from the user's own .mdlx instead.
Format (worked out on the user's files; checked pixel-exact against OpenKH's export of W_EX010_M0):
  * .mdlx is a BAR archive; entry type 7 is the texture. Header u32[9]: ..., [7] image offset, [8] palette offset.
  * Image: 8-bit indices, 256 wide, stored in PS2 GS memory order (PSMT8 swizzle) -> unswizzle.
  * Palette: 256 RGBA entries in a 64-entry-wide GS area: index k -> s = k with bits 3/4 swapped (CSM1),
    entry = (s // 16) * 64 + s % 16. RGB as stored, alpha 0..128 -> x2 (clamped 255).
Usage: python kh2_weapon_texture.py <in .mdlx> <out .png>
"""
import struct, sys
import numpy as np
from PIL import Image


def unswizzle8(buf, w, h):
    y, x = np.mgrid[0:h, 0:w]
    block = (y & ~0xf) * w + (x & ~0xf) * 2
    swap = (((y + 2) >> 2) & 1) * 4
    py = (((y & ~3) >> 1) + (y & 1)) & 7
    column = py * w * 2 + ((x + swap) & 7) * 4
    byte = ((y >> 1) & 1) + ((x >> 2) & 2)
    return buf[block + column + byte]


def texture(path):
    d = open(path, "rb").read()
    if d[:3] != b"BAR":
        raise ValueError("not a BAR file")
    n = struct.unpack_from("<I", d, 4)[0]
    off = next(struct.unpack_from("<I", d, 16 + i * 16 + 8)[0] for i in range(n)
               if struct.unpack_from("<H", d, 16 + i * 16)[0] == 7)
    h = struct.unpack_from("<9I", d, off)
    pix = np.frombuffer(d, np.uint8, h[8] - h[7], off + h[7])
    width = 256
    height = len(pix) // width
    k = np.arange(256)
    s = (k & ~0x18) | ((k & 0x8) << 1) | ((k & 0x10) >> 1)
    entry = (s // 16) * 64 + s % 16
    raw = np.frombuffer(d, np.uint8, (entry.max() + 1) * 4, off + h[8]).reshape(-1, 4)
    pal = raw[entry].astype(np.int32)
    pal[:, 3] = np.minimum(pal[:, 3] * 2, 255)
    return Image.fromarray(pal[unswizzle8(pix, width, height)].astype(np.uint8), "RGBA")


if __name__ == "__main__":
    texture(sys.argv[1]).save(sys.argv[2])
