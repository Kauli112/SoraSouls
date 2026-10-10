"""SoraSouls – make Donald & Goofy's battle AI exist in every area (v87).

In-game v86: they follow Sora but never attack, though enemies hit them. Dark Souls keeps battle AI scripts per area
(script/mXX_XX_00_00.luabnd.dcx); the bandit battle goals Donald (6804, attack magic) and Goofy (6802, warrior) use
are only in Darkroot Garden's (m12_00). Elsewhere the goal is missing, so the AI never enters battle.

This copies those two compiled scripts, unchanged, from the user's own m12_00 luabnd into every other area luabnd that
lacks them, and registers them the way the area files do (LuaInfo goal entry + LuaGNL function names). Nothing else in
the files changes. (The co-op summon battle scripts 6520/6540 were not used: they branch on their own NpcThinkParam
ids; the bandit scripts have no such check.)

v90: also adds SoraSouls' own follow logic 006950_logic.lua (party_logic.py) to every area, Darkroot included.

Usage: python party_ai.py <DSR game dir or staged copy> <mod dir>
"""
import os, sys
from soulstruct.containers import Binder, BinderEntry
import struct

SOURCE_MAP = "m12_00_00_00"
GOALS = (6804, 6802)          # party.THINK battle ids (Donald, Goofy)
MAPS = ["m10_00_00_00", "m10_01_00_00", "m10_02_00_00", "m11_00_00_00", "m12_00_00_00", "m12_01_00_00",
        "m13_00_00_00", "m13_01_00_00", "m13_02_00_00", "m14_00_00_00", "m14_01_00_00", "m15_00_00_00",
        "m15_01_00_00", "m16_00_00_00", "m17_00_00_00", "m18_00_00_00", "m18_01_00_00"]
INFO_ID, GNL_ID = 1000001, 1000000


# ---- raw LuaInfo / LuaGNL editing (soulstruct's classes don't rebuild these byte-for-byte) ----------------------
# LuaInfo: "LUAI", 1, count, 0, then count x (goal id, name offset, logic-interrupt name offset, flags) u32, then the
# NUL-terminated names (vanilla files have leftover bytes after them). LuaGNL: count x u32 name offsets, a 0 u32, then the names.
def _cstr(d, o):
    return d[o:d.index(b"\0", o)]


def info_read(d):
    n = struct.unpack_from("<I", d, 8)[0]
    out = []
    for k in range(n):
        gid, no, lo, fl = struct.unpack_from("<IIII", d, 16 + 16 * k)
        out.append((gid, _cstr(d, no), _cstr(d, lo) if lo else None, fl))
    return out


def info_add(d, new):
    """Insert goal records after the existing ones and append their names at the very end; every existing byte is
    kept (vanilla files carry leftover bytes after the names), only shifted, with the old offsets moved to match."""
    n = struct.unpack_from("<I", d, 8)[0]
    ins = 16 * len(new)
    head = bytearray(d[:16]); struct.pack_into("<I", head, 8, n + len(new))
    table = bytearray(d[16:16 + 16 * n])
    for k in range(n):
        gid, no, lo, fl = struct.unpack_from("<IIII", table, 16 * k)
        struct.pack_into("<IIII", table, 16 * k, gid, no + ins, lo + ins if lo else 0, fl)
    rest = bytearray(d[16 + 16 * n:])
    base = 16 + 16 * (n + len(new)) + len(rest)
    recs, strings = b"", b""
    for gid, name, li, fl in new:
        no = base + len(strings); strings += name + b"\0"
        lo = 0
        if li is not None:
            lo = base + len(strings); strings += li + b"\0"
        recs += struct.pack("<IIII", gid, no, lo, fl)
    return bytes(head + table + recs + rest + strings)


def gnl_read(d):
    names, i = [], 0
    while True:
        o = struct.unpack_from("<I", d, 4 * i)[0]
        if o == 0:
            return names
        names.append(_cstr(d, o)); i += 1


def gnl_add(d, new):
    """Insert name offsets before the 0 terminator and append the names at the very end (existing bytes kept)."""
    n = len(gnl_read(d))
    ins = 4 * len(new)
    table = bytearray(d[:4 * n])
    for k in range(n):
        struct.pack_into("<I", table, 4 * k, struct.unpack_from("<I", table, 4 * k)[0] + ins)
    rest = d[4 * n:]                                   # 0 terminator + names (+ any leftover bytes)
    base = 4 * (n + len(new)) + len(rest)
    offs, strings = b"", b""
    for nm in new:
        offs += struct.pack("<I", base + len(strings)); strings += nm + b"\0"
    return bytes(table + offs + rest + strings)


