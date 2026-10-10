"""SoraSouls – Drive Forms (KH2) for Dark Souls Remastered. Imported by build_abilities.py.

Design (user choices 2026-10-04: "Items + refill at rest"; forms Valor, Wisdom, Anti, Master, Final):
  * Each form is a permanent, NOT consumed quick-bar item (template: Humanity, crush animation) that applies a
    timed SpEffect – it never leaves the inventory, so it stays in its quick-bar slot (v12 removed + re-awarded a
    consumable stack on rest; at 0 the game cleared the slot – in-game report 2026-10-04).
  * v14: the item applies only a 1 s invisible TRIGGER SpEffect. The handler catches every use (removes the trigger
    at once and restarts), spends one charge flag and applies the form SpEffect itself. v13 counted only form
    *starts*, so re-using the item while a form was active refreshed it uncounted ("can use the forms infinitely").
  * "Drive gauge" = one plain event flag per charge (CHARGE_FLAG_BASE + 4*i + n); a @RestartOnRest event
    (confirmed to fire from common.emevd in-game) disables them on every rest/load.
  * One form at a time: a handler event per form removes the other forms when one starts.
  * Anti Form: when Valor/Wisdom/Master starts, a random roll (ANTI_CHANCE_FLAGS of ANTI_ROLL_RANGE) replaces it
    with Anti Form (big attack, takes much more damage). Final Form never turns into Anti (as in KH2).
  * Auras: SpEffect.SpecialState picks a visual from SpEffectVfxParam (states verified in vanilla params).
    The SpEffect template is Power Within (timed, icon); its HP drain (HPReductionPercentage 1 % per 1 s
    UpdateInterval) and stacking category 10001 are cleared explicitly. Valor uses the Red Tearstone glow (48);
    Power Within's flame aura (200) is an option to try later.

Verified in-game (v12, 2026-10-04): @RestartOnRest fires from common.emevd; repeat AwardItemLot (ItemFlag -1)
works; auras 48 (Valor, red) visible, 71 (Dusk Crown) invisible, 29/40 both white circles.
v13 test: 41 (Wisdom) ok; 153 glows on the weapon only; 205 not visible on the player; Anti needs to take more
damage (×1.5 -> ×2.0). v14 test: charges/refill/re-use all work; 178 shows BLUE (user prefers yellow -> Master back to 153 gold,
weapon-only); 22 (black phantom) not visible on the player either.
v15: temporary AURA TEST kit -> player picked 50 (yellow body) for Master and 237 (dark) for Anti.
v16: Master = 50 body + 153 gold Keyblade glow (second, visual-only SpEffect EXTRA_VISUAL_SPEFFECT_BASE);
Anti = 237. Test kit no longer given; a one-time event removes the test items (rows kept so old saves stay valid).
"""
import keyblade_icons   # v119: Drive Form menu icons (crown emblem)

ONS = (11510902, 11510903)
AURA = False   # v121: Drive Form auras off – the form outfits (drive_outfits.py) show the form instead
OUTFIT_EVENT_BASE, OUTFIT_FLAG_BASE = 9911, 9984   # v120: forms 0-3 + Anti (4); DLL FORM_FLAG_BASE

