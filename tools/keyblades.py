"""SoraSouls – Keyblade collection (v63). Imported by build_abilities.py (params/events/text) and make_keyblades.py
(models). User choices 2026-10-07: Oathkeeper, Oblivion, Ultima Weapon, Fenrir, Star Seeker, Hidden Dragon;
"Themed" boss drops; "KH2-inspired perks".

Every Keyblade is a copy of the Kingdom Key row (1311000 = Broadsword moves + CanCastSorceries, no stat
requirements), so R1/R2 and L1+R1 casting work the same. Fenrir is the exception: it cannot cast (KH2: Negative
Combo – all offence). Each has its own model WP_A_<model> (tools/make_keyblades.py, from the user's OpenKH FBX
exports of the listed KH2 files) and up to three equipped SpEffects (EquipParamWeapon.EquippedSpecialEffect0-2):
  stamina   copy of SpEffect 6890 (Grass Crest Shield: StaminaRecoverySpeedChange +10)
  regen     copy of SpEffect 6740 (Sanctus: HPPointsLost -2 every 2 s), HP per tick set per Keyblade
  spells    copy of SpEffect 2050 (Bellowing Dragoncrest Ring, sorceries x1.2), multiplier set to 1.1
  critical  SpEffect 36 itself (Hornet Ring: ThrowCondition 5 = stronger backstabs/ripostes)
Drops: one event per Keyblade waits for the boss-defeated flag (verified in each map's vanilla EMEVD: the flag is
set right after CharacterDead(<boss>)) and awards a one-item lot once. Beating the boss before installing still
gives the Keyblade on the next load.
Model ids 292-297 are unused by every vanilla EquipParamWeapon row. If ModEngine2 cannot load NEW part files in DSR
(unconfirmed – first in-game test), the Keyblades will appear invisible; fallback = reuse vanilla model slots.
"""

import keyblade_icons

KINGDOM_KEY = 1311000
REGEN_TEMPLATE, STAMINA_TEMPLATE, SPELL_TEMPLATE, HORNET = 6740, 6890, 2050, 36
LOT_TEMPLATE = 100000

