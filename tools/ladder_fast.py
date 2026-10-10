"""SoraSouls – fast ladder climb + slide down (v72). User 2026-10-08: "implement a fast climb on ladders up and down
(down being a slide down animation)".

Ladder facts (vanilla c0000.esd + c0000_a00_md.anibnd, 2026-10-08):
  * climbing up = one rung step per animation, alternating a00_7011 / a00_7012 (0.4 s, root y +0.5 m each);
    down = 7021 / 7022 (0.4 s, -0.5 m). States: 236 (7011), 235 (7012), 238 (7021), 237 (7022).
  * DS1 already has a ladder slide: roll/B on a ladder -> State_251 (a00_7000 slide start) -> 7001 slide loop.
Changes:
  1. Climb up x SPEED: in 7011/7012 the hkaSplineCompressedAnimation duration, frameDuration, blockDuration,
     blockInverseDuration and the root-motion duration are rescaled in place (same bytes otherwise, so the same
     poses and the same +0.5 m per step, in 1/SPEED the time). Their TAE event times (a00.tae in c0000.anibnd) are
     scaled the same way, so rung events still fire inside the shorter animation.
  2. Down = slide: every ladder-state condition that would start a down step (target State_237/238) now targets the
     slide start State_251 instead (machine 1, copy-on-write via esd_rewrite – other records untouched).
Usage: python ladder_fast.py <vanilla c0000_a00_md.anibnd.dcx> <mod c0000.anibnd.dcx> <vanilla c0000.esd.dcx>
       <StateMachine_1.esp.py of the vanilla ESD> <out chr dir>
"""
import os, struct, sys
from soulstruct.containers import Binder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tae32 import TAE32

SPEED = 2.0
UP_ANIMS = (7011, 7012)
DOWN_STEP_STATES, SLIDE_STATE = (237, 238), 251


def _f(v):
    return struct.pack("<f", v)


def speed_hkx(data, speed):
    d = bytearray(data)
    import logging
    logging.disable(logging.CRITICAL)
    from soulstruct.havok.fromsoft.darksouls1r import AnimationHKX
    a = AnimationHKX.from_bytes(bytes(data)).animation_container.hkx_animation
    fields = [(a.duration, 2), (a.frameDuration, 1), (a.blockDuration, 1), (a.blockInverseDuration, 1)]
    if abs(a.extractedMotion.duration - a.duration) > 1e-6:
        raise RuntimeError("root motion duration differs from the animation duration")
    for (val, expect), new in zip(fields, (a.duration / speed, a.frameDuration / speed, a.blockDuration / speed,
                                           a.blockInverseDuration * speed)):
        raw = _f(val)
        hits = [i for i in range(len(d) - 3) if d[i:i + 4] == raw]
        if len(hits) != expect:
            raise RuntimeError(f"value {val} found {len(hits)}x, expected {expect}")
        for i in hits:
            d[i:i + 4] = _f(new)
    b = AnimationHKX.from_bytes(bytes(d)).animation_container.hkx_animation
    logging.disable(logging.NOTSET)
    assert abs(b.duration - a.duration / speed) < 1e-6 and abs(b.extractedMotion.duration - a.duration / speed) < 1e-6
    return bytes(d)


def speed_tae(data, anim_ids, speed):
    t = TAE32.parse(data)
    d = bytearray(data)
    done = []
    for a in t.animations:
        if a.id not in anim_ids:
            continue
        _, _, _, _, times_n, times_off, _ = struct.unpack_from("<7i", d, a.offset)
        for k in range(times_n):
            v, = struct.unpack_from("<f", d, times_off + 4 * k)
            struct.pack_into("<f", d, times_off + 4 * k, v / speed)
        done.append((a.id, times_n))
    if sorted(x for x, _ in done) != sorted(anim_ids):
        raise RuntimeError(f"TAE anims found {done}")
    return bytes(d), done


def ladder_esd(vanilla_esd, esp_path, out):
    """Rebuilds the seamless-casting ESD (esd_seamless_v2, from VANILLA – its rewriter needs the vanilla layout) with
    the down-step -> slide retarget added in the same pass."""
    import esd_seamless_v2
    stats = esd_seamless_v2.build(vanilla_esd, out, open(esp_path).read(),
                                  retarget_states={s: SLIDE_STATE for s in DOWN_STEP_STATES})
    if not stats["retarget"]:
        raise RuntimeError("no ladder down-step transition found")


def main(md_src, anibnd_src, vanilla_esd, esp_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    b = Binder.from_path(md_src)
    for e in b.entries:
        name = e.name.split("\\")[-1]
        if name in tuple(f"a00_{i}.hkx" for i in UP_ANIMS):
            e.data = speed_hkx(bytes(e.data), SPEED)
            print(f"{name}: x{SPEED}")
    b.write(os.path.join(out_dir, os.path.basename(md_src)))
    b = Binder.from_path(anibnd_src)
    for e in b.entries:
        if e.name.endswith("a00.tae"):
            e.data, done = speed_tae(bytes(e.data), UP_ANIMS, SPEED)
            print("a00.tae times scaled:", done)
    b.write(os.path.join(out_dir, os.path.basename(anibnd_src)))
    ladder_esd(vanilla_esd, esp_path, os.path.join(out_dir, "c0000.esd.dcx"))


if __name__ == "__main__":
    main(*sys.argv[1:6])
