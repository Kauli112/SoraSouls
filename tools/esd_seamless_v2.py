"""SoraSouls – seamless Keyblade casting v2 (layout-preserving copy-on-write, tools/esd_rewrite.py).

Setup: right hand = cast-capable Keyblade (R1 raises ONLY magic request 2; request 3 = left-hand magic).
Goal: R1 = light attack, R2 = heavy (unchanged), L1 (guard) + R1 = cast – one- and two-handed.
For every NON-guard state of machine 1 (guard states – see GUARD_STATES – keep the vanilla records):
  R-CAST  conditions testing IsAtkRequest(2)/IsChainAtkRequest(2): argument 2 -> 61 (unused) – no R1 cast.
  R-ATK   conditions that lead to a LIGHT-attack state (SetAttackType 0/2/5/7), and their group parents:
          each IsAtkRequest(0) / IsChainAtkRequest(0) call becomes "X(0) X(2) or" (postfix) – request 2 counts
          as R1. Works inside register-using tests too (the register then stores the OR result).
Modified condition copies are shared by all non-guard states (memoised per original record); guard states and
machine 0 are untouched. Vanilla catalysts in the right hand behave the same way (R1 bash, L1+R1 cast).
"""
import re, struct, sys
import esd_rewrite

# v30: guard loops only. v40 (bug 2026-10-07: "holding L1 then clicking R1" sometimes gave a light attack): pressing
# R1 right after L1 lands in the guard-RAISE states (75/76, other grip 121/122) or a block reaction (83-85, 129-131),
# which v30 treated as non-guard. They now keep their vanilla records too (their chain magic transitions -> cast).
# Guard-LOWERING states 78/79/127/128 (L1 released) and parry 86 stay non-guard.
GUARD_STATES = {77, 80, 81, 82, 123, 124, 125, 126,     # v30: guard loops
                75, 76, 121, 122, 83, 84, 85, 129, 130, 131}   # v40: guard raise + block reactions
LIGHT_TYPES = {"0", "2", "5", "7"}


def call(f, a):
    return bytes([0x82]) + f.to_bytes(4, "little") + bytes([a + 64, 0x85])


ATK0, ATK2, CH0, CH2 = call(0x64, 0), call(0x64, 2), call(0x66, 0), call(0x66, 2)
ATK61, CH61 = call(0x64, 61), call(0x66, 61)


def light_states(esp_text):
    out = set()
    for m in re.finditer(r'class State_(\d+)\(State\):(.*?)(?=\nclass State_|\Z)', esp_text, re.S):
        enter = re.search(r'def enter\(self\):\n((?:        .*\n)+)', m.group(2))
        if enter and set(re.findall(r'SetAttackType\((\d+)\)', enter.group(1))) & LIGHT_TYPES:
            out.add(int(m.group(1)))
    return out


def build(src, out, esp_text, report=print, retarget_states=None):
    """retarget_states: {old state id: new state id} for machine-1 transitions (v72 ladder: down step -> slide)."""
    import esd_cow
    _, states = esd_cow.state_offsets(src)
    rw = esd_rewrite.Rewriter(src)
    d = rw.d
    Q = lambda o, n=1: list(struct.unpack_from(f"<{n}q", d, o))
    sid_at = {off: sid for (mk, sid), off in states.items()}
    light = light_states(esp_text)
    memo, stats = {}, {"cast": 0, "atk": 0, "conds": 0, "retarget": 0}
    retarget = {states[(1, a)]: states[(1, b)] for a, b in (retarget_states or {}).items()}

    def leads_to_light(c):
        rec = Q(c, 7)
        if rec[0] != -1 and sid_at.get(rec[0]) in light:
            return True
        return rec[3] != -1 and rec[4] and any(leads_to_light(s) for s in Q(rec[3], rec[4]))

    def transform(c):
        if c in memo:
            return memo[c]
        rec = Q(c, 7)
        changed = False
        if rec[3] != -1 and rec[4]:
            subs = Q(rec[3], rec[4])
            new_subs = [transform(s) for s in subs]
            if new_subs != subs:
                rec[3] = rw.add_ptr_list(new_subs)
                changed = True
        test = bytes(d[rec[5]:rec[5] + rec[6]]) if rec[5] != -1 else b""
        new = test
        if ATK2 in new or CH2 in new:
            new = new.replace(ATK2, ATK61).replace(CH2, CH61)
            stats["cast"] += 1
        if (ATK0 in new or CH0 in new) and leads_to_light(c):
            new = new.replace(ATK0, ATK0 + ATK2 + b"\x99").replace(CH0, CH0 + CH2 + b"\x99")
            stats["atk"] += 1
        if new != test:
            rec[5], rec[6] = rw.add_ezl(new), len(new)
            changed = True
        if rec[0] in retarget:
            rec[0] = retarget[rec[0]]
            stats["retarget"] += 1
            changed = True
        res = rw.add_cond(rec) if changed else c
        if changed:
            stats["conds"] += 1
        memo[c] = res
        return res

    touched = 0
    for (mk, sid), so in sorted(states.items()):
        if mk != 1 or sid in GUARD_STATES:   # guard states never start a ladder step
            continue
        _, cp, cn = Q(so, 3)
        if cp == -1 or not cn:
            continue
        conds = Q(cp, cn)
        new = [transform(c) for c in conds]
        if new != conds:
            rw.set_state_conditions(so, rw.add_ptr_list(new), cn)
            touched += 1
    rw.build(out)
    report(f"seamless v2: {touched} states re-pointed, {stats['conds']} condition copies "
           f"({stats['cast']} cast tests disabled, {stats['atk']} light-attack tests widened) -> {out}")
    return stats


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2], open(sys.argv[3]).read())
