"""SoraSouls – "append + repoint" patching for the player state machine (chr/c0000.esd.dcx).

Same-size patches can't express seamless casting (tests are shared between attack and guard states and the new
tests are 9-18 bytes longer). But every CONDITION has its own 56-byte header (int64 fields: next_state, pass
commands offset/count, subconditions offset/count, test_ezl_offset @+40, test_ezl_size @+48). The EZL test data
is the LAST section of the file (file = 0x6C header + data size stored at header int[5]). So:
  1. new test blocks are appended at the very end (nothing existing moves),
  2. only the chosen conditions' test_ezl_offset/size are re-pointed,
  3. header int[5] (data size) grows by the appended length.
Everything else stays byte-identical to vanilla (verified below).
"""
import struct, sys
import esd_map
from soulstruct.dcx import decompress, compress

TEST_OFF, TEST_SIZE = 40, 48


def condition_header(raw, base, row):
    """Absolute offset of a condition's 56-byte header, verified against its test pointer."""
    for cand in (row["header"], row["header"] + base):
        off, size = struct.unpack_from("<qq", raw, cand + TEST_OFF)
        if off + base == row["offset"] and size == row["size"]:
            return cand
    raise RuntimeError(f"could not locate header for {row['machine']}/{row['state']}{row['path']}")


def build(src, out, repoints):
    """repoints: list of (label, row, new_test_bytes). Each row = one condition of one state."""
    raw, base, rows = esd_map.build_map(src)
    dcx_type = decompress(open(src, "rb").read())[1]
    buf = bytearray(raw)
    data_size = struct.unpack_from("<i", buf, 0x14)[0]
    assert data_size + base == len(buf), "unexpected layout: test data is not the last section"
    touched = []
    for label, row, test in repoints:
        h = condition_header(raw, base, row)
        new_off = len(buf) - base
        buf += test
        struct.pack_into("<qq", buf, h + TEST_OFF, new_off, len(test))
        touched.append((h + TEST_OFF, 16))
        print(f"  {label}: header @{h:#x} -> appended test @{new_off + base:#x} ({len(test)} bytes, was {row['size']})")
    struct.pack_into("<i", buf, 0x14, len(buf) - base)
    touched.append((0x14, 4))
    # verification: everything outside the touched fields and the appended tail is byte-identical
    allowed = set()
    for o, n in touched:
        allowed.update(range(o, o + n))
    diffs = [i for i in range(len(raw)) if raw[i] != buf[i] and i not in allowed]
    if diffs:
        raise RuntimeError(f"{len(diffs)} unexpected byte changes, first at {diffs[0]:#x}")
    packed = compress(bytes(buf), dcx_type)
    if decompress(packed)[0] != bytes(buf):
        raise RuntimeError("DCX round trip mismatch")
    open(out, "wb").write(packed)
    print(f"wrote {out}: {len(raw)} -> {len(buf)} bytes, only {len(allowed)} header bytes changed + {len(buf) - len(raw)} appended")
    return bytes(buf)


def null_test(src, out):
    """Re-point state 0's one-handed R1 light-attack condition to an identical appended copy of its test."""
    _, _, rows = esd_map.build_map(src)
    row = next(r for r in rows if r["machine"] == 1 and r["state"] == 0 and r["offset"] == 0x56B30)
    return build(src, out, [("null repoint (state 0 -> 46, identical copy)", row, row["test"])])


if __name__ == "__main__":
    {"null_test": null_test}[sys.argv[3]](sys.argv[1], sys.argv[2])
