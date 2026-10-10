"""SoraSouls – player state machine (chr/c0000.esd.dcx) tooling for seamless casting v2.

  python esd_tool.py decompile <c0000.esd.dcx> <out.txt>      readable dump (soulstruct ESP text), read-only
  python esd_tool.py roundtrip <c0000.esd.dcx> <out.esd.dcx>  write an UNCHANGED copy + verify semantic equality

Findings (2026-10-05):
  * soulstruct's chr-ESD decompiler crashes (bytearray used as dict key) -> patched at runtime below.
  * soulstruct's ESP *compiler* cannot recompile its own output for c0000 ("Condition IF block should return a state
    class name": conditions that run pass-commands before switching state) -> edits are made on the in-memory ESD
    objects and written with ESD.to_bytes() instead.
  * to_bytes() is not byte-identical (different layout, +537 bytes) but SEMANTICALLY identical: re-reading gives the
    same states, conditions, EZL test bytecode, commands and transitions for all 502 states (esd_signature()).
  * Casting: idle/attack states go to the cast states when (IsAtkRequest(3) or IsAtkRequest(2)) and IsMagicUseable();
    cast states play 6200/6400 + IsRightHandMagic()*100 (62/64 = left hand, 63/65 = right hand). Requests are made by
    the engine from buttons + equipment; there is no raw button query in the ESD.
"""
import sys
import soulstruct.base.ezstate.esd.ezl_parser as _p

_ff, _fb = _p.format_function, _p.format_binary_operator
_p.format_function = lambda s, k, *a, **kw: _ff(s, bytes(k), *a, **kw)
_p.format_binary_operator = lambda s, k, *a, **kw: _fb(s, bytes(k), *a, **kw)
from soulstruct.darksouls1r.ezstate.esd.core import ChrESD  # noqa: E402


def _cmd(c):
    return (c.bank, c.index, tuple(bytes(a) for a in c.args))


def _cond(c):
    return (c.next_state_id, bytes(c.test_ezl), tuple(_cmd(x) for x in c.pass_commands),
            tuple(_cond(s) for s in c.subconditions))


def esd_signature(esd):
    return {mk: {sid: (tuple(_cmd(c) for c in st.enter_commands), tuple(_cmd(c) for c in st.exit_commands),
                       tuple(_cmd(c) for c in st.ongoing_commands), tuple(_cond(c) for c in st.conditions))
                 for sid, st in sm.items()} for mk, sm in esd.state_machines.items()}


def decompile(src, out):
    e = ChrESD.from_path(src)
    with open(out, "w", encoding="utf-8") as f:
        for k in e.state_machines:
            f.write(e.to_esp(state_machine_index=k) + "\n\n")
    print("wrote", out)


def write_verified(esd, out, reference_signature):
    data = esd.to_bytes()
    back = ChrESD.from_bytes(data)
    if esd_signature(back) != reference_signature:
        raise RuntimeError("written ESD does not read back as intended")
    with open(out, "wb") as f:
        f.write(data)
    return len(data)


def roundtrip(src, out):
    e = ChrESD.from_path(src)
    n = write_verified(e, out, esd_signature(ChrESD.from_path(src)))
    print(f"wrote {out} ({n} bytes), semantically identical to vanilla")


if __name__ == "__main__":
    {"decompile": decompile, "roundtrip": roundtrip}[sys.argv[1]](sys.argv[2], sys.argv[3])