KEYBLADES = [
    dict(key="StarSeeker", name="Star Seeker", fbx="W_EX010_30", model=292, weapon=1313000, boss=3,
         boss_name="Bell Gargoyles", event=9825, lot=9801000,
         phys=115, str_=30, dex=70, int_=112, weight=2.0, cast=True, perks=dict(stamina=10),
         summary="Light Keyblade. Faster stamina",
         long="\nA Keyblade that shines like a star\nabove distant worlds.\n\nLight and quick; favours dexterity.\nWhile equipped: stamina recovers faster.\n\nHold L1 + R1: cast attuned magic.\nRequires no stats."),
    dict(key="HiddenDragon", name="Hidden Dragon", fbx="W_EX010_40", model=293, weapon=1314000, boss=2,
         boss_name="Gaping Dragon", event=9826, lot=9801010,
         phys=130, str_=40, dex=40, int_=160, weight=3.0, cast=True, perks=dict(spells=1.1),
         summary="Magic Keyblade. Stronger spells",
         long="\nA Keyblade in which a dragon sleeps.\n\nIts magic grows with intelligence\nmore than any other Keyblade.\nWhile equipped: sorceries +10%.\n\nHold L1 + R1: cast attuned magic.\nRequires no stats."),
    dict(key="Fenrir", name="Fenrir", fbx="W_EX010_M0", model=294, weapon=1315000, boss=5,
         boss_name="Great Grey Wolf Sif", event=9827, lot=9801020,
         phys=185, str_=90, dex=30, int_=0, weight=6.0, cast=False, perks={},
         summary="Heavy Keyblade. Cannot cast",
         long="\nA Keyblade named for the great wolf.\n\nThe hardest-hitting Keyblade, driven\nby strength. Its power leaves no room\nfor magic: it cannot cast spells.\n\nRequires no stats."),
    dict(key="Oathkeeper", name="Oathkeeper", fbx="W_EX010_10", model=295, weapon=1316000, boss=12,
         boss_name="Ornstein & Smough", event=9828, lot=9801030,
         phys=175, str_=55, dex=55, int_=125, weight=3.0, cast=True, perks=dict(regen=2),
         summary="Balanced Keyblade. Slowly restores HP",
         long="\nA Keyblade born of a promise to\nreturn.\n\nBalanced strength and dexterity.\nWhile equipped: slowly restores HP.\n\nHold L1 + R1: cast attuned magic.\nRequires no stats."),
    dict(key="Oblivion", name="Oblivion", fbx="W_EX010_20", model=296, weapon=1317000, boss=13,
         boss_name="Four Kings", event=9829, lot=9801040,
         phys=190, str_=40, dex=80, int_=125, weight=3.5, cast=True, perks=dict(critical=True),
         summary="Dark Keyblade. Stronger critical hits",
         long="\nA Keyblade drawn from the dark\nbetween worlds.\n\nFavours dexterity.\nWhile equipped: backstabs and\nripostes hit harder.\n\nHold L1 + R1: cast attuned magic.\nRequires no stats."),
    dict(key="Ultima", name="Ultima Weapon", fbx="W_EX010_N0", model=297, weapon=1318000, boss=14,
         boss_name="Seath the Scaleless", event=9830, lot=9801050,
         phys=210, str_=60, dex=60, int_=150, weight=3.0, cast=True, perks=dict(regen=2, stamina=10, spells=1.1),
         summary="The ultimate Keyblade", thicken=0.004,
         long="\nThe ultimate Keyblade.\n\nStrong in every way.\nWhile equipped: slowly restores HP,\nstamina recovers faster and\nsorceries +10%.\n\nHold L1 + R1: cast attuned magic.\nRequires no stats."),
]
# v115 (user: "match DSR progress"): Keyblades can't be upgraded, so each one's base damage stands in for a vanilla
# weapon upgraded to the level a player typically has when its boss falls (Longsword 80 on the normal path: +5 120,
# +8 144, +10 160, +12 176, +15 200): Star Seeker 115 (Bell Gargoyles, light), Hidden Dragon 130 (Gaping Dragon, magic
# Keyblade), Fenrir 185 (Sif, heavy, no magic), Oathkeeper 175 (O&S), Oblivion 190 (Four Kings), Ultima 210 (Seath).
# Before: 110 / 115 / 165 / 150 / 160 / 190. Scaling unchanged.
SPEFFECT_BASE = 97600   # 97600 + 10*index + slot
# TEST ONLY (turn off for release, like the DLL's TEST_KEYS): event 9831 gives all six Keyblades once on the next
# load, so their models can be checked without beating the bosses. The boss drops still happen later (duplicates).
KEYBLADE_TEST, TEST_EVENT = False, 9831   # v115: off (user: remove test helpers)


def build_keyblade_params(gp, get_param, copy_row):
    w, lot, sp = get_param(gp, "EquipParamWeapon"), get_param(gp, "ItemLotParam"), get_param(gp, "SpEffectParam")
    for i, kb in enumerate(KEYBLADES):
        r = copy_row(w, KINGDOM_KEY, kb["weapon"], f"SoraSouls {kb['name']}")
        r.WeaponModel = kb["model"]
        r.WeaponIcon = keyblade_icons.ICON_ID[kb["key"]]      # v116: own menu icon (keyblade_icons.py)
        r.BasePhysicalDamage = kb["phys"]
        r.StrengthScaling, r.DexterityScaling, r.IntelligenceScaling = float(kb["str_"]), float(kb["dex"]), float(kb["int_"])
        r.Weight = kb["weight"]
        r.CanCastSorceries = 1 if kb["cast"] else 0
        effects = []
        for slot, (perk, val) in enumerate(kb["perks"].items()):
            if perk == "critical":
                effects.append(HORNET)
                continue
            sid = SPEFFECT_BASE + 10 * i + slot
            tmpl = {"stamina": STAMINA_TEMPLATE, "regen": REGEN_TEMPLATE, "spells": SPELL_TEMPLATE}[perk]
            e = copy_row(sp, tmpl, sid, f"SoraSouls {kb['name']} {perk}")
            if perk == "stamina":
                e.StaminaRecoverySpeedChange = val
            elif perk == "regen":
                e.HPPointsLost = -val
            else:
                e.MagicAttackPowerMultiplier = e.FireAttackPowerMultiplier = val
                e.LightningAttackPowerMultiplier = e.PhysicalAttackPowerMultiplier = val
            effects.append(sid)
        for slot in range(3):
            setattr(r, f"EquippedSpecialEffect{slot}", effects[slot] if slot < len(effects) else -1)
        l = copy_row(lot, LOT_TEMPLATE, kb["lot"], f"SoraSouls {kb['name']}")
        l.Item1ID, l.Item1Category, l.Item1Count, l.Item1ChancePoints, l.ItemFlag = kb["weapon"], 0, 1, 100, -1
        if any(getattr(l, f"Item{n}ID") not in (0, -1) for n in range(2, 9)) or kb["lot"] + 1 in lot.rows:
            raise RuntimeError(f"keyblade lot {kb['lot']}: extra items or chain")


