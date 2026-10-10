"""SoraSouls – copy-on-write patching for the player state machine (chr/c0000.esd.dcx).

Condition records AND their tests are shared between states (1,683 records for 34,155 condition uses; 172 records
are shared by guard and non-guard states). To change a condition for some states only, the path from the state to
that condition is copied: state's condition-pointer list -> parent condition record -> its sub-condition list ->
... -> the condition record (+ optionally a new test). Copies are APPENDED after the last section; then only the
state's 8-byte condition_pointers_offset is re-pointed. Nothing existing moves; all other bytes stay identical.

Layout (all offsets relative to the data block at 0x6C, int64 'varints'):
  state record (72 B): id, cond_ptrs_off, cond_count, enter_off, enter_n, exit_off, exit_n, ongoing_off, ongoing_n
  condition record (56 B): next_state_off, pass_cmds_off, pass_cmds_n, sub_ptrs_off, sub_n, test_off, test_size
  header int[5] @0x14 = data size (file = 0x6C + data size)
"""
import struct, sys
import soulstruct.base.ezstate.esd.state as _state
from soulstruct.dcx import decompress, compress
from soulstruct.darksouls1r.ezstate.esd.core import ChrESD

BASE = 0x6C
_STATE_POS = {}
_orig_state = _state.State.from_esd_reader.__func__


def _hook(cls, reader):
    pos = reader.position
    obj = _orig_state(cls, reader)
    _STATE_POS[id(obj)] = pos
    return obj


_state.State.from_esd_reader = classmethod(_hook)


def state_offsets(path):
    """{(machine, state_id): relative offset of the state record}, verified by reading the id back."""
    raw = decompress(open(path, "rb").read())[0]
    _STATE_POS.clear()
    esd = ChrESD.from_path(path)
    out = {}
    for mk, sm in esd.state_machines.items():
        for sid, st in sm.items():
            pos = _STATE_POS[id(st)]
            for cand in (pos - BASE, pos):
                if 0 <= cand and struct.unpack_from("<q", raw, BASE + cand)[0] == sid:
                    out[(mk, sid)] = cand
                    break
            else:
                raise RuntimeError(f"state {mk}/{sid}: record not found")
    return raw, out


class Cow:
    def __init__(self, raw):
        self.orig = raw
        self.buf = bytearray(raw)
        self.allowed = set()

    def q(self, rel, n=1):
        return struct.unpack_from(f"<{n}q", self.buf, BASE + rel)

    def append(self, data, align=8):
        while (len(self.buf) - BASE) % align:
            self.buf += b"\0"
        rel = len(self.buf) - BASE
        self.buf += data
        return rel

    def copy_condition(self, cond_rel, path, edits):
        """Return rel offset of a (possibly new) condition record honouring edits {path: new_test or None}."""
        rec = list(self.q(cond_rel, 7))
        changed = False
        if rec[3] != -1 and rec[4] > 0 and any(p[:len(path) + 1][:-1] == path and len(p) > len(path) for p in edits):
            subs = list(self.q(rec[3], rec[4]))
            new_subs = [self.copy_condition(s, path + (i,), edits) for i, s in enumerate(subs)]
            if new_subs != subs:
                rec[3] = self.append(struct.pack(f"<{len(new_subs)}q", *new_subs))
                changed = True
        if path in edits:
            changed = True
            if edits[path] is not None:
                rec[5] = self.append(edits[path], align=1)
                rec[6] = len(edits[path])
        if not changed:
            return cond_rel
        return self.append(struct.pack("<7q", *rec))

    def patch_state(self, state_rel, edits):
        sid, cptr, ccount = self.q(state_rel, 3)
        conds = list(self.q(cptr, ccount))
        new = [self.copy_condition(c, (i,), edits) for i, c in enumerate(conds)]
        if new == conds:
            return False
        new_ptr = self.append(struct.pack(f"<{len(new)}q", *new))
        struct.pack_into("<q", self.buf, BASE + state_rel + 8, new_ptr)
        self.allowed.update(range(BASE + state_rel + 8, BASE + state_rel + 16))
        return True

    def finish(self, out, dcx_type):
        struct.pack_into("<i", self.buf, 0x14, len(self.buf) - BASE)
        self.allowed.update(range(0x14, 0x18))
        diffs = [i for i in range(len(self.orig)) if self.orig[i] != self.buf[i] and i not in self.allowed]
        if diffs:
            raise RuntimeError(f"{len(diffs)} unexpected changes, first at {diffs[0]:#x}")
        packed = compress(bytes(self.buf), dcx_type)
        if decompress(packed)[0] != bytes(self.buf):
            raise RuntimeError("DCX round trip mismatch")
        open(out, "wb").write(packed)
        changed = sum(1 for i in range(len(self.orig)) if self.orig[i] != self.buf[i])
        print(f"wrote {out}: {len(self.orig)} -> {len(self.buf)} bytes; {changed} existing bytes changed, "
              f"{len(self.buf) - len(self.orig)} appended")


def null_cow(src, out):
    """State 0: copy the path to its one-handed R1 condition (25,4) – identical copies, test unchanged."""
    raw, states = state_offsets(src)
    cow = Cow(raw)
    assert cow.patch_state(states[(1, 0)], {(25, 4): None})
    cow.finish(out, decompress(open(src, "rb").read())[1])


if __name__ == "__main__":
    {"null_cow": null_cow}[sys.argv[3]](sys.argv[1], sys.argv[2])
