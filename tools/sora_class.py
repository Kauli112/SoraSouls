"""SoraSouls – Sora's starting class, outfit and Kingdom Key spell scaling (v44). Imported by build_abilities.py.

User choices (2026-10-07): "Light clothes", "Balanced hybrid" stats, Kingdom Key spells "Scale with INT" at about 80 %
of a Sorcerer's Catalyst.

Outfit: Sora's model replaces the Knight set (EquipParamProtector 390000-393000, 24.9 weight -> 27.9/50 = fat roll
with the Kingdom Key). Now light clothes: 4.5 weight total, low defence, no poise. Start: 7.5 / 51 = 15 % = fast roll.
Reinforcement: the Knight set has no per-level rows (verified: 39x001-39x010 do not exist); upgrades multiply these
base values. The loop would also handle per-level copies if a set had them.
Stats: the Knight's level-4 total (86) redistributed for a Keyblade-first, magic-second Sora; ATT 12 = 2 slots.
Spell scaling: a catalyst's Magic Adjust is 100 + IntelligenceScaling x curve(INT) (Sorcerer's Catalyst, scaling 140:
109 @ INT 10, 142 @ 20, 211 @ 40, 240 @ 99 – Fextralife). The Kingdom Key had IntelligenceScaling 0 (flat 100).
It now gets 80 % of the catalyst's scaling (112) on its own correction curve (type 0, shared with STR/DEX) – to be
confirmed in-game: spells should get slightly stronger as INT rises.
"""

KNIGHT_ROWS = (2001, 3001)
STATS = dict(Vitality=12, Attunement=12, Endurance=11, Strength=11, Dexterity=13, Intelligence=12, Faith=8, Resistance=7)
KNIGHT_TOTAL = 86

# id: (name, weight, physical, magic, fire, lightning, poison/toxic, bleed, curse)
OUTFIT = {
    390000: ("Sora's Hair", 0.5, 4, 4, 4, 4, 3, 3, 3),
    391000: ("Sora's Jacket", 2.0, 12, 10, 10, 10, 8, 8, 6),
    392000: ("Sora's Gloves", 0.5, 4, 3, 3, 3, 3, 3, 2),
    393000: ("Sora's Shoes", 1.5, 7, 6, 6, 6, 5, 5, 4),
}
OUTFIT_DESC = {
    390000: ("Sora's trademark spiky hair", "\nNo helm could hold it down.\n\nLight as air; offers almost no\nprotection."),
    391000: ("Sora's jacket", "\nThe jacket Sora wears on his journey.\n\nLight clothes made for running and\ndodging, not for taking hits."),
    392000: ("Sora's gloves", "\nFingerless gloves that give Sora a\nsure grip on his Keyblade."),
    393000: ("Sora's shoes", "\nOversized shoes, somehow perfect\nfor jumping and gliding."),
}

KINGDOM_KEY = 1311000
CATALYST = 1300000
SPELL_SCALING_SHARE = 0.8


def build_class_params(gp, get_param):
    ci, pr, wp = (get_param(gp, n) for n in ("CharaInitParam", "EquipParamProtector", "EquipParamWeapon"))
    if sum(STATS.values()) != KNIGHT_TOTAL or sum(getattr(ci.rows[3001], k) for k in STATS) != KNIGHT_TOTAL:
        raise RuntimeError("stat total no longer matches the Knight's")
    for rid in KNIGHT_ROWS:
        for k, v in STATS.items():
            setattr(ci.rows[rid], k, v)
    for aid, (_, weight, phys, mag, fire, light, poison, bleed, curse) in OUTFIT.items():
        base = pr.rows[aid]
        new = dict(PhysicalDefense=phys, MagicDefense=mag, FireDefense=fire, LightningDefense=light,
                   PoisonResistance=poison, ToxicResistance=poison, BleedResistance=bleed, CurseResistance=curse)
        ratios = {}
        for k, v in new.items():   # reinforced copies (+1..+10 = aid+1..aid+10) keep their growth relative to +0
            ratios[k] = [(pr.rows[aid + n], getattr(pr.rows[aid + n], k) / getattr(base, k) if getattr(base, k) else 1.0)
                         for n in range(1, 11) if aid + n in pr.rows]
        for k, v in new.items():
            for r, ratio in ratios[k]:
                setattr(r, k, round(v * ratio))
            setattr(base, k, v)
        for r in [base] + [pr.rows[aid + n] for n in range(1, 11) if aid + n in pr.rows]:
            r.Weight, r.Poise = weight, 0
            r.SlashDefense = r.StrikeDefense = r.ThrustDefense = 0
    # Face showing through Sora's head: v45 HideFlag0 = 1 (no effect) and v46 face scale 0.4 (shrank Sora's head part
    # too) are both reverted in v47 – the fix is geometric, see tools/scale_sora_head.py.
    wp.rows[KINGDOM_KEY].IntelligenceScaling = round(wp.rows[CATALYST].IntelligenceScaling * SPELL_SCALING_SHARE)


def class_text():
    return {"Armor_name_.fmg": {k: v[0] for k, v in OUTFIT.items()},
            "Armor_description_.fmg": {k: OUTFIT_DESC[k][0] for k in OUTFIT},
            "Armor_long_desc_.fmg": {k: OUTFIT_DESC[k][1] for k in OUTFIT}}