# outgoing damage multipliers: (physical, magic, fire, lightning); incoming = multiplier for every damage type taken
FORMS = [
    dict(key="valor", name="Valor Form", unlock=3, unlock_doc="Bell Gargoyles", charges=2, duration=30.0,
         out=(1.3, 0.5, 0.5, 0.5), incoming=1.0, poise=20, stamina=20, speed=1.15, state=48, icon=2096,
         desc="Drive into Valor Form",
         long="\nSora draws on the strength of a friend.\nMelee attacks hit much harder; magic\nis weakened.\n\n"
              "Lasts 30 seconds. 2 uses, refilled\nwhen resting at a bonfire.\n\nMay turn into Anti Form."),
    dict(key="wisdom", name="Wisdom Form", unlock=9, unlock_doc="Chaos Witch Quelaag", charges=2, duration=30.0,
         out=(0.8, 1.5, 1.5, 1.5), incoming=1.0, poise=0, stamina=20, speed=1.10, state=41, icon=2094,
         desc="Drive into Wisdom Form",
         long="\nSora draws on the wisdom of a friend.\nMagic hits much harder; melee is\nweakened.\n\n"
              "Lasts 30 seconds. 2 uses, refilled\nwhen resting at a bonfire.\n\nMay turn into Anti Form."),
    dict(key="master", name="Master Form", unlock=11, unlock_doc="Iron Golem", charges=1, duration=30.0,
         out=(1.25, 1.25, 1.25, 1.25), incoming=1.0, poise=20, stamina=30, speed=1.15, state=50, extra_state=153, icon=2035,
         desc="Drive into Master Form",
         long="\nSora draws on the strength and wisdom\nof his friends. Melee and magic both\nhit harder.\n\n"
              "Lasts 30 seconds. 1 use, refilled\nwhen resting at a bonfire.\n\nMay turn into Anti Form."),
    dict(key="final", name="Final Form", unlock=ONS, unlock_doc="Ornstein & Smough", charges=1, duration=30.0,
         out=(1.4, 1.4, 1.4, 1.4), incoming=0.8, poise=40, stamina=40, speed=1.20, state=40, icon=2099,
         desc="Drive into Final Form",
         long="\nSora's ultimate form. Melee and magic\nhit far harder and damage taken is\nreduced.\n\n"
              "Lasts 30 seconds. 1 use, refilled\nwhen resting at a bonfire.\n\nNever turns into Anti Form."),
]
ANTI = dict(key="anti", name="Anti Form", duration=30.0, out=(1.6, 0.5, 0.5, 0.5), incoming=2.0, poise=30,
            stamina=30, speed=1.25, state=237)
# speed = animation speed (SpEffect grabityRate, verified in-game v18). Whether it stacks with the Quick Run
# passive (x1.10) is untested.
ANTI_FORMS = ("valor", "wisdom", "master")

# ids (all checked free in vanilla params / common + staged map events)
FORM_SPEFFECT_BASE, ANTI_SPEFFECT = 97520, 97524
FORM_GOODS_BASE = 9710
FORM_LOT_BASE = 9800600                      # + 10 * i, 1 item, ItemFlag -1 (re-given only if the item is missing)
UNLOCK_EVENT_BASE, REFILL_EVENT_BASE, HANDLER_EVENT_BASE = 9900, 9920, 9930
ANTI_ROLL_RANGE, ANTI_CHANCE_FLAGS = (9940, 9959), (9940, 9942)   # 3 of 20 flags = 15 %
UNLOCK_TEXT_BASE, ANTI_TEXT, EMPTY_TEXT = 10975200, 10975210, 10975211
CHARGE_FLAG_BASE, CHARGE_BITS = 9960, 4   # form i: charge flags 9960+4i .. (one per charge; free in vanilla)
TRIGGER_SPEFFECT_BASE, TRIGGER_DURATION = 97525, 1.0
# Temporary aura test kit (v15): one non-consumed item per candidate SpecialState, 10 s each, given once.
# Remove (AURA_TESTS = []) once Anti/Master auras are chosen. States with known hard-coded gameplay (24 magic ban,
# 69 revive, 200 Power Within) are excluded; 14 (soul steal) and 9 (gravity user) may carry hidden behaviour. ("gravity user" is only the vfx row's name.)
AURA_TESTS = [("dark", 9), ("dark", 14), ("dark", 43), ("dark", 157), ("dark", 201), ("dark", 237),
              ("yellow", 50), ("yellow", 75), ("yellow", 76), ("yellow", 155), ("yellow", 202)]
