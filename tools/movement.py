"""SoraSouls – Step 6 Movement (High Jump, Aerial Recovery, Glide). Imported by build_abilities.py.

Phase 1 (v18): MOVEMENT TEST KIT. Results (in-game 2026-10-04): grabityRate = ANIMATION SPEED (1.5 faster,
0.5/0.25 slower); IgnoreGravity does nothing; FallDamageMultiplier 0 does not prevent fall damage on the player.
=> High Jump / Glide / Aerial Recovery cannot be done with SpEffects; they move to the animation (TAE) research
   together with seamless casting v2. Speed is used for Quick Run and the Drive Forms (build_abilities/drive_forms).
v19: kit retired (GIVE_MOVE_TESTS False) and removed from the inventory once by MOVE_TEST_CLEANUP_EVENT.
Original notes:
Facts from vanilla params (2026-10-04):
  * SpEffect `grabityRate` (soulstruct name "AnimationSpeedMultiplier", tooltip says animation speed) is set to 0
    only on the Hydra's severed-neck states -> probably gravity, unproven for the player.
  * `IgnoreGravity` (grabityIgnore) exists only on a developer test effect (57 "PG test: gravity disabled").
  * `FallDamageMultiplier` 0.5 is used on two vanilla NPC buffs; tooltip: cannot prevent lethal falls.
  * `MovementType` only has slow modes (Iron Flesh, deep water, chameleon) – no speed-up field exists.
Each kit item is permanent (not consumed) and applies one candidate effect for TEST_DURATION seconds.
"""

TEST_DURATION = 20.0
# (label, field overrides)
MOVE_TESTS = [
    ("Gravity 0.5", dict(AnimationSpeedMultiplier=0.5)),
    ("Gravity 0.25", dict(AnimationSpeedMultiplier=0.25)),
    ("Gravity 1.5", dict(AnimationSpeedMultiplier=1.5)),
    ("No Gravity", dict(IgnoreGravity=1)),
    ("No Fall Damage", dict(FallDamageMultiplier=0.0)),
    ("Glide Candidate", dict(AnimationSpeedMultiplier=0.3, FallDamageMultiplier=0.0)),
]
GIVE_MOVE_TESTS = False
MOVE_TEST_CLEANUP_EVENT = 9909
MOVE_TEST_SPEFFECT_BASE, MOVE_TEST_GOODS_BASE, MOVE_TEST_LOT_BASE = 97545, 9740, 9800900
MOVE_TEST_EVENT = 9908
SPEFFECT_TEMPLATE, GOODS_TEMPLATE, LOT_TEMPLATE = 1090, 500, 100000   # same templates as drive_forms
GOODS_CATEGORY = 0x40000000
STATUS_ICON = 5001

NEUTRAL_FLOATS = ("OutgoingPhysicalDamageMultiplier", "OutgoingMagicDamageMultiplier", "OutgoingFireDamageMultiplier",
                  "OutgoingLightningDamageMultiplier")


def build_movement_params(gp, get_param, copy_row):
    sp, goods, lot = (get_param(gp, n) for n in ("SpEffectParam", "EquipParamGoods", "ItemLotParam"))
    for i, (label, fields) in enumerate(MOVE_TESTS):
        r = copy_row(sp, SPEFFECT_TEMPLATE, MOVE_TEST_SPEFFECT_BASE + i, f"SoraSouls move test {label}")
        # neutralise the Power Within template (no drain, no aura, no damage change)
        r.EffectDuration, r.SpecialState, r.UseVisualEffect, r.StatusIcon = TEST_DURATION, 0, 0, STATUS_ICON
        for f in NEUTRAL_FLOATS:
            setattr(r, f, 1.0)
        r.StaminaRecoverySpeedChange = 0
        r.HPReductionPercentage, r.HPPointsLost, r.UpdateInterval, r.SpecialEffectCategory = 0, 0, 0.0, 0
        for f, v in fields.items():
            setattr(r, f, v)
        g = copy_row(goods, GOODS_TEMPLATE, MOVE_TEST_GOODS_BASE + i, f"SoraSouls move test {label}")
        g.ReferenceType, g.ReferenceID, g.ConsumedOnUse = 2, MOVE_TEST_SPEFFECT_BASE + i, 0
        g.SortIndex, g.MaxHoldQuantity, g.CanBeStored, g.CanBeDropped = 3975 + i, 1, 0, 1
        g.AchievementID = g.CollectionAchievementID = -1
        g.VagrantItemLot = g.VagrantBonusEnemyDropItemLot = g.VagrantItemEnemyDropItemLot = -1
        lid = MOVE_TEST_LOT_BASE + 10 * i
        l = copy_row(lot, LOT_TEMPLATE, lid, f"SoraSouls move test {label}")
        l.Item1ID, l.Item1Category, l.Item1Count, l.Item1ChancePoints = MOVE_TEST_GOODS_BASE + i, GOODS_CATEGORY, 1, 100
        l.ItemFlag = -1
        if any(getattr(l, f"Item{n}ID") not in (0, -1) for n in range(2, 9)) or lid + 1 in lot.rows:
            raise RuntimeError(f"move test lot {lid}: extra items or chain")


def movement_evs():
    if MOVE_TESTS and not GIVE_MOVE_TESTS:
        removes = "\n".join(f"    if PlayerHasGood({MOVE_TEST_GOODS_BASE + i}):\n        RemoveGoodFromPlayer({MOVE_TEST_GOODS_BASE + i}, 1)"
                            for i in range(len(MOVE_TESTS)))
        return f"    Event_{MOVE_TEST_CLEANUP_EVENT}()\n", f'''
@ContinueOnRest({MOVE_TEST_CLEANUP_EVENT})
def Event_{MOVE_TEST_CLEANUP_EVENT}():
    """SoraSouls: remove the retired movement test kit once."""
    if ThisEventFlagEnabled():
        return
    Wait(3.0)
{removes}
'''
    if not MOVE_TESTS:
        return "", ""
    awards = "\n".join(f"    AwardItemLot({MOVE_TEST_LOT_BASE + 10 * i}, host_only=True)" for i in range(len(MOVE_TESTS)))
    return f"    Event_{MOVE_TEST_EVENT}()\n", f'''
@ContinueOnRest({MOVE_TEST_EVENT})
def Event_{MOVE_TEST_EVENT}():
    """SoraSouls: temporary movement test kit, given once."""
    if ThisEventFlagEnabled():
        return
{awards}
'''


def movement_text():
    names, short, long = {}, {}, {}
    for i, (label, fields) in enumerate(MOVE_TESTS):
        gid = MOVE_TEST_GOODS_BASE + i
        names[gid] = f"Move Test: {label}"
        short[gid] = f"{label} for 20 seconds"
        detail = ", ".join(f"{k}={v}" for k, v in fields.items())
        long[gid] = f"\nSoraSouls test item (not consumed).\n{label} for 20 seconds.\n\n{detail}\n\nTest on flat, safe ground."
    return {"Item_name_.fmg": names, "Item_description_.fmg": short, "Item_long_desc_.fmg": long}
