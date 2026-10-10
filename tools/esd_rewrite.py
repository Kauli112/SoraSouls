"""SoraSouls – layout-preserving rewriter for DSR chr ESD (c0000.esd.dcx).

Tables (data block, header-described): states 72 B | conditions 56 B | commands 24 B | args 16 B | condition
pointer table 8 B | EZL bytecode. New records are INSERTED at the end of their own table so the game's load-time
relocation (which walks these tables by count) covers them. Every offset field of every record is shifted:
  +56*k  for offsets at/after the old end of the condition table (k new conditions)
  +8*m   additionally for offsets at/after the old end of the pointer table (m new pointer slots)
External header: data size, condition count, pointer-table offset/count and the three end-of-data offsets are
updated. Acceptance test: no insertions -> byte-identical output (see __main__).
"""
import struct, sys
from soulstruct.dcx import decompress, compress
import esd_layout

BASE = 0x6C


class Rewriter:
    def __init__(self, path):
        self.L = esd_layout.Layout(path)
        self.d = bytearray(self.L.d)
        e = self.L.ext
        self.cond_start = 0x8E48
        self.cond_end = self.cond_start + 56 * e[14]
        self.cmd_end = self.cond_end + 24 * e[16]
        self.arg_end = self.cmd_end + 16 * e[18]
        self.cptr_start, self.cptr_end = e[19], e[19] + 8 * e[20]
        assert self.cptr_start == self.arg_end and self.cptr_end == 0x50D10 and self.cond_start - 0x88 == 72 * e[12]
        self.new_conds, self.new_ptrs, self.new_ezl = [], [], []   # staged insertions

    # ---- staging API (returns OLD-space handles resolved at build time) ----
    def add_ezl(self, blob):
        self.new_ezl.append(bytes(blob))
        return ("ezl", len(self.new_ezl) - 1)

    def add_ptr_list(self, items):
        self.new_ptrs.append(list(items))
        return ("ptrs", len(self.new_ptrs) - 1)

    def add_cond(self, rec7):
        self.new_conds.append(list(rec7))
        return ("cond", len(self.new_conds) - 1)

    def set_state_conditions(self, state_off, handle_or_off, count):
        self._state_patches = getattr(self, "_state_patches", [])
        self._state_patches.append((state_off, handle_or_off, count))

    # ---- build ----
    def build(self, out_path=None):
        k = len(self.new_conds)
        m = sum(len(p) for p in self.new_ptrs)
        d = self.d

        def shift(o):
            if o == -1:
                return o
            if o >= self.cptr_end:
                return o + 56 * k + 8 * m
            if o >= self.cond_end:
                return o + 56 * k
            return o

        ptr_pos, acc = [], self.cptr_end + 56 * k
        for p in self.new_ptrs:
            ptr_pos.append(acc); acc += 8 * len(p)
        ezl_pos, acc = [], len(d) + 56 * k + 8 * m
        for b in self.new_ezl:
            ezl_pos.append(acc); acc += len(b)

        def resolve(h):
            if isinstance(h, tuple):
                kind, i = h
                if kind == "cond":
                    return self.cond_end + 56 * i
                return ptr_pos[i] if kind == "ptrs" else ezl_pos[i]
            return shift(h)

        out = bytearray(d)
        Q = lambda buf, o, n=1: list(struct.unpack_from(f"<{n}q", buf, o))
        # states (all 504 slots, incl. the 2 unreferenced ones): cond ptrs, enter/exit/ongoing commands
        for so in range(0x88, self.cond_start, 72):
            f = Q(d, so, 9)
            for i in (1, 3, 5, 7):
                f[i] = shift(f[i])
            struct.pack_into("<9q", out, so, *f)
        for so, h, n in getattr(self, "_state_patches", []):
            struct.pack_into("<qq", out, so + 8, resolve(h), n)
        # conditions: next state (state table, unshifted), pass cmds, sub ptrs, test
        for co in range(self.cond_start, self.cond_end, 56):
            f = Q(d, co, 7)
            for i in (1, 3, 5):
                f[i] = shift(f[i])
            struct.pack_into("<7q", out, co, *f)
        # commands: args offset
        for co in range(self.cond_end, self.cmd_end, 24):
            ao = Q(d, co + 8)[0]
            struct.pack_into("<q", out, co + 8, shift(ao))
        # args: ezl offset
        for ao in range(self.cmd_end, self.arg_end, 16):
            eo = Q(d, ao)[0]
            struct.pack_into("<q", out, ao, shift(eo))
        # pointer table entries -> conditions (condition table start..end is unshifted)
        for po in range(self.cptr_start, self.cptr_end, 8):
            p = Q(d, po)[0]
            struct.pack_into("<q", out, po, shift(p))
        # assemble with insertions
        new_cond_bytes = b"".join(struct.pack("<7q", *[resolve(x) if isinstance(x, tuple) else
                                                         (shift(x) if j in (1, 3, 5) else x)
                                                         for j, x in enumerate(r)]) for r in self.new_conds)
        new_ptr_bytes = b"".join(struct.pack(f"<{len(p)}q", *[resolve(x) for x in p]) for p in self.new_ptrs)
        data = (out[:self.cond_end] + new_cond_bytes + out[self.cond_end:self.cptr_end] + new_ptr_bytes +
                out[self.cptr_end:] + b"".join(self.new_ezl))
        # external header
        ext = list(self.L.ext)
        ext[5] = len(data)
        ext[14] += k
        ext[19] = shift(ext[19]) if k else ext[19]
        ext[20] += m
        for i in (21, 23, 25):
            ext[i] = len(data) if ext[i] == len(self.d) else shift(ext[i])
        hdr = bytearray(self.L.raw[:BASE])
        struct.pack_into("<27i", hdr, 0, *ext)
        raw = bytes(hdr) + bytes(data)
        if out_path:
            packed = compress(raw, self.L.dcx_type)
            assert decompress(packed)[0] == raw
            open(out_path, "wb").write(packed)
        return raw


