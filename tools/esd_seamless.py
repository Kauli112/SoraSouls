"""SoraSouls – seamless Keyblade casting via same-size ESD patches (plan + build).

Design (user, 2026-10-06): right hand = cast-capable Keyblade. R1 = light attack, R2 = heavy, L1 (guard) + R1 = cast,
one- and two-handed. Facts from vanilla c0000.esd:
  * a cast-capable right-hand weapon raises ONLY magic request 2 on R1 (exp. 3b); request 3 = left-hand magic
    (state 135 plays 6225 = left, state 138 plays 6325 = right).
  * guard states 77, 80-82, 123-126 already contain magic transitions -> casting while guarding is vanilla.
Rules (applied per condition block, using tools/esd_map.py offsets):
  R-CAST : in blocks used ONLY by non-guard states, IsAtkRequest(2)/IsChainAtkRequest(2) -> 61 (1 byte each) –
           R1 no longer casts outside guard; L1 (left-hand Focus, request 3) is untouched.
  R-ATK  : blocks leading to a LIGHT-attack state (SetAttackType 0/2/5/7) accept request 2 like request 0:
           X(0) -> (X(0) or X(2)) for X in IsAtkRequest / IsChainAtkRequest. The rewritten expression is compiled
           with soulstruct's EZL compiler, decompiled again to verify, and padded to the original size.
Blocks that are shared with guard states, use registers, or don't fit are reported and left unchanged.
"""
import ast, re, sys
import esd_map
from soulstruct.base.ezstate.esd import ezl_parser as P
from soulstruct.base.ezstate.esd.esd_type import ESDType
from soulstruct.base.ezstate.esd.esp_compiler import ESPCompiler

GUARD_STATES = {77, 80, 81, 82, 123, 124, 125, 126}
LIGHT_ATTACK_TYPES = {"0", "2", "5", "7"}
REG_OPS = set(range(0xA7, 0xB7))          # register store 0xA7-0xAE, load 0xAF-0xB6
TRUE_PAD, END = b"\x41\x98", b"\xa1"


def decompile(b):
    P.CLEAR_REGISTERS()
    return P.decompile(b, ESDType.CHR)


def compile_expr(text):
    c = object.__new__(ESPCompiler)
    c.esd_type, c.registers, c.current_to_write = ESDType.CHR, [None] * 8, []
    return c.compile_ezl(ast.parse(text, mode="eval").body)


def fit(body, size):
    room = size - 1 - len(body)
    if room < 0:
        return None
    if room % 2:
        body += b"\xa6"   # 'continue if false' – only short-circuits a false result
        room -= 1
    return body + TRUE_PAD * (room // 2) + END


def light_attack_states(esp_text):
    out = set()
    for m in re.finditer(r'class State_(\d+)\(State\):(.*?)(?=\nclass State_|\Z)', esp_text, re.S):
        enter = re.search(r'def enter\(self\):\n((?:        .*\n)+)', m.group(2))
        if enter and any(a in LIGHT_ATTACK_TYPES for a in re.findall(r'SetAttackType\((\d+)\)', enter.group(1))):
            out.add(int(m.group(1)))
    return out


def plan(esd_path, esp_text):
    raw, base, rows = esd_map.build_map(esd_path)
    light = light_attack_states(esp_text)
    users, nexts, tests = {}, {}, {}
    for r in rows:
        if r["machine"] != 1:
            continue
        users.setdefault(r["offset"], set()).add(r["state"])
        nexts.setdefault(r["offset"], set()).add(r["next_state"])
        tests[r["offset"]] = r["test"]
    edits, skipped = [], []
    r2 = [bytes.fromhex("82 64 00 00 00 42 85"), bytes.fromhex("82 66 00 00 00 42 85")]
    for off, t in sorted(tests.items()):
        st = users[off]
        # --- R-CAST
        if any(x in t for x in r2):
            if st & GUARD_STATES:
                if not st <= GUARD_STATES:
                    skipped.append(("cast block shared with guard states", off, sorted(st)))
                continue
            new = t
            for x in r2:
                new = new.replace(x, x[:5] + bytes([61 + 64]) + x[6:])
            edits.append(("R-CAST", off, t, new, sorted(st)[:6], len(st)))
            continue
        # --- R-ATK
        if nexts[off] & light and (b"\x82\x64\x00\x00\x00\x40\x85" in t or b"\x82\x66\x00\x00\x00\x40\x85" in t):
            if st & GUARD_STATES:
                skipped.append(("attack block used by guard states (left as is)", off, sorted(st)))
                continue
            if any(b in REG_OPS for b in t):
                skipped.append(("uses registers", off, sorted(st)[:6]))
                continue
            src = decompile(t)
            txt = re.sub(r'IsAtkRequest\(0\)(\s*==\s*1)?', '(IsAtkRequest(0) or IsAtkRequest(2))', src)
            txt = re.sub(r'IsChainAtkRequest\(0\)(\s*==\s*1)?', '(IsChainAtkRequest(0) or IsChainAtkRequest(2))', txt)
            body = compile_expr(txt)
            new = fit(body, len(t))
            if new is None:
                skipped.append((f"too long by {len(body) + 1 - len(t)} bytes", off, sorted(st)[:6], src[:120]))
                continue
            check = decompile(new)
            edits.append(("R-ATK", off, t, new, sorted(st)[:6], len(st), src, check))
    return raw, edits, skipped


if __name__ == "__main__":
    esd_path, esp_txt = sys.argv[1], sys.argv[2]
    raw, edits, skipped = plan(esd_path, open(esp_txt).read())
    print(f"R-CAST edits: {sum(1 for e in edits if e[0] == 'R-CAST')}, R-ATK edits: {sum(1 for e in edits if e[0] == 'R-ATK')}, skipped: {len(skipped)}")
    for e in edits:
        if e[0] == "R-ATK":
            print(f"  ATK @{e[1]:#x} states {e[4]}{'+' if e[5] > 6 else ''} ({e[5]})\n     old: {e[6][:150]}\n     new: {e[7][:150]}")
    for s in skipped:
        print("  SKIP", s[0], hex(s[1]), s[2:])
