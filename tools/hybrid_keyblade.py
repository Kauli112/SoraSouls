"""SoraSouls – Animation research, experiment 1: one Keyblade that both swings and casts (seamless casting v2).

Findings so far (tools/tae32.py on chr/c0000.anibnd, 2026-10-05):
  * Player TAEs are version 0x1000B with 32-bit offsets (soulstruct reads only the 64-bit 0x1000C layout and cannot
    write TAE at all) -> own reader tools/tae32.py; all 116 files parse with every event pointer validated.
  * Spell casts are a00 animations 6200 (right hand) / 6300 (left hand) / 6400 (two-handed), driven by JumpTable
    events 89/90/91. They contain no bullet/dummy event: the engine fires the spell from the hand that holds the
    catalyst (that weapon's dummy 100). a41 3300/4300 are catalyst MELEE bashes (behaviour variation 4101), not casts.
  * Hypothesis: if the right-hand Kingdom Key is itself a catalyst, Sora casts with his Keyblade arm and the spell
    leaves the Keyblade tip (WP_A_0204 dummy 100 sits at the tip) – both v1 issues gone, no TAE edit needed.
    Unknown: which field the player state machine uses to decide "R1 = cast" (CanCastSorceries? WeaponCategory 8?
    motion set 41?) and what R2 then does. Two variants answer that in one in-game test.

  Hybrid A (1311000): Broadsword row (category 1, motion set 23, behaviour 2301) + CanCastSorceries.
  Hybrid B (1312000): Sorcerer's Catalyst row (category 8, CanCastSorceries) + Broadsword motion set/behaviour/damage.
Both: no stat requirements. Given once to the player (event HYBRID_EVENT).

Result experiment 1 (in-game 2026-10-05): BOTH hybrids – R1 casts with the RIGHT arm, R2 = heavy sword attack,
two-handed unchanged; the spell leaves the HAND, not the tip (dummy 100). Weapon category is not the deciding factor.
Experiment 2 (v21): test models from tools/make_dummy_test_models.py – A uses WP_A_1311 (dummy 110 moved to the tip),
B uses WP_A_1312 (dummy 120 moved to the tip). Whichever casts from the tip names the cast dummy.
Result experiment 2: still from the hand -> the origin is the CASTING HAND (character side), not a weapon dummy.

v30 (seamless casting v2): Hybrid A becomes THE "Kingdom Key" (model 204 again). Together with the layout-preserving
state-machine patch (tools/esd_seamless_v2.py): R1 light, R2 heavy, L1 (guard) + R1 = cast from the right hand,
one- and two-handed. Hybrid B stays as a test item.
"""

CATALYST, BROADSWORD, KEY_MODEL = 1300000, 202000, 204
TEST_MODELS = {}   # experiment 2 dummy-test models retired (v30)
HYBRID_A, HYBRID_B = 1311000, 1312000
HYBRID_LOT_BASE, HYBRID_EVENT = 9800360, 9910
GOODS_LOT_TEMPLATE = 100000
GIVE_HYBRIDS = True

SWORD_MOTION_FIELDS = ("AttackAnimationCategory", "BehaviorVariationID", "SpecialAttackCategory")
SWORD_DAMAGE_FIELDS = ("BasePhysicalDamage", "BaseStaminaDamage", "BasePoiseDamage", "StrengthScaling",
                       "DexterityScaling", "DealsNeutralDamage", "DealsStrikeDamage", "VisualSoundEffectsOnHit")
NAMES = {HYBRID_A: ("Kingdom Key", "Sora's Keyblade",
                    "\nThe key chosen by Sora's heart.\n\nR1: light attack   R2: heavy attack\nHold L1 + R1: cast attuned magic\n\nWorks one- and two-handed.\nRequires no stats."),
         HYBRID_B: ("Keyblade Hybrid B (test)", "Catalyst with sword moves",
                    "\nSoraSouls research weapon B.\nCatalyst + Broadsword motion set.\n\nTest: R1, R2, two-handed,\nwhere do spells come from?")}


def build_hybrid_params(gp, get_param, copy_row):
    w, lot = get_param(gp, "EquipParamWeapon"), get_param(gp, "ItemLotParam")
    a = copy_row(w, BROADSWORD, HYBRID_A, "SoraSouls Keyblade Hybrid A")
    a.CanCastSorceries = 1
    b = copy_row(w, CATALYST, HYBRID_B, "SoraSouls Keyblade Hybrid B")
    src = w.rows[BROADSWORD]
    for f in SWORD_MOTION_FIELDS + SWORD_DAMAGE_FIELDS:
        setattr(b, f, getattr(src, f))
    for wid, r in ((HYBRID_A, a), (HYBRID_B, b)):
        r.WeaponModel = TEST_MODELS.get(wid, KEY_MODEL)
        r.RequiredStrength = r.RequiredDexterity = r.RequiredIntelligence = r.RequiredFaith = 0
        r.UpgradeOrigin0 = -1
    for i, wid in enumerate((HYBRID_A, HYBRID_B)):
        lid = HYBRID_LOT_BASE + 10 * i
        l = copy_row(lot, GOODS_LOT_TEMPLATE, lid, f"SoraSouls {NAMES[wid][0]}")
        l.Item1ID, l.Item1Category, l.Item1Count, l.Item1ChancePoints, l.ItemFlag = wid, 0, 1, 100, -1
        if any(getattr(l, f"Item{n}ID") not in (0, -1) for n in range(2, 9)) or lid + 1 in lot.rows:
            raise RuntimeError(f"hybrid lot {lid}: extra items or chain")


def hybrid_evs():
    if not GIVE_HYBRIDS:
        return "", ""
    return f"    Event_{HYBRID_EVENT}()\n", f'''
@ContinueOnRest({HYBRID_EVENT})
def Event_{HYBRID_EVENT}():
    """SoraSouls: animation research – give the two hybrid Keyblades once."""
    if ThisEventFlagEnabled():
        return
    Wait(2.0)
    AwardItemLot({HYBRID_LOT_BASE}, host_only=True)
    AwardItemLot({HYBRID_LOT_BASE + 10}, host_only=True)
'''


def hybrid_text():
    return {"Weapon_name_.fmg": {k: v[0] for k, v in NAMES.items()},
            "Weapon_description_.fmg": {k: v[1] for k, v in NAMES.items()},
            "Weapon_long_desc_.fmg": {k: v[2] for k, v in NAMES.items()}}