if __name__ == "__main__":
    src = sys.argv[1]
    rw = Rewriter(src)
    raw = rw.build()
    print("zero-insertion rebuild byte-identical:", raw == bytes(rw.L.raw), len(raw))


# ---- copy-on-write on top of the rewriter ----------------------------------------------------------------------
def cow_state(rw, state_off, edits):
    """Give ONE state private copies of the condition path(s) named in `edits` {path tuple: new EZL bytes or None}.
    Shared records stay untouched for every other state. Returns number of copied conditions."""
    Q = lambda o, n=1: list(struct.unpack_from(f"<{n}q", rw.d, o))
    copied = [0]

    def copy(cond_off, path):
        rec = Q(cond_off, 7)
        changed = False
        if rec[3] != -1 and rec[4] and any(len(p) > len(path) and p[:len(path)] == path for p in edits):
            subs = Q(rec[3], rec[4])
            new_subs = [copy(s, path + (i,)) for i, s in enumerate(subs)]
            if new_subs != subs:
                rec[3] = rw.add_ptr_list(new_subs)
                changed = True
        if path in edits:
            changed = True
            if edits[path] is not None:
                rec[5] = rw.add_ezl(edits[path])
                rec[6] = len(edits[path])
        if not changed:
            return cond_off
        copied[0] += 1
        return rw.add_cond(rec)

    sid, cp, cn = Q(state_off, 3)
    conds = Q(cp, cn)
    new = [copy(c, (i,)) for i, c in enumerate(conds)]
    if new != conds:
        rw.set_state_conditions(state_off, rw.add_ptr_list(new), cn)
    return copied[0]


def null_cow(src, out):
    import esd_cow
    _, states = esd_cow.state_offsets(src)
    rw = Rewriter(src)
    n = cow_state(rw, states[(1, 0)], {(25, 4): None})
    rw.build(out)
    print(f"null COW: state 0 got {n} private condition copies -> {out}")