AURA_TEST_SPEFFECT_BASE, AURA_TEST_GOODS_BASE, AURA_TEST_LOT_BASE = 97530, 9720, 9800700
AURA_TEST_EVENT, AURA_TEST_DURATION = 9905, 10.0
GIVE_AURA_TESTS = False            # v16: kit retired
AURA_TEST_CLEANUP_EVENT = 9906     # removes the kit items once
EXTRA_VISUAL_SPEFFECT_BASE = 97541  # + form index for forms with "extra_state" (visual only)   # 97525-97528, invisible, no stats
# aura states: 48 Red Tearstone glow (Valor), 41 Water Veil blue (Wisdom), 50 Replenishment yellow body +
# 153 Sunlight Blade gold weapon (Master), 40 Great Magic Barrier white (Final), 237 dark (Anti) – all picked in-game.
# Replaced: 71 Dusk Crown (invisible), 29 Magic Barrier (= Final), 178 (blue), 205 Artorias + 22 black phantom
# (both invisible on the player).
SPEFFECT_TEMPLATE, GOODS_TEMPLATE, LOT_TEMPLATE = 1090, 500, 100000  # Power Within (timed buff), Humanity, goods lot
FORM_STATUS_ICON, ANTI_STATUS_ICON = 5002, 5000
GOODS_CATEGORY = 0x40000000
FORM_SORT_BASE = 3950

for i, f in enumerate(FORMS):
    f.update(speffect=FORM_SPEFFECT_BASE + i, goods=FORM_GOODS_BASE + i, lot=FORM_LOT_BASE + 10 * i,
             unlock_event=UNLOCK_EVENT_BASE + i, refill_event=REFILL_EVENT_BASE + i,
             handler_event=HANDLER_EVENT_BASE + i, unlock_text=UNLOCK_TEXT_BASE + i,
             charge_flag=CHARGE_FLAG_BASE + CHARGE_BITS * i, trigger=TRIGGER_SPEFFECT_BASE + i,
             extra=EXTRA_VISUAL_SPEFFECT_BASE + i if "extra_state" in f and AURA else None)
ANTI["speffect"] = ANTI_SPEFFECT

INCOMING_FIELDS = ("IncomingSlashDamageMultiplier", "IncomingStrikeDamageMultiplier", "IncomingThrustDamageMultiplier",
                   "IncomingNeutralDamageMultiplier", "IncomingMagicDamageMultiplier", "IncomingFireDamageMultiplier",
                   "IncomingLightningDamageMultiplier")
OUT_FIELDS = ("OutgoingPhysicalDamageMultiplier", "OutgoingMagicDamageMultiplier", "OutgoingFireDamageMultiplier",
              "OutgoingLightningDamageMultiplier")


def _form_speffect(sp, copy_row, form, sp_id, icon):
    r = copy_row(sp, SPEFFECT_TEMPLATE, sp_id, f"SoraSouls {form['name']}")
    # v121 (in-game v120: the form outfits change perfectly – user: "please take off the aura"): no aura state, no VFX
    r.EffectDuration, r.StatusIcon = form["duration"], icon
    r.SpecialState, r.UseVisualEffect = (form["state"], 1) if AURA else (0, 0)
    for f, v in zip(OUT_FIELDS, form["out"]):
        setattr(r, f, v)
    for f in INCOMING_FIELDS:
        setattr(r, f, form["incoming"])
    r.PoiseAddition, r.StaminaRecoverySpeedChange = form["poise"], form["stamina"]
    r.AnimationSpeedMultiplier = form.get("speed", 1.0)
    r.HPReductionPercentage, r.HPPointsLost, r.UpdateInterval, r.SpecialEffectCategory = 0, 0, 0.0, 0
    r.AffectsMagic, r.AffectsMiracles = 1, 1
    return r