def keyblade_evs():
    calls, defs = [], []
    for i, kb in enumerate(KEYBLADES):
        calls.append(f"    Event_{kb['event']}()\n")
        defs.append(f'''
@ContinueOnRest({kb['event']})
def Event_{kb['event']}():
    """SoraSouls: {kb['name']} – awarded once after {kb['boss_name']} (flag {kb['boss']})."""
    if ThisEventFlagEnabled():
        return
    MAIN.Await(FlagEnabled({kb['boss']}))
    Wait(3.0)
    AwardItemLot({kb['lot']}, host_only=True)
''')
    if KEYBLADE_TEST:
        calls.append(f"    Event_{TEST_EVENT}()\n")
        awards = "\n".join(f"    AwardItemLot({kb['lot']}, host_only=True)" for kb in KEYBLADES)
        defs.append(f'''
@ContinueOnRest({TEST_EVENT})
def Event_{TEST_EVENT}():
    """SoraSouls TEST: all six Keyblades once (remove for release)."""
    if ThisEventFlagEnabled():
        return
    Wait(5.0)
{awards}
''')
    return "".join(calls), "".join(defs)


def keyblade_text():
    return {"Weapon_name_.fmg": {kb["weapon"]: kb["name"] for kb in KEYBLADES},
            "Weapon_description_.fmg": {kb["weapon"]: "Keyblade" for kb in KEYBLADES},   # v64: shown as the weapon TYPE; longer text overlapped the "Weight Type" label
            "Weapon_long_desc_.fmg": {kb["weapon"]: kb["long"] for kb in KEYBLADES}}


# v118 (user choice "Titanite +0 to +10"): Keyblades upgrade at a blacksmith with normal Titanite (vanilla material
# rows EquipMtrlSetParam 0-10: Titanite Shards to +5, Large Titanite Shards to +10, same costs as any weapon). They use
# their own ReinforceParamWeapon rows 9600-9610 (copies of the normal path rows 0-10) so that
#   * +10 is the cap (the game offers levels while ReinforceParamWeapon[base + level] exists);
#   * damage grows gently: physical x1.00 -> x1.35 at +10 (3.5 % per level), stat scaling x1.00 -> x1.20,
#     so the v115 damage stays the value at the boss where each Keyblade drops and an early one stays useful late.
# DSR has no per-level weapon rows (vanilla Longsword +5 = row 201000 with reinforce row 5), so nothing else is added.
# The max-upgrade achievement link is cleared (MaxUpgradeAchievementID -1) so the mod never unlocks Steam achievements.
UPGRADE_BASE, UPGRADE_MAX = 9600, 10
UPGRADE_PHYS, UPGRADE_SCALING = 0.035, 0.02
UPGRADE_ROWS = (1311000, 1312000) + tuple(kb["weapon"] for kb in KEYBLADES)   # Kingdom Key (melee, hybrid B) + six


def build_keyblade_upgrades(gp, get_param, copy_row):
    rp, w = get_param(gp, "ReinforceParamWeapon"), get_param(gp, "EquipParamWeapon")
    for lv in range(UPGRADE_MAX + 1):
        r = copy_row(rp, lv, UPGRADE_BASE + lv, f"SoraSouls Keyblade +{lv}")
        r.PhysicalDamageMultiplier = 1.0 + UPGRADE_PHYS * lv
        r.StaminaDamageMultiplier = 1.0 + UPGRADE_PHYS * lv
        for f in ("StrengthScalingMultiplier", "DexterityScalingMultiplier", "IntelligenceScalingMultiplier",
                  "FaithScalingMultiplier"):
            setattr(r, f, 1.0 + UPGRADE_SCALING * lv)
    assert UPGRADE_BASE + UPGRADE_MAX + 1 not in rp.rows
    for wid in UPGRADE_ROWS:
        r = w.rows[wid]
        r.WeaponUpgradeID, r.UpgradeMaterialID, r.IsUpgraded = UPGRADE_BASE, 0, 1
        r.MaxUpgradeAchievementID = -1