def _script_entry(bnd, gid):
    return next((e for e in bnd.entries if e.name.endswith(f"{gid:06d}_battle.lua")), None)


def _source(game):
    src = Binder.from_path(os.path.join(game, "script", f"{SOURCE_MAP}.luabnd.dcx"))
    info = info_read(src.find_entry_by_id(INFO_ID).get_uncompressed_data())
    gnl = gnl_read(src.find_entry_by_id(GNL_ID).get_uncompressed_data())
    out = {}
    for gid in GOALS:
        e = _script_entry(src, gid)
        goal = next(g for g in info if g[0] == gid and g[1].endswith(b"Battle"))
        stem = goal[1][:-len(b"Battle")]                            # e.g. b"BanditD6804"
        names = [n for n in gnl if n.startswith(stem)]
        out[gid] = dict(path=e.path, data=e.get_uncompressed_data(), flags=e.flags, goal=goal, names=names)
    # v90: SoraSouls' own follow logic (party_logic.py), added to every area including Darkroot
    import party_logic
    out["logic"] = dict(path=party_logic.SCRIPT_PATH, data=party_logic.build(), flags=src.entries[0].flags,
                        goal=party_logic.INFO_RECORD, names=list(party_logic.GNL_NAMES))
    return out


def _has(bnd, key):
    if key == "logic":
        return any(e.name.endswith("006950_logic.lua") for e in bnd.entries)
    return _script_entry(bnd, key) is not None


def patch_all(game, mod, report=print):
    src = _source(game)
    os.makedirs(os.path.join(mod, "script"), exist_ok=True)
    written = []
    for m in MAPS:
        path = os.path.join(game, "script", f"{m}.luabnd.dcx")
        bnd = Binder.from_path(path)
        missing = [g for g in (*GOALS, "logic") if not _has(bnd, g)]
        if not missing:
            report(f"{m}: already has everything")
            continue
        info_e, gnl_e = bnd.find_entry_by_id(INFO_ID), bnd.find_entry_by_id(GNL_ID)
        di, dg = info_e.get_uncompressed_data(), gnl_e.get_uncompressed_data()
        info, gnl = info_read(di), gnl_read(dg)
        new_goals, new_names = [], []
        next_id = max(e.entry_id for e in bnd.entries if e.entry_id < INFO_ID - 1) + 1
        for g in missing:
            s = src[g]
            bnd.add_entry(BinderEntry(data=s["data"], entry_id=next_id, path=s["path"], flags=s["flags"]))
            next_id += 1
            new_goals.append(s["goal"])
            new_names += [n for n in s["names"] if n not in gnl and n not in new_names]
        ni, ng = info_add(di, new_goals), gnl_add(dg, new_names)
        assert info_read(ni) == info + new_goals and gnl_read(ng) == gnl + new_names
        info_e.set_uncompressed_data(ni)
        gnl_e.set_uncompressed_data(ng)
        # keep the binder's entry order: scripts first, then .luagnl / .luainfo
        bnd.entries.sort(key=lambda e: e.entry_id)
        out = os.path.join(mod, "script", f"{m}.luabnd.dcx")
        bnd.write(out)
        # check: re-read, every original entry byte-identical, new scripts identical to the source
        chk, orig = Binder.from_path(out), Binder.from_path(path)
        for e in orig.entries:
            if e.entry_id in (INFO_ID, GNL_ID):
                continue
            assert chk.find_entry_by_id(e.entry_id).get_uncompressed_data() == e.get_uncompressed_data(), (m, e.name)
        for g in missing:
            e = next(x for x in chk.entries if x.path == src[g]["path"])
            assert e.get_uncompressed_data() == src[g]["data"]
        ci = info_read(chk.find_entry_by_id(INFO_ID).get_uncompressed_data())
        assert {g[0] for g in ci} >= set(GOALS) | {6950} and ci[:len(info_read(di))] == info_read(di)
        report(f"{m}: added {missing} -> {out}")
        written.append(out)
    return written


if __name__ == "__main__":
    patch_all(sys.argv[1], sys.argv[2])