def _neutral(r):
    """Invisible 1 s marker effect: no stats, no aura, no icon."""
    r.EffectDuration, r.SpecialState, r.UseVisualEffect, r.StatusIcon = TRIGGER_DURATION, 0, 0, -1
    for f in OUT_FIELDS + INCOMING_FIELDS:
        setattr(r, f, 1.0)
    r.PoiseAddition = r.StaminaRecoverySpeedChange = 0
    r.HPReductionPercentage, r.HPPointsLost, r.UpdateInterval, r.SpecialEffectCategory = 0, 0, 0.0, 0


def l_id_next(lot, lid):
    return lid + 1 in lot.rows


def build_drive_params(gp, get_param, copy_row):
    sp, goods, lot = (get_param(gp, n) for n in ("SpEffectParam", "EquipParamGoods", "ItemLotParam"))
    for i, f in enumerate(FORMS):
        _form_speffect(sp, copy_row, f, f["speffect"], FORM_STATUS_ICON)
        g = copy_row(goods, GOODS_TEMPLATE, f["goods"], f"SoraSouls {f['name']}")
        t = copy_row(sp, SPEFFECT_TEMPLATE, f["trigger"], f"SoraSouls {f['name']} trigger")
        _neutral(t)
        g.ReferenceType, g.ReferenceID, g.GoodIcon = 2, f["trigger"], keyblade_icons.DRIVE_ICON_ID[f["key"]]   # v119: crown icon
        g.SortIndex, g.MaxHoldQuantity, g.CanBeStored, g.CanBeDropped = FORM_SORT_BASE + i, 2, 0, 0
        g.ConsumedOnUse = 0  # permanent: charges live in event flags
        g.AchievementID = g.CollectionAchievementID = -1
        g.VagrantItemLot = g.VagrantBonusEnemyDropItemLot = g.VagrantItemEnemyDropItemLot = -1
        l = copy_row(lot, LOT_TEMPLATE, f["lot"], f"SoraSouls {f['name']} refill")
        l.Item1ID, l.Item1Category, l.Item1Count, l.Item1ChancePoints = f["goods"], GOODS_CATEGORY, 1, 100
        l.ItemFlag = -1
        extra = [n for n in range(2, 9) if getattr(l, f"Item{n}ID") not in (0, -1)]
        if extra or f["lot"] + 1 in lot.rows:
            raise RuntimeError(f"drive lot {f['lot']}: extra items {extra} or chain")
    _form_speffect(sp, copy_row, ANTI, ANTI_SPEFFECT, ANTI_STATUS_ICON)
    for f in FORMS:
        if f["extra"]:
            x = copy_row(sp, SPEFFECT_TEMPLATE, f["extra"], f"SoraSouls {f['name']} extra visual")
            _neutral(x)
            x.EffectDuration, x.SpecialState, x.UseVisualEffect = f["duration"], f["extra_state"], 1
    for i, (_, state) in enumerate(AURA_TESTS):
        t = copy_row(sp, SPEFFECT_TEMPLATE, AURA_TEST_SPEFFECT_BASE + i, f"SoraSouls aura test {state}")
        _neutral(t)
        t.EffectDuration, t.SpecialState, t.UseVisualEffect = AURA_TEST_DURATION, state, 1
        g = copy_row(goods, GOODS_TEMPLATE, AURA_TEST_GOODS_BASE + i, f"SoraSouls aura test {state}")
        g.ReferenceType, g.ReferenceID, g.ConsumedOnUse = 2, AURA_TEST_SPEFFECT_BASE + i, 0
        g.SortIndex, g.MaxHoldQuantity, g.CanBeStored, g.CanBeDropped = 3960 + i, 1, 0, 1
        g.AchievementID = g.CollectionAchievementID = -1
        g.VagrantItemLot = g.VagrantBonusEnemyDropItemLot = g.VagrantItemEnemyDropItemLot = -1
        l = copy_row(lot, LOT_TEMPLATE, AURA_TEST_LOT_BASE + 10 * i, f"SoraSouls aura test {state}")
        l.Item1ID, l.Item1Category, l.Item1Count, l.Item1ChancePoints = AURA_TEST_GOODS_BASE + i, GOODS_CATEGORY, 1, 100
        l.ItemFlag = -1
        if any(getattr(l, f"Item{n}ID") not in (0, -1) for n in range(2, 9)) or l_id_next(lot, AURA_TEST_LOT_BASE + 10 * i):
            raise RuntimeError("aura test lot chain")
    return ("SpEffectParam", "EquipParamGoods", "ItemLotParam")


