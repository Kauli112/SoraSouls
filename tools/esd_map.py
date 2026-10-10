"""SoraSouls – map every EZL condition test in c0000.esd to (machine, state, condition path, absolute byte offset),
so same-size patches can target specific states instead of every occurrence of a byte pattern.
Read-only. Used by esd_patch.py. Offsets are verified: raw[offset:offset+size] == the condition's test bytes.
"""
import soulstruct.base.ezstate.esd.condition as _cond
from soulstruct.dcx import decompress
from soulstruct.darksouls1r.ezstate.esd.core import ChrESD

_OFFSETS = {}
_orig = _cond.Condition.from_esd_reader.__func__


def _patched(cls, reader):
    start = reader.position
    header = _cond.ConditionStruct.from_bytes(reader)
    reader.seek(start)
    obj = _orig(cls, reader)
    _OFFSETS[id(obj)] = (header.test_ezl_offset, header.test_ezl_size, start)
    return obj


_cond.Condition.from_esd_reader = classmethod(_patched)


def build_map(path):
    raw = decompress(open(path, "rb").read())[0]
    _OFFSETS.clear()
    esd = ChrESD.from_path(path)
    # find the base that turns reader offsets into absolute positions in the decompressed file
    base = None
    rows, seen = [], set()

    def walk(conds, trail, mk, sid):
        for i, c in enumerate(conds):
            off, size, hdr = _OFFSETS[id(c)]
            rows.append((mk, sid, trail + (i,), off, size, bytes(c.test_ezl), c.next_state_id, hdr))
            walk(c.subconditions, trail + (i,), mk, sid)

    for mk, sm in esd.state_machines.items():
        for sid, st in sm.items():
            walk(st.conditions, (), mk, sid)
    for cand in (0x6C, 0, 0x2C):  # 0x6C = header size (offsets in the file are relative to the data block)
        if all(raw[o + cand:o + cand + n] == t for _, _, _, o, n, t, _, _ in rows[:200]):
            base = cand
            break
    if base is None:
        raise RuntimeError("could not determine offset base")
    bad = [r for r in rows if raw[r[3] + base:r[3] + base + r[4]] != r[5]]
    if bad:
        raise RuntimeError(f"{len(bad)} conditions do not match at their offsets")
    return raw, base, [dict(machine=r[0], state=r[1], path=r[2], offset=r[3] + base, size=r[4], test=r[5],
                            next_state=r[6], header=r[7]) for r in rows]
