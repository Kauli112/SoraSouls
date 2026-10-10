"""SoraSouls – Step 6 Movement, unlocks + levels for High Jump and Glide (v37). Imported by build_abilities.py.

Glide and the extra High Jump levels run in the add-on DLL (dll/sora_glide.c), which reads the event flags set here.
Each level is one event: it waits for the previous level AND its boss, shows "Sora learned …" once, then ends –
ending sets the event's own flag (= the level flag the DLL reads). Levels therefore always unlock in order.

  High Jump LV1  always (built into the jump animation, tools/root_motion_test.py: +1.5 m)
  High Jump LV2  Taurus Demon       flag 11010901 -> event/flag 9823 (DLL: rise x1.5)
  High Jump MAX  Great Grey Wolf Sif flag 5       -> event/flag 9824 (DLL: rise x2.0)
  Glide LV1      Bell Gargoyles     flag 3        -> event/flag 9820 (DLL: sink 2.0 m/s)
  Glide LV2      Gaping Dragon      flag 2        -> event/flag 9821 (DLL: sink 1.3 m/s)
  Glide MAX      Moonlight Butterfly flag 11200900 -> event/flag 9822 (DLL: sink 0.8 m/s = the v36 feel)
Ids 9820-9824 verified unused (tools use 9815-9819 and 9840+); text ids 10975300+.
"""

LEVELS = [
    # (event/flag, boss flag, previous level flag or None, message)
    (9820, 3, None, "Sora learned Glide!"),
    (9821, 2, 9820, "Glide LV2!"),
    (9822, 11200900, 9821, "Glide MAX!"),
    (9823, 11010901, None, "High Jump LV2!"),
    (9824, 5, 9823, "High Jump MAX!"),
]
TEXT_BASE = 10975300


def levels_evs():
    calls, defs = [], []
    for i, (ev, boss, prev, msg) in enumerate(LEVELS):
        calls.append(f"    Event_{ev}()\n")
        if prev is None:
            wait = f"    MAIN.Await(FlagEnabled({boss}))"
        else:
            wait = f"    AND_1.Add(FlagEnabled({prev}))\n    AND_1.Add(FlagEnabled({boss}))\n    MAIN.Await(AND_1)"
        defs.append(f'''
@ContinueOnRest({ev})
def Event_{ev}():
    """SoraSouls: {msg} – level flag read by sora_glide.dll."""
    if ThisEventFlagEnabled():
        return
{wait}
    DisplayStatus({TEXT_BASE + i})
''')
    return "".join(calls), "".join(defs)


def levels_text():
    return {TEXT_BASE + i: msg for i, (_, _, _, msg) in enumerate(LEVELS)}
