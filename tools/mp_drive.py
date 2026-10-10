"""SoraSouls – KH-style MP Charge and Drive gauge: event side (v68). Imported by build_abilities.py.
User choices 2026-10-08: MP = "KH2 MP Charge"; Drive gauge filled by "Both" (defeating enemies and taking damage).

The work is done by the add-on DLL (dll/sora_glide.c, section "MP Charge / Drive gauge"); it talks to the game
through plain event flags, and these events only show the messages:
  9832  set by the DLL while MP is charging        -> event 9835 shows "MP Charge..." when it turns on
  9833  set by the DLL when MP has been restored   -> event 9836 shows "MP restored!" and clears it
  9834  set by the DLL when the Drive gauge filled -> event 9837 shows "Drive gauge full! ..." and clears it
The DLL restores Drive uses by clearing spent charge flags (drive_forms.py CHARGE_FLAG_BASE 9960 + 4*i + n).
Ids 9832-9837 and text 10975400-10975402 verified unused (vanilla + every SoraSouls tool).
"""
import drive_forms

MP_CHARGING, MP_RESTORED, DRIVE_RESTORED = 9832, 9833, 9834
EV_CHARGE_MSG, EV_MP_MSG, EV_DRIVE_MSG = 9835, 9836, 9837
# v71 (in-game v70: "whenever a message is played I cannot attack or cast"; "MP restored" never showed): the
# DisplayStatus pop-ups block attack/cast input while shown. The HUD overlay now shows these states itself, so the
# three message events are no longer built (ids stay reserved).
MESSAGE_EVENTS = False
# v71 Drive "on hit" (user: "Drive should fill on hit not on kill"): a permanent, invisible sensor SpEffect on Sora
# whose SpecialEffectOnAttack (vanilla mechanism of SpEffect 2240 "HP drain" -> 2241) applies a 0.3 s self-only
# marker when his attack lands. Event 9853 turns each marker into flag 9854; the DLL counts and clears that flag.
# Event 9852 re-applies the sensor every 5 s (death/loads drop SpEffects). Ids 9852-9854, SpEffect 97660-97661 free.
SENSOR_SPEFFECT, HIT_MARKER_SPEFFECT = 97660, 97661
SENSOR_EVENT, HIT_EVENT, HIT_FLAG = 9852, 9853, 9854
SENSOR_TEMPLATE, MARKER_TEMPLATE = 2240, 2241
HIT_SENSOR = False   # v72: in-game v71 the marker never reached Sora; the DLL now tracks enemy HP instead
# TEST ONLY (turn off for release): event 9838 gives all four Drive Form items once on the next load, so the gauge can
# be tested on a new save before the unlocking bosses. Each form starts with its full charges.
DRIVE_TEST, DRIVE_TEST_EVENT = False, 9838   # v115: off
# TEST ONLY (off for release): event 9839 gives every SoraSouls spell once (their normal boss unlocks still announce
# later; the lots carry ItemFlags so nothing is given twice). spell lots come from build_abilities.SPELLS.
SPELL_TEST, SPELL_TEST_EVENT = False, 9839   # v115: off
TEXT_BASE = 10975400
TEXTS = {TEXT_BASE: "MP Charge...", TEXT_BASE + 1: "MP restored!",
         TEXT_BASE + 2: "Drive gauge full! A Drive Form use is restored."}
DRIVE_NOTE = "\n\nThe Drive gauge also restores uses:\nit fills as Sora lands hits and\ntakes damage."
MAGIC_NOTE = ("\n\nAll Sora's spells share one MP pool.\nWhen MP runs out, it recharges fully\nafter a short wait "
              "(MP Charge).")


def build_mp_drive_params(gp, get_param, copy_row):
    if not HIT_SENSOR:
        return
    sp = get_param(gp, "SpEffectParam")
    s = copy_row(sp, SENSOR_TEMPLATE, SENSOR_SPEFFECT, "SoraSouls Drive hit sensor")
    s.SpecialEffectOnAttack, s.StatusIcon, s.EffectDuration = HIT_MARKER_SPEFFECT, -1, -1.0
    m = copy_row(sp, MARKER_TEMPLATE, HIT_MARKER_SPEFFECT, "SoraSouls Drive hit marker")
    m.HPPointsLost, m.EffectDuration, m.UpdateInterval, m.StatusIcon = 0, 0.3, 0.0, -1
    m.CanAffectEnemy, m.CanAffectAlly = 0, 0          # only Sora himself can carry the marker


