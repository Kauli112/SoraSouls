"""SoraSouls – Step 6 Movement, Glide phase 3 (test builds v34, v35): where does the jump's "no gravity" come from?

Known (in-game 2026-10-06/07):
  * v31/v32: root y in the jump a00_0900 is followed exactly (High Jump +1.5 m, lands on chest-high ledges).
  * v31: root y in the fall loop a00_1500 is ~ignored (gravity wins).
  * v33: a glide built into the jump works (slow drift, then a smooth hand-over to the normal fall).
Question for a SEPARATE glide (user choice 2026-10-07: own trigger, more floaty than v33):
  is gravity suspended by the jump animation's TAE events (then any ESD state that plays an animation with those
  events can glide), or by the engine's built-in jump action (then a glide needs another route)?

Test v34 (crashed at start-up) / v35:
  * Jump a00_0900 back to High Jump only (v32 arc, root_motion_test.jump_arc with JUMP_GLIDE_TEST off).
  * Fall loop a00_1500: gets its own copy of a00_0900's events (v35, appended to a00.tae; v34 shared one list
    -> crash at start-up), vanilla 1500 events left in the file unused, and its root motion set to a floaty glide:
    FALL_SINK m/s down + FALL_FORWARD m/s forward.
  -> every fall floats slowly  = gravity switch is in the TAE events (separate Glide is buildable: ESD state +
     spare animation slot with these events);
     falls stay normal          = it is the engine's jump action (needs another route).
  Expect jump sounds/odd poses each 0.8 s loop – it is a test.
Writes mod copies of chr/c0000.anibnd.dcx (TAE) and chr/c0000_a00_lo.anibnd.dcx (HKX); every other entry is
byte-identical (verified).
Usage: python glide_test.py <vanilla chr dir> <mod chr dir>
"""
import os, sys, struct
import numpy as np
from soulstruct.containers import Binder
import root_motion_test as rmt
from tae32 import TAE32

FALL_SINK = -0.8      # m/s (v33 glide sank at 1.5 m/s – user wants it floatier)
FALL_FORWARD = 2.0    # m/s forward drift
LOOP_S = 0.8          # a00_1500 duration


def fall_glide(s):
    s = s.copy()
    t = np.linspace(0.0, LOOP_S, len(s))
    s[:, 1] = FALL_SINK * t
    s[:, 2] = -FALL_FORWARD * t
    return s


def copy_events(tae_bytes, dst_id, src_id):
    """v35: give dst_id its OWN copy of src_id's events. v34 pointed both animations at one shared event list and
    the game crashed a few seconds after start-up (the engine fixes up each animation's event offsets in place, so a
    shared list is relocated twice – same lesson as the ESD condition records). The source block
    [times, event headers, event data] is appended at the end of the file and every offset inside the copy is
    shifted; the vanilla block and every other animation stay untouched."""
    t = TAE32.parse(tae_bytes)
    by = {a.id: a for a in t.animations}
    ev_n, ev_off, grp_n, grp_off, times_n, times_off, _ = struct.unpack_from("<7i", tae_bytes, by[src_id].offset)
    if grp_n:
        raise RuntimeError("source animation has event groups")
    starts = sorted(struct.unpack_from("<i", tae_bytes, a.offset + 24)[0] for a in t.animations)
    end = min(x for x in starts if x > times_off)
    out = bytearray(tae_bytes)
    while len(out) % 16:
        out.append(0)
    delta = len(out) - times_off
    blk = bytearray(tae_bytes[times_off:end])
    for j in range(ev_n):
        h = ev_off - times_off + 12 * j
        s_off, e_off, d_off = struct.unpack_from("<3i", blk, h)
        if not (times_off <= min(s_off, e_off, d_off) and max(s_off, e_off, d_off) < end):
            raise RuntimeError(f"event {j} points outside the copied block")
        struct.pack_into("<3i", blk, h, s_off + delta, e_off + delta, d_off + delta)
        ptr, = struct.unpack_from("<i", blk, d_off - times_off + 4)
        if ptr:
            struct.pack_into("<i", blk, d_off - times_off + 4, ptr + delta)
    out += blk
    struct.pack_into("<i", out, 0x0C, len(out))
    struct.pack_into("<6i", out, by[dst_id].offset, ev_n, ev_off + delta, 0, 0, times_n, times_off + delta)
    chk = {a.id: a for a in TAE32.parse(bytes(out)).animations}
    assert [(e.type, e.start, e.end, e.payload[:8]) for e in chk[dst_id].events] == \
           [(e.type, e.start, e.end, e.payload[:8]) for e in by[src_id].events]
    assert all(e.data_offset == -1 or e.data_offset >= len(tae_bytes) for e in chk[dst_id].events)
    assert bytes(out[:0x0C]) == tae_bytes[:0x0C] and bytes(out[0x10:len(tae_bytes)]) == \
           bytes(bytearray(tae_bytes[0x10:])[:by[dst_id].offset - 0x10] + out[by[dst_id].offset:by[dst_id].offset + 24]
                 + bytearray(tae_bytes[by[dst_id].offset + 24:]))
    return bytes(out)


def main(van_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    rmt.JUMP_GLIDE_TEST = False
    # HKX: jump = High Jump arc, fall loop = floaty glide motion
    lo = os.path.join(van_dir, "c0000_a00_lo.anibnd.dcx")
    van = {e.entry_id: bytes(e.data) for e in Binder.from_path(lo).entries}
    b = Binder.from_path(lo)
    by = {e.entry_id: e for e in b.entries}
    for aid, fn in ((rmt.JUMP, rmt.jump_arc), (rmt.FALL, fall_glide)):
        d = bytes(by[aid].data)
        by[aid].data = rmt._patch(d, fn(rmt._samples(d)))
    b.write(os.path.join(out_dir, os.path.basename(lo)))
    chk = {e.entry_id: bytes(e.data) for e in Binder.from_path(os.path.join(out_dir, os.path.basename(lo))).entries}
    assert sorted(i for i in chk if chk[i] != van[i]) == [rmt.JUMP, rmt.FALL]
    for aid in (rmt.JUMP, rmt.FALL):
        s = rmt._samples(chk[aid])
        print(f"a00_{aid:04d}: y {s[:, 1].min():.2f}..{s[:, 1].max():.2f}, z end {s[-1, 2]:.2f}")
    # TAE: fall loop uses the jump's events
    anibnd = os.path.join(van_dir, "c0000.anibnd.dcx")
    van_t = {e.entry_id: bytes(e.data) for e in Binder.from_path(anibnd).entries}
    b = Binder.from_path(anibnd)
    e = [x for x in b.entries if x.name.endswith("\\a00.tae")][0]
    e.data = copy_events(bytes(e.data), rmt.FALL, rmt.JUMP)
    out = os.path.join(out_dir, os.path.basename(anibnd))
    b.write(out)
    chk_t = {x.entry_id: bytes(x.data) for x in Binder.from_path(out).entries}
    changed = [i for i in chk_t if chk_t[i] != van_t[i]]
    assert changed == [e.entry_id], changed
    print(f"wrote {out}: a00.tae anim {rmt.FALL} now has its own copy of anim {rmt.JUMP}'s events; "
          f"{len(chk_t) - 1} other entries identical")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
