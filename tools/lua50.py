"""SoraSouls – minimal Lua 5.0 bytecode reader/writer for Dark Souls Remastered AI scripts (v90).

DSR AI scripts are Lua 5.0 bytecode compiled for 64-bit (header: ESC "Lua" 0x50, little endian, int 4, size_t 8,
Instruction 4, op 6 / A 8 / B 9 / C 9 bits, number = double). No Lua 5.0 compiler is available in the build
environment, so SoraSouls' own small AI scripts are written as instruction lists and assembled here (see
party_logic.py). The reader is used to check the format against the game's own files (a parse + rewrite must give the
same bytes) – it reads instructions, constants and names only; it does not turn scripts back into source.
Format reference: Lua 5.0 lundump.c / ldump.c / lopcodes.h (public, MIT licence).
"""
import struct

HEADER = b"\x1bLua\x50\x01\x04\x08\x04\x06\x08\x09\x09\x08" + struct.pack("<d", 3.14159265358979323846e7)
OPS = ["MOVE", "LOADK", "LOADBOOL", "LOADNIL", "GETUPVAL", "GETGLOBAL", "GETTABLE", "SETGLOBAL", "SETUPVAL",
       "SETTABLE", "NEWTABLE", "SELF", "ADD", "SUB", "MUL", "DIV", "POW", "UNM", "NOT", "CONCAT", "JMP", "EQ", "LT",
       "LE", "TEST", "CALL", "TAILCALL", "RETURN", "FORLOOP", "TFORLOOP", "TFORPREP", "SETLIST", "SETLISTO", "CLOSE",
       "CLOSURE"]
OP = {n: i for i, n in enumerate(OPS)}
POS_C, POS_B, POS_A = 6, 15, 24
MAXARG_BX = (1 << 18) - 1
BIAS_SBX = MAXARG_BX >> 1
TNIL, TBOOL, TNUMBER, TSTRING = 0, 1, 3, 4


class Proto:
    def __init__(self):
        self.source, self.line, self.nups, self.nparams, self.vararg, self.maxstack = None, 0, 0, 0, 0, 2
        self.lines, self.locvars, self.upvals, self.consts, self.protos, self.code = [], [], [], [], [], []


class _R:
    def __init__(self, d):
        self.d, self.o = d, 0

    def u8(self):
        v = self.d[self.o]; self.o += 1; return v

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.o)[0]; self.o += 4; return v

    def u64(self):
        v = struct.unpack_from("<Q", self.d, self.o)[0]; self.o += 8; return v

    def f64(self):
        v = struct.unpack_from("<d", self.d, self.o)[0]; self.o += 8; return v

    def string(self):
        n = self.u64()
        if n == 0:
            return None
        s = self.d[self.o:self.o + n - 1]; self.o += n; return s


def _load(r):
    p = Proto()
    p.source = r.string(); p.line = r.i32()
    p.nups, p.nparams, p.vararg, p.maxstack = r.u8(), r.u8(), r.u8(), r.u8()
    p.lines = [r.i32() for _ in range(r.i32())]
    p.locvars = [(r.string(), r.i32(), r.i32()) for _ in range(r.i32())]
    p.upvals = [r.string() for _ in range(r.i32())]
    for _ in range(r.i32()):
        t = r.u8()
        p.consts.append(r.f64() if t == TNUMBER else r.string() if t == TSTRING else None if t == TNIL else
                        _bad(t))
    p.protos = [_load(r) for _ in range(r.i32())]
    p.code = [struct.unpack_from("<I", r.d, r.o + 4 * i)[0] for i in range(r.i32())]
    r.o += 4 * len(p.code)
    return p


def _bad(t):
    raise ValueError(f"constant type {t}")


def load(data):
    assert data[:len(HEADER)] == HEADER, data[:len(HEADER)]
    r = _R(data); r.o = len(HEADER)
    p = _load(r)
    assert r.o == len(data), (r.o, len(data))
    return p


def _wstr(s):
    if s is None:
        return struct.pack("<Q", 0)
    return struct.pack("<Q", len(s) + 1) + s + b"\0"


def _dump(p):
    out = [_wstr(p.source), struct.pack("<iBBBB", p.line, p.nups, p.nparams, p.vararg, p.maxstack)]
    out.append(struct.pack("<i", len(p.lines)) + b"".join(struct.pack("<i", x) for x in p.lines))
    out.append(struct.pack("<i", len(p.locvars)) + b"".join(_wstr(n) + struct.pack("<ii", a, b) for n, a, b in p.locvars))
    out.append(struct.pack("<i", len(p.upvals)) + b"".join(_wstr(u) for u in p.upvals))
    out.append(struct.pack("<i", len(p.consts)))
    for c in p.consts:
        if c is None:
            out.append(bytes([TNIL]))
        elif isinstance(c, float):
            out.append(bytes([TNUMBER]) + struct.pack("<d", c))
        else:
            out.append(bytes([TSTRING]) + _wstr(c))
    out.append(struct.pack("<i", len(p.protos)) + b"".join(_dump(q) for q in p.protos))
    out.append(struct.pack("<i", len(p.code)) + b"".join(struct.pack("<I", c) for c in p.code))
    return b"".join(out)


def dump(p):
    return HEADER + _dump(p)


# ---- instructions ----
def enc(op, a=0, b=0, c=0, bx=None, sbx=None):
    o = OP[op]
    if sbx is not None:
        bx = sbx + BIAS_SBX
    if bx is not None:
        return o | (bx << POS_C) | (a << POS_A)
    return o | (c << POS_C) | (b << POS_B) | (a << POS_A)


def dec(i):
    o, a, b, c = i & 63, (i >> POS_A) & 255, (i >> POS_B) & 511, (i >> POS_C) & 511
    return OPS[o], a, b, c, (i >> POS_C) & MAXARG_BX


def listing(p, indent=""):
    """Instruction list with constant names, for checking how the game's scripts make calls."""
    rows = []
    for k, i in enumerate(p.code):
        op, a, b, c, bx = dec(i)
        note = ""
        if op in ("LOADK", "GETGLOBAL", "SETGLOBAL"):
            note = repr(p.consts[bx])
        elif op in ("SELF", "GETTABLE", "SETTABLE", "EQ", "LT", "LE"):
            note = " ".join(repr(p.consts[x - 250]) for x in (b, c) if x >= 250)
        rows.append(f"{indent}{k:3d} {op:9s} A={a} B={b} C={c} Bx={bx} {note}")
    for q in p.protos:
        rows.append(f"{indent}-- function (params {q.nparams}, stack {q.maxstack}, line {q.line})")
        rows += listing(q, indent + "    ")
    return rows