def _await_unlock(flags, indent="    "):
    flags = flags if isinstance(flags, tuple) else (flags,)
    if len(flags) == 1:
        return f"{indent}MAIN.Await(FlagEnabled({flags[0]}))"
    return "\n".join(f"{indent}OR_1.Add(FlagEnabled({x}))" for x in flags) + f"\n{indent}MAIN.Await(OR_1)"


def drive_evs():
    calls, defs = [], []
    all_effects = [f["speffect"] for f in FORMS] + [f["extra"] for f in FORMS if f["extra"]]
    for f in FORMS:
        calls += [f"    Event_{f['unlock_event']}()\n", f"    Event_{f['refill_event']}()\n",
                  f"    Event_{f['handler_event']}()\n"]
        defs.append(f'''
@ContinueOnRest({f['unlock_event']})
def Event_{f['unlock_event']}():
    """SoraSouls: announce {f['name']} once ({f['unlock_doc']})."""
    if ThisEventFlagEnabled():
        return
{_await_unlock(f['unlock'])}
    DisplayStatus({f['unlock_text']})
''')
        defs.append(f'''
@RestartOnRest({f['refill_event']})
def Event_{f['refill_event']}():
    """SoraSouls: Drive gauge – {f['name']} back to {f['charges']} charge(s) on every rest/load once unlocked."""
{_await_unlock(f['unlock'])}
    DisableFlagRange(({f['charge_flag']}, {f['charge_flag'] + f['charges'] - 1}))
    if PlayerDoesNotHaveGood({f['goods']}):
        AwardItemLot({f['lot']}, host_only=True)
''')
        others = "\n".join(f"    RemoveSpecialEffect(PLAYER, {e})" for e in all_effects)
        c0, cn = f["charge_flag"], f["charge_flag"] + f["charges"] - 1
        spend = "\n".join(f"    {'if' if n == 0 else 'elif'} FlagDisabled({c0 + n}):\n        EnableFlag({c0 + n})"
                          for n in range(f["charges"]))
        extra = f"\n    AddSpecialEffect(PLAYER, {f['extra']})" if f["extra"] else ""
        drop_extra = f"\n        RemoveSpecialEffect(PLAYER, {f['extra']})" if f["extra"] else ""
        anti = ""
        if f["key"] in ANTI_FORMS:
            anti = f'''
    DisableFlagRange(({ANTI_ROLL_RANGE[0]}, {ANTI_ROLL_RANGE[1]}))
    EnableRandomFlagInRange(({ANTI_ROLL_RANGE[0]}, {ANTI_ROLL_RANGE[1]}))
    if FlagRangeAnyEnabled(({ANTI_CHANCE_FLAGS[0]}, {ANTI_CHANCE_FLAGS[1]})):
        RemoveSpecialEffect(PLAYER, {f['speffect']}){drop_extra}
        AddSpecialEffect(PLAYER, {ANTI_SPEFFECT})
        DisplayStatus({ANTI_TEXT})'''
        defs.append(f'''
@ContinueOnRest({f['handler_event']})
def Event_{f['handler_event']}():
    """SoraSouls: {f['name']} item used – spend a charge, start the form{', Anti Form roll' if anti else ''}."""
    MAIN.Await(PlayerHasSpecialEffect({f['trigger']}))
    RemoveSpecialEffect(PLAYER, {f['trigger']})
    if PlayerHasSpecialEffect({ANTI_SPEFFECT}):
        return RESTART
    if FlagRangeAllEnabled(({c0}, {cn})):
        DisplayStatus({EMPTY_TEXT})
        return RESTART
{spend}
{others}
    AddSpecialEffect(PLAYER, {f['speffect']}){extra}{anti}
    Wait(0.5)
    return RESTART
''')
    # v120 Drive Form outfits: mirror "form k active" (its SpEffect on Sora) into flag 9984+k for the DLL, which swaps
    # Sora's armor ids to that form's outfit (drive_outfits.py) while the flag is on
    for k, sp_id in enumerate([f["speffect"] for f in FORMS] + [ANTI_SPEFFECT]):
        ev, flag = OUTFIT_EVENT_BASE + k, OUTFIT_FLAG_BASE + k
        calls.append(f"    Event_{ev}()\n")
        defs.append(f'''
@RestartOnRest({ev})
def Event_{ev}():
    """SoraSouls: outfit flag {flag} on while Drive Form SpEffect {sp_id} is on Sora (the DLL swaps the outfit)."""
    DisableFlag({flag})
    MAIN.Await(PlayerHasSpecialEffect({sp_id}))
    EnableFlag({flag})
    MAIN.Await(PlayerDoesNotHaveSpecialEffect({sp_id}))
    DisableFlag({flag})
    return RESTART
''')
    if AURA_TESTS and not GIVE_AURA_TESTS:
        calls.append(f"    Event_{AURA_TEST_CLEANUP_EVENT}()\n")
        removes = "\n".join(f"    if PlayerHasGood({AURA_TEST_GOODS_BASE + i}):\n        RemoveGoodFromPlayer({AURA_TEST_GOODS_BASE + i}, 1)"
                            for i in range(len(AURA_TESTS)))
        defs.append(f'''
@ContinueOnRest({AURA_TEST_CLEANUP_EVENT})
def Event_{AURA_TEST_CLEANUP_EVENT}():
    """SoraSouls: remove the retired aura test kit once."""
    if ThisEventFlagEnabled():
        return
    Wait(3.0)
{removes}
''')
    if AURA_TESTS and GIVE_AURA_TESTS:
        calls.append(f"    Event_{AURA_TEST_EVENT}()\n")
        awards = "\n".join(f"    AwardItemLot({AURA_TEST_LOT_BASE + 10 * i}, host_only=True)" for i in range(len(AURA_TESTS)))
        defs.append(f'''
@ContinueOnRest({AURA_TEST_EVENT})
def Event_{AURA_TEST_EVENT}():
    """SoraSouls: temporary aura test kit, given once."""
    if ThisEventFlagEnabled():
        return
{awards}
''')
    return "".join(calls), "".join(defs)


def drive_text():
    item = {
        "Item_name_.fmg": {f["goods"]: f["name"] for f in FORMS},
        "Item_description_.fmg": {f["goods"]: f["desc"] for f in FORMS},
        "Item_long_desc_.fmg": {f["goods"]: f["long"] for f in FORMS},
    }
    for i, (kind, state) in enumerate(AURA_TESTS):
        gid = AURA_TEST_GOODS_BASE + i
        item["Item_name_.fmg"][gid] = f"Aura Test {state} ({kind})"
        item["Item_description_.fmg"][gid] = f"Shows aura {state} for 10 seconds"
        item["Item_long_desc_.fmg"][gid] = (f"\nSoraSouls test item.\nShows aura state {state} for 10 seconds.\n\n"
                                           f"Candidate {kind} aura – tell Claude\nwhich numbers look right.")
    menu = {f["unlock_text"]: f"Sora gained {f['name']}!" for f in FORMS}
    menu[ANTI_TEXT] = "Anti Form!"   # v121: shorter (user: messages too long for the bar)
    menu[EMPTY_TEXT] = "Not enough Drive!"
    return item, menu
