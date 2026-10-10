"""SoraSouls – Step 6 Movement, phase 2: root-motion test for High Jump and Glide (test build v31).

Findings (2026-10-06, soulstruct-havok on c0000_a00_lo.anibnd.dcx, Havok 2015 tagfiles):
  * The running jump is a00_0900 (2.0 s). Its root motion (hkaDefaultAnimatedReferenceFrame, 61 samples x/y/z/yaw)
    is purely forward: z 0 -> -6.0 m, y = 0 for the whole animation. The visible hop is only the pelvis bone
    (0.54 -> 1.54 -> 0.11 m), so the character capsule never leaves the ground. That is why DS1 jumps can't reach
    higher ledges.
  * Vertical root motion exists elsewhere (ladders a00_7010-7014: +0.5/+1.54 m; fall start a00_1550: -0.77 m), so the
    engine does read the y column in some states. Unknown: whether it is applied during the jump and the fall loop.
  * Fall loop a00_1500 (0.8 s, looping): root y ~0 (small bob).

Test (one build, two independent questions):
  A) High Jump: a00_0900 gets a parabolic root y arc between frames ARC_START..ARC_END, peak HIGH_JUMP_PEAK m.
     -> Sora jumps visibly higher / reaches ledges  = root y works in the jump.
  B) Glide: a00_1500 gets a steady root y descent of GLIDE_DROP_PER_LOOP m per loop (a slow fall).
     -> slow, steady fall = root motion overrides gravity while falling (glide via a gated fall anim is possible);
        normal or faster fall = gravity is added on top (glide needs another route).
     A descending value is used on purpose: a rising value could leave the player floating up forever if root
     motion overrides gravity.
Patch method: the sample block is located by its exact bytes (must occur once) and overwritten in place with the
same number of floats – no Havok re-serialisation. Every other entry stays byte-identical (verified).
Results v31 (in-game 2026-10-06): A) jump goes higher, Sora lands on chest-high ledges, feels good ->
   kept as High Jump lv1. B) fall "a tiny bit slower" at most: a -2 m/s override would have been obvious, so the
   fall loop's root y does not replace gravity. v32 keeps only A.
Usage: python root_motion_test.py <vanilla c0000_a00_lo.anibnd.dcx> <mod chr dir>
"""
import os, sys, logging
import numpy as np
from soulstruct.containers import Binder

HIGH_JUMP_PEAK = 1.5          # metres of extra capsule height at the top of the arc
ARC_START, ARC_END = 2, 27    # frames (30 fps): take-off 0.07 s .. landing 0.9 s (pelvis arc peaks ~0.3 s)
GLIDE_DROP_PER_LOOP = -1.6    # metres per 0.8 s loop = -2 m/s
GLIDE_TEST = False            # v32: off. Result v31: fall only 'a tiny bit slower' -> fall-loop root motion does NOT override gravity
JUMP, FALL = 900, 1500
# v33 Glide test, route 2: inside the jump animation the engine follows root y without gravity (v31 arc worked),
# so the jump itself rises, then sinks slowly instead of landing. Jump off a ledge: does Sora drift down slowly
# for the rest of the 2 s animation, then hand over to a normal fall?
JUMP_GLIDE_TEST = True
GLIDE_PEAK_FRAME = 14         # peak at ~0.47 s (vanilla arc peaked ~0.48 s)
GLIDE_SINK = -1.5             # m/s after the peak (y crosses take-off height at ~1.5 s, ends ~0.8 m below)
GLIDE_FORWARD = 2.0           # m/s extra forward drift after the peak (+3.1 m total)


def _samples(data):
    logging.disable(logging.CRITICAL)
    from soulstruct.havok.fromsoft.darksouls1r import AnimationHKX
    rf = AnimationHKX.from_bytes(data).animation_container.hkx_animation.extractedMotion
    logging.disable(logging.NOTSET)
    return np.array([[v[0], v[1], v[2], v[3]] for v in rf.referenceFrameSamples], dtype=np.float32)


def _patch(data, new):
    old = _samples(data)
    raw = old.tobytes()
    if data.count(raw) != 1:
        raise RuntimeError("root-motion block not unique")
    i = data.find(raw)
    out = data[:i] + new.astype(np.float32).tobytes() + data[i + len(raw):]
    if not np.allclose(_samples(out), new, atol=1e-6):
        raise RuntimeError("patched samples do not read back")
    return out


def jump_glide(s):
    """v33 Glide test: rise to HIGH_JUMP_PEAK (ease-out) by GLIDE_PEAK_FRAME, then sink at GLIDE_SINK m/s with
    GLIDE_FORWARD m/s extra forward drift until the jump animation ends (2.0 s)."""
    s = s.copy()
    rise = GLIDE_PEAK_FRAME - ARC_START
    for f in range(ARC_START, len(s)):
        if f <= GLIDE_PEAK_FRAME:
            u = (f - ARC_START) / rise
            s[f, 1] += HIGH_JUMP_PEAK * (1 - (1 - u) ** 2)
        else:
            t = (f - GLIDE_PEAK_FRAME) / 30.0
            s[f, 1] += HIGH_JUMP_PEAK + GLIDE_SINK * t
            s[f, 2] -= GLIDE_FORWARD * t          # forward is -z in DSR root motion (roll 700 ends at z -3.94)
    return s


def jump_arc(s):
    if JUMP_GLIDE_TEST:
        return jump_glide(s)
    s = s.copy()
    n = ARC_END - ARC_START
    for f in range(ARC_START, ARC_END + 1):
        u = (f - ARC_START) / n
        s[f, 1] += 4 * HIGH_JUMP_PEAK * u * (1 - u)
    return s


def glide_fall(s):
    s = s.copy()
    s[:, 1] = np.linspace(0.0, GLIDE_DROP_PER_LOOP, len(s))
    return s


def main(src, out_dir):
    van = {e.entry_id: bytes(e.data) for e in Binder.from_path(src).entries}
    b = Binder.from_path(src)
    by_id = {e.entry_id: e for e in b.entries}
    for aid, fn in ((JUMP, jump_arc), (FALL, glide_fall))[:2 if GLIDE_TEST else 1]:
        e = by_id[aid]
        if not e.name.endswith(f"a00_{aid:04d}.hkx"):
            raise RuntimeError(f"entry {aid} is {e.name}")
        e.data = _patch(bytes(e.data), fn(_samples(bytes(e.data))))
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, os.path.basename(src))
    b.write(out)
    chk = {e.entry_id: bytes(e.data) for e in Binder.from_path(out).entries}
    assert set(chk) == set(van)
    changed = sorted(i for i in chk if chk[i] != van[i])
    assert changed == ([JUMP, FALL] if GLIDE_TEST else [JUMP]), changed
    for aid in changed:
        s = _samples(chk[aid])
        print(f"a00_{aid:04d}: y min {s[:, 1].min():.2f} max {s[:, 1].max():.2f}, z end {s[-1, 2]:.2f}, "
              f"{len(chk[aid])} bytes (vanilla {len(van[aid])})")
    print(f"wrote {out}: {len(changed)} entries changed, {len(chk) - len(changed)} identical")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
