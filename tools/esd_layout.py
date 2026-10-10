"""SoraSouls – exact layout model of a DSR chr ESD (c0000.esd.dcx) for layout-preserving rewrites.

Parses every record with its byte position (offsets are relative to the data block that follows the 0x6C-byte
external header) and checks that the records tile the data block completely. Record kinds:
  ihdr  internal header (72 B)          smh  state machine header (32 B: index, states_off, count, states_off2)
  state (72 B)                          cond condition (56 B)        cmd command (24 B: bank,index,args_off,args_n)
  arg   command arg (16 B: ezl_off, ezl_size)
  cptrs condition pointer array (8 B each; states' lists and sub-condition lists live in ONE pointer table)
  ezl   EZL bytecode blob (condition tests and command args)          tail  trailing bytes (name block etc.)
"""
import struct
from collections import defaultdict
from soulstruct.dcx import decompress

BASE = 0x6C


class Layout:
    def __init__(self, path):
        self.raw, self.dcx_type = decompress(open(path, "rb").read())
        self.d = self.raw[BASE:]
        self.ext = list(struct.unpack_from("<27i", self.raw, 0))
        self.records = {}            # offset -> (kind, size)
        self.refs = defaultdict(list)  # offset -> list of (field_owner_offset, field_byte_pos)
        self._parse()

    def q(self, off, n=1):
        return struct.unpack_from(f"<{n}q", self.d, off)

    def add(self, off, kind, size):
        prev = self.records.get(off)
        if prev and prev != (kind, size):
            # pointer arrays can overlap (a sub-list may be a suffix of another list); keep the larger extent
            if prev[0] == kind == "cptrs":
                self.records[off] = (kind, max(size, prev[1]))
                return
            raise RuntimeError(f"record clash at {off:#x}: {prev} vs {(kind, size)}")
        self.records[off] = (kind, size)

    def _parse(self):
        d = self.d
        self.add(0, "ihdr", 72)
        sm_off, sm_n = self.q(0x18, 2)
        seen_state, seen_cond, seen_cmds = set(), set(), set()
        for m in range(sm_n):
            mo = sm_off + 32 * m
            self.add(mo, "smh", 32)
            idx, st_off, st_n, st_off2 = self.q(mo, 4)
            for s in range(st_n):
                so = st_off + 72 * s
                if so in seen_state:
                    continue
                seen_state.add(so)
                self.add(so, "state", 72)
                sid, cp, cn, eo, en, xo, xn, oo, on = self.q(so, 9)
                if cp != -1 and cn:
                    self.add(cp, "cptrs", 8 * cn)
                    for c in self.q(cp, cn):
                        self._cond(c, seen_cond, seen_cmds)
                for co, cn_ in ((eo, en), (xo, xn), (oo, on)):
                    self._cmds(co, cn_, seen_cmds)

    def _cond(self, c, seen_cond, seen_cmds):
        if c in seen_cond:
            return
        seen_cond.add(c)
        self.add(c, "cond", 56)
        nxt, pco, pcn, spo, spn, to, ts = self.q(c, 7)
        self._cmds(pco, pcn, seen_cmds)
        if spo != -1 and spn:
            self.add(spo, "cptrs", 8 * spn)
            for s in self.q(spo, spn):
                self._cond(s, seen_cond, seen_cmds)
        if to != -1 and ts:
            self.add(to, "ezl", ts)

    def _cmds(self, off, n, seen_cmds):
        if off == -1 or not n:
            return
        for k in range(n):
            co = off + 24 * k
            if co in seen_cmds:
                continue
            seen_cmds.add(co)
            self.add(co, "cmd", 24)
            bank, index = struct.unpack_from("<ii", self.d, co)
            ao, an = self.q(co + 8, 2)
            if ao != -1 and an:
                for a in range(an):
                    aoff = ao + 16 * a
                    self.add(aoff, "arg", 16)
                    eo, es = self.q(aoff, 2)
                    if eo != -1 and es:
                        self.add(eo, "ezl", es)

    def coverage(self):
        """Walk the data block: report gaps/overlaps between records."""
        items = sorted(self.records.items())
        gaps, overlaps, pos = [], [], 0
        for off, (kind, size) in items:
            if off > pos:
                gaps.append((pos, off - pos))
            elif off < pos:
                overlaps.append((off, kind, pos - off))
            pos = max(pos, off + size)
        if pos < len(self.d):
            gaps.append((pos, len(self.d) - pos))
        return gaps, overlaps

    def regions(self):
        """Contiguous runs of the same record kind (the 'tables')."""
        out, cur = [], None
        for off, (kind, size) in sorted(self.records.items()):
            if cur and cur[0] == kind and off <= cur[2]:
                cur[2] = max(cur[2], off + size); cur[3] += 1
            else:
                if cur:
                    out.append(tuple(cur))
                cur = [kind, off, off + size, 1]
        out.append(tuple(cur))
        return out
