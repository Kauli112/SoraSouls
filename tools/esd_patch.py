"""SoraSouls – same-size, in-place byte patches for the player state machine (chr/c0000.esd.dcx).

Why: rewriting c0000.esd with soulstruct (tools/esd_tool.py) is semantically equal but structurally different
(shared conditions/commands merged or split) and caused a "forward-only movement lock" in-game (null test v23).
The byte-identical vanilla file had no lock (v24). So edits are applied to the decompressed bytes WITHOUT changing
any size or offset: only EZL bytecode constants are replaced, and every patch states how many matches it expects.

EZL encoding (soulstruct ezl_parser): 0x00-0x7F = small int (byte - 64), 0x82 + int32 = int, 0x84..0x8A = call with
0..6 args, 0x95 '==', 0x98 'and', 0x99 'or', 0xA1 end. Function ids: IsAtkRequest 0x64 (100).
"""
import sys
from soulstruct.dcx import decompress, compress


def call(func_id, *args):
    """EZL bytes for func(args) with small-int args, e.g. call(0x64, 3) = IsAtkRequest(3)."""
    b = bytes([0x82]) + func_id.to_bytes(4, "little")
    for a in args:
        if not -64 <= a <= 63:
            raise ValueError("only small ints supported")
        b += bytes([a + 64])
    return b + bytes([0x84 + len(args)])


def apply(src, out, patches):
    """patches: list of (label, old_bytes, new_bytes, expected_count)."""
    blob = open(src, "rb").read()
    dec = decompress(blob)
    raw, dcx_type = (dec if isinstance(dec, tuple) else (dec, None))
    raw = bytearray(raw)
    for label, old, new, expected in patches:
        if len(old) != len(new):
            raise ValueError(f"{label}: size change not allowed")
        n = bytes(raw).count(old)
        if n != expected:
            raise RuntimeError(f"{label}: expected {expected} matches, found {n}")
        raw = bytearray(bytes(raw).replace(old, new))
        print(f"  {label}: {n} x patched")
    if dcx_type is None:
        from soulstruct.dcx import DCXType
        dcx_type = DCXType.DCX_DFLT_10000_24_9
    packed = compress(bytes(raw), dcx_type)
    back = decompress(packed)
    back = back[0] if isinstance(back, tuple) else back
    if bytes(back) != bytes(raw):
        raise RuntimeError("DCX round trip mismatch")
    orig = dec[0] if isinstance(dec, tuple) else dec
    diff = sum(1 for a, b in zip(orig, raw) if a != b)
    open(out, "wb").write(packed)
    print(f"wrote {out}: {len(raw)} bytes (unchanged size), {diff} bytes differ from vanilla")


# ---- Experiment 3 (v25): does R1 still request a light attack when the right-hand weapon can cast? ----
# Magic requests 2/3 are renamed to unused ids 61/62 everywhere -> no state ever reacts to a cast request.
EXPERIMENT_NO_CAST = [
    ("IsAtkRequest(3) -> (62)", call(0x64, 3), call(0x64, 62), 28),
    ("IsAtkRequest(2) -> (61)", call(0x64, 2), call(0x64, 61), 28),
]

# Experiment 3b (v26): v25 still cast on R1 -> the chained-request family (IsChainAtkRequest 0x66) also carries
# magic requests 2/3 (58 + 34 occurrences); rename those too.
EXPERIMENT_NO_CAST_B = EXPERIMENT_NO_CAST + [
    ("IsChainAtkRequest(3) -> (62)", call(0x66, 3), call(0x66, 62), 34),
    ("IsChainAtkRequest(2) -> (61)", call(0x66, 2), call(0x66, 61), 58),
]

if __name__ == "__main__":
    apply(sys.argv[1], sys.argv[2], {"no_cast": EXPERIMENT_NO_CAST, "no_cast_b": EXPERIMENT_NO_CAST_B}[sys.argv[3]])