def mp_drive_evs(spell_lots=()):
    calls = "".join(f"    Event_{e}()\n" for e in (SENSOR_EVENT, HIT_EVENT)) if HIT_SENSOR else ""
    defs = "" if not HIT_SENSOR else f'''
@RestartOnRest({SENSOR_EVENT})
def Event_{SENSOR_EVENT}():
    """SoraSouls: keep the Drive hit sensor on Sora."""
    AddSpecialEffect(PLAYER, {SENSOR_SPEFFECT})
    Wait(5.0)
    return RESTART


@RestartOnRest({HIT_EVENT})
def Event_{HIT_EVENT}():
    """SoraSouls: Sora's attack landed (marker {HIT_MARKER_SPEFFECT}) -> flag {HIT_FLAG} for the DLL's Drive gauge."""
    MAIN.Await(PlayerHasSpecialEffect({HIT_MARKER_SPEFFECT}))
    RemoveSpecialEffect(PLAYER, {HIT_MARKER_SPEFFECT})
    EnableFlag({HIT_FLAG})
    Wait(0.1)
    return RESTART
'''
    if MESSAGE_EVENTS:
        calls += "".join(f"    Event_{e}()\n" for e in (EV_CHARGE_MSG, EV_MP_MSG, EV_DRIVE_MSG))
        defs += f'''
@RestartOnRest({EV_CHARGE_MSG})
def Event_{EV_CHARGE_MSG}():
    """SoraSouls: 'MP Charge...' each time the DLL starts an MP charge (flag {MP_CHARGING})."""
    MAIN.Await(FlagEnabled({MP_CHARGING}))
    DisplayStatus({TEXT_BASE})
    MAIN.Await(FlagDisabled({MP_CHARGING}))
    return RESTART


@RestartOnRest({EV_MP_MSG})
def Event_{EV_MP_MSG}():
    """SoraSouls: 'MP restored!' when the DLL finishes an MP charge (flag {MP_RESTORED})."""
    MAIN.Await(FlagEnabled({MP_RESTORED}))
    DisableFlag({MP_RESTORED})
    DisplayStatus({TEXT_BASE + 1})
    Wait(1.0)
    return RESTART


@RestartOnRest({EV_DRIVE_MSG})
def Event_{EV_DRIVE_MSG}():
    """SoraSouls: Drive gauge filled and a Drive use came back (flag {DRIVE_RESTORED})."""
    MAIN.Await(FlagEnabled({DRIVE_RESTORED}))
    DisableFlag({DRIVE_RESTORED})
    DisplayStatus({TEXT_BASE + 2})
    Wait(1.0)
    return RESTART
'''
    if DRIVE_TEST:
        calls += f"    Event_{DRIVE_TEST_EVENT}()\n"
        awards = "\n".join(f"    AwardItemLot({f['lot']}, host_only=True)" for f in drive_forms.FORMS)
        defs += f'''

@ContinueOnRest({DRIVE_TEST_EVENT})
def Event_{DRIVE_TEST_EVENT}():
    """SoraSouls TEST: all four Drive Form items once (remove for release)."""
    if ThisEventFlagEnabled():
        return
    Wait(5.0)
{awards}
'''
    if SPELL_TEST and spell_lots:
        calls += f"    Event_{SPELL_TEST_EVENT}()\n"
        awards = "\n".join(f"    AwardItemLot({lot}, host_only=True)" for lot in spell_lots)
        defs += f'''

@ContinueOnRest({SPELL_TEST_EVENT})
def Event_{SPELL_TEST_EVENT}():
    """SoraSouls TEST: every Sora spell once (remove for release)."""
    if ThisEventFlagEnabled():
        return
    Wait(6.0)
{awards}
'''
    return calls, defs


def mp_drive_text():
    """(item FMG edits, menu FMG edits): the gauge note on the Drive Form items, and the three messages."""
    return ({"Item_long_desc_.fmg": {f["goods"]: f["long"] + DRIVE_NOTE for f in drive_forms.FORMS}},
            {"Event_text_.fmg": {**TEXTS, drive_forms.EMPTY_TEXT: "Not enough Drive!"}})


# ---- v72 HUD: pop-up messages and the Abilities panel move into the DLL overlay ----------------------------------
# In-game v71: every DisplayStatus pop-up blocks attack/cast input while shown. Each SoraSouls pop-up
# (text ids 10975000-10975999) becomes EnableFlag(HUD_MSG_FLAG_BASE + n); the DLL shows the text in the HUD and
# clears the flag. Flags 9600-9699 verified unused in vanilla (common + all map events) and in every SoraSouls tool.
import re as _re

HUD_MSG_FLAG_BASE, HUD_MSG_FLAG_LAST = 9600, 9699
_OURS = _re.compile(r"DisplayStatus\((10975\d\d\d)\)")


def hud_messages(evs):
    """Returns (evs with our pop-ups replaced, {flag: text id})."""
    ids = sorted({int(x) for x in _OURS.findall(evs)})
    if HUD_MSG_FLAG_BASE + len(ids) - 1 > HUD_MSG_FLAG_LAST:
        raise RuntimeError("HUD message flag range full")
    flag = {t: HUD_MSG_FLAG_BASE + i for i, t in enumerate(ids)}
    return _OURS.sub(lambda m: f"EnableFlag({flag[int(m.group(1))]})", evs), {f: t for t, f in flag.items()}


def _c(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def write_hud_header(path, msg_flags, texts, abilities, extra_msgs=None):
    """dll/hud_data.h – generated; the DLL build includes it. abilities: [(category, name, flag_a, flag_b)],
    learned when either flag is on (0 = always learned, -1 = unused)."""
    cats = []
    for c, *_ in abilities:
        if c not in cats:
            cats.append(c)
    lines = ["/* generated by tools/build_abilities.py (mp_drive.write_hud_header) - do not edit */",
             "typedef struct { int flag; const char *text; } HUD_MSG;",
             "typedef struct { int cat; const char *name; int fa, fb; } HUD_ABIL;",
             f"static const char *HUD_CATS[] = {{ {', '.join(_c(c) for c in cats)} }};",
             f"#define HUD_NCATS {len(cats)}",
             "static const HUD_MSG HUD_MSGS[] = {"]
    lines += [f"    {{ {f}, {_c(texts[t])} }}," for f, t in sorted(msg_flags.items())]
    lines += [f"    {{ {f}, {_c(t)} }}," for f, t in sorted((extra_msgs or {}).items())]   # flags raised directly
    lines += ["};", f"#define HUD_NMSGS {len(msg_flags) + len(extra_msgs or {})}", "static const HUD_ABIL HUD_ABILS[] = {"]
    lines += [f"    {{ {cats.index(c)}, {_c(n)}, {fa}, {fb} }}," for c, n, fa, fb in abilities]
    lines += ["};", f"#define HUD_NABILS {len(abilities)}", ""]
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(lines))
    return path


# v122 (user: "can we add drive recovery items to the game as well?"): KH2's Drive Recovery / High Drive Recovery as
# consumable goods sold by the Moogle (Undead Merchant). Using one applies a 1 s marker SpEffect; an event turns it
# into a flag the DLL reads: Drive Recovery fills half the Drive gauge (50), High Drive Recovery gives back every spent
# Drive Form use. Goods are copies of the Potion row (consumed, drink animation), icons = KH2's own item pictures
# (keyblade_icons.ITEM_ICONS). Carry limits match the potion balance (v115).
import keyblade_icons
DRIVE_ITEMS = [
    dict(key="drive_recovery", name="Drive Recovery", goods=9703, speffect=97516, flag=9989, event=9916,
         shop_row=1176, price=800, max_hold=5, summary="Restores half the Drive gauge",
         long="\nA restorative from distant worlds\nthat fills the heart with strength.\n\nRestores half of the Drive gauge."),
    dict(key="high_drive_recovery", name="High Drive Recovery", goods=9704, speffect=97517, flag=9990, event=9917,
         shop_row=1177, price=4000, max_hold=2, summary="Restores every Drive Form use",
         long="\nA rare restorative crowned with\nlight.\n\nRestores every spent use of\nSora's Drive Forms."),
]
DRIVE_ITEM_GOODS_TEMPLATE, DRIVE_ITEM_SP_TEMPLATE, SHOP_TEMPLATE = 9700, 3020, 1105   # Potion goods, Estus effect


def build_drive_items(gp, get_param, copy_row):
    sp, goods, shop = (get_param(gp, n) for n in ("SpEffectParam", "EquipParamGoods", "ShopLineupParam"))
    for it in DRIVE_ITEMS:
        e = copy_row(sp, DRIVE_ITEM_SP_TEMPLATE, it["speffect"], f"SoraSouls {it['name']}")
        e.HPPointsLost, e.HPReductionPercentage, e.EffectDuration, e.StatusIcon = 0, 0.0, 1.0, -1
        g = copy_row(goods, DRIVE_ITEM_GOODS_TEMPLATE, it["goods"], f"SoraSouls {it['name']}")
        g.ReferenceID, g.GoodIcon, g.MaxHoldQuantity = it["speffect"], keyblade_icons.ITEM_ICON_ID[it["key"]], it["max_hold"]
        s = copy_row(shop, SHOP_TEMPLATE, it["shop_row"], f"SoraSouls {it['name']}")
        s.ItemID, s.ItemType, s.SoulCost, s.InitialQuantity, s.QuantityFlag = it["goods"], 3, it["price"], -1, -1


def drive_item_evs():
    calls = "".join(f"    Event_{it['event']}()\n" for it in DRIVE_ITEMS)
    defs = "".join(f'''
@RestartOnRest({it['event']})
def Event_{it['event']}():
    """SoraSouls: {it['name']} used -> flag {it['flag']} for the DLL's Drive gauge."""
    MAIN.Await(PlayerHasSpecialEffect({it['speffect']}))
    RemoveSpecialEffect(PLAYER, {it['speffect']})
    EnableFlag({it['flag']})
    Wait(1.0)
    return RESTART
''' for it in DRIVE_ITEMS)
    return calls, defs
