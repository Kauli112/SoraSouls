"""SoraSouls – Donald & Goofy party summon, prototype (v76). User choices 2026-10-08: "summon item anywhere but you can
cancel it by reusing the item"; "Prototype first" (Dark Souls stand-in looks); "KH roles" (Donald casts and heals,
Goofy tanks with a shield).

How it works (Dark Souls has no "spawn a character" instruction, so they must exist in every map):
  * Params (build_party_params): Donald = copy of the Witch Beatrice co-op summon (NpcParam/CharaInitParam 6520 – robe,
    witch hat, catalyst, sorceries; AI 6521), Goofy = copy of the Solaire co-op summon (6540; AI 6540) holding a Mace
    and a Tower Shield. New rows NpcParam/CharaInitParam 6950 (Donald) / 6951 (Goofy), names "Donald" / "Goofy"
    (NPC_name 6950/6951). Item "Donald & Goofy" (goods 9760, never consumed, applies trigger SpEffect 97670),
    Cure SpEffect 97671 (heals 30 % of Sora's HP).
  * Maps (patch_maps): every main map MSB gets two disabled c0000 characters with those params (entity ids picked
    per map, verified unused) and its event script gets two events:
      summon  – while the party flag 9855 is on AND Sora is inside this map: enable both, team FightingAlly (12:
                targets enemies, targeted by enemies), move them to Sora (copying his draw parent so they load where
                he is). Leaving the map or turning the flag off hides them again. Because the flag is saved, the
                party follows Sora into the next map and after loading.
      cure    – Donald alive, party on, Sora below 35 % HP: Donald's Cure heals Sora 30 %, then waits 30 s.
  * Common events (party_evs): the item toggles flag 9855 ("Donald & Goofy joined/left"); 9856 from a map's cure
    event shows "Donald: Cure!"; the item is given once on load. Messages go to the HUD (mp_drive.hud_messages).
Fallen party members stay down until Sora rests at a bonfire (map reload), as Dark Souls characters do.
Unverified (in-game test decides): whether the summon AIs follow and fight when enabled this way instead of being
summoned from a sign. Fallback: real summon signs placed next to Sora by the same events.
"""
import os, re
import party_logic
from soulstruct.darksouls1r.maps import MSB
from soulstruct.darksouls1r.events import EMEVD

PARTY_FLAG, CURE_FLAG = 9855, 9856
EV_ITEM, EV_CURE_MSG, EV_GIVE = 9857, 9858, 9859
GOODS, LOT, TRIGGER_SP, CURE_SP = 9760, 9801100, 97670, 97671
DONALD, GOOFY = 6950, 6951
NAMES = {DONALD: "Donald", GOOFY: "Goofy"}
TEMPLATES = {DONALD: dict(npc=6520, init=6520, ai=DONALD), GOOFY: dict(npc=6540, init=6540, ai=GOOFY)}
# v83 (in-game v82: they appear – placed by the DLL – but "do not follow or act"): the co-op summon AIs (logic
# 6520/6540) only run for sign-summoned phantoms. New NpcThinkParam rows 6950/6951 use the generic NPC logic 10000
# that the Darkroot bandits run, with their battle scripts: Donald = attack-magic bandit (battle 6804, casts the
# sorceries in his CharaInit), Goofy = warrior bandit (battle 6802). Sight/hearing raised so they join fights.
# Following is done by the DLL (catch-up placement when Sora gets more than a few metres away).
THINK = {DONALD: 6804, GOOFY: 6802}
DONALD_INT = 16
DONALD_CASTER = 6804                                                    # CharaInitParam of the bandit he copies
DONALD_COPY = ("RightHandWeapon1", "RightHandWeapon2", "LeftHandWeapon1", "LeftHandWeapon2", "SpellSlot1",
               "SpellSlot2", "SpellSlot3", "SpellSlot4", "SpellSlot5", "SpellSlot6", "SpellSlot7",
               "Vitality", "Attunement", "Endurance",
               "Strength", "Dexterity", "Intelligence", "Faith", "Resistance", "Humanity")
MODEL = {DONALD: 9560, GOOFY: 9570}                  # armor part model ids (HD_A_9560.partsbnd.dcx, ...)
ARMOR_BASE = {DONALD: 9560000, GOOFY: 9570000}
# v105: off – in-game v104 the helmet face scale squashed the KH2 heads (the helmet) and left the human face as it was
FACE_SCALE = {}       # EquipParamProtector rows (+0/1000/2000/3000 head/body/arms/legs)
# v111: KH2 weapons (make_party_weapons.py): Donald's Mage's Staff = copy of the Sorcerer's Catalyst row with model
# WP_A_0298, Goofy's Knight's Shield = copy of the Tower Shield row with model WP_A_0299 (stats unchanged)
STAFF_WEAPON, STAFF_FROM, STAFF_MODEL = 1319000, 1300000, 298
SHIELD_WEAPON, SHIELD_FROM, SHIELD_MODEL = 1519000, 1501000, 299
# v112 (user: "Goofy should attack with his shield"; "Donald should attack or cast with his staff"): Goofy holds the
# shield in the RIGHT hand (Dark Souls: a right-hand shield attacks with shield bashes; with the left hand empty L1
# still guards with it), mace and talisman removed. Donald: R1 = staff as catalyst (casts), R2 = staff as a club
# (copy of the Club row, model WP_A_0298) – the battle script switches to weapon 2 up close, so he hits with the staff
# instead of casting point-blank; the bandit's leftover leather shield is removed.
STAFF_MELEE, STAFF_MELEE_FROM = 1320000, 800000
GOOFY_GEAR = dict(RightHandWeapon1=SHIELD_WEAPON, RightHandWeapon2=SHIELD_WEAPON, LeftHandWeapon1=-1,
                  LeftHandWeapon2=-1)
TEXT_JOIN, TEXT_LEAVE, TEXT_CURE, TEXT_FAIL = 10975500, 10975501, 10975502, 10975503
TEXTS = {TEXT_JOIN: "Donald & Goofy joined the party!", TEXT_LEAVE: "Donald & Goofy left the party.",
         TEXT_CURE: "Donald: Cure!", TEXT_FAIL: "Donald cast Cure... on himself!"}
# v77 (user: "Donald should be a little bad at healing Sora"): he waits until Sora is lower, heals less, waits longer,
# and 1 time in 3 his Cure goes to himself instead ("Donald cast Cure... on himself!").
CURE_BELOW, CURE_PCT, CURE_WAIT = 0.25, 25.0, 45.0
FAIL_ROLL, FAIL_FLAG = (9976, 9978), 9979        # flags 9976-9979 free (drive charges end at 9975)
# v89 (in-game v88: "their new home location doesn't save immediately ... they walk to that direction or don't follow
# closely"): the AI keeps walking to the home point it planned with until it re-plans. The DLL raises 9980 (Donald) /
# 9981 (Goofy) after moving a lagging member's home point; each map's replan event answers with ReplanAI. Flags
# 9980-9981 verified unused (vanilla events + every SoraSouls tool).
REPLAN_FLAGS = (9980, 9981)
# v77 debug (in-game v76: "Donald and Goofy do not appear"): each map's summon event raises flag 9690 once it has
# enabled and moved them; the DLL shows "Party: placed next to Sora (debug)". Remove with the prototype.
PARTY_DEBUG = False   # v115: the 'Party debug 1-6' / 'placed next to Sora' HUD messages are off
DEBUG_FLAG, DEBUG_TEXT = 9690, "Party: Donald & Goofy placed next to Sora (debug)"
# v78 more debug steps (in-game v77: only "joined the party" showed, never 9690):
DEBUG_STEPS = {9691: "Party debug 1: area script loaded", 9692: "Party debug 2: summon event started",
               9693: "Party debug 3: Donald & Goofy found in this area", 9694: "Party debug 4: party flag + area check passed",
               # v79 (in-game v78: all steps shown, still invisible – at the Asylum bonfire outside the demon doors)
               9695: "Party debug 5: Donald exists and is alive", 9696: "Party debug 5: Donald does NOT exist / is dead",
               9697: "Party debug 6: Donald is loaded (backread on)", 9698: "Party debug 6: Donald is NOT loaded (backread off)"}
# v84 (in-game v83: "i am able to hit donald and goofy"): team WhitePhantom (EMEVD TeamType 2) like a sign-summoned
# phantom – the host cannot hurt them, enemies target them and they target enemies. FightingAlly (12) could be hit.
PARTY_TEAM = "TeamType.WhitePhantom"
# v92 turned their character collision off for good -> in-game they fell through the floor ("appearing and
# disappearing"). v93 (user: "they still have collision but just not against Sora"): DS1 has no per-pair collision
# switch, so collision is only off while Sora pushes into one of them: the DLL raises 9982 (Donald) / 9983 (Goofy),
# the map's ghost event turns that member's collision AND gravity off (so he can't drop), and back on once the DLL
# clears the flag (Sora is through / stopped pushing). Flags 9982-9983 verified unused.
GHOST_FLAGS = (9982, 9983)   # v94 log: Sora still blocked while their collision was off -> DisableCharacterCollision
                              # only affects map collision, not character-vs-character; ghost events removed in v96
ENTITY_SUFFIX, EVENT_SUFFIX = 6950, 6950
MAPS = ["m10_00_00_00", "m10_01_00_00", "m10_02_00_00", "m11_00_00_00", "m12_00_00_00", "m12_00_00_01",
        "m12_01_00_00", "m13_00_00_00", "m13_01_00_00", "m13_02_00_00", "m14_00_00_00", "m14_01_00_00",
        "m15_00_00_00", "m15_01_00_00", "m16_00_00_00", "m17_00_00_00", "m18_00_00_00", "m18_01_00_00"]
ITEM_LONG = ("\nCall Donald and Goofy to Sora's side.\nUse again to send them away.\n\nDonald casts magic and heals "
             "Sora\nwhen he is hurt; Goofy guards with\nhis shield. Fallen friends return\nafter resting at a bonfire.")


def build_party_params(gp, get_param, copy_row, goods_template, heal_template):
    npc, ci, sp, goods, lot, pr = (get_param(gp, n) for n in ("NpcParam", "CharaInitParam", "SpEffectParam",
                                                              "EquipParamGoods", "ItemLotParam", "EquipParamProtector"))
    wp = get_param(gp, "EquipParamWeapon")
    for wid, src, model, nm in ((STAFF_WEAPON, STAFF_FROM, STAFF_MODEL, "Donald Mage's Staff"),
                                (SHIELD_WEAPON, SHIELD_FROM, SHIELD_MODEL, "Goofy Knight's Shield"),
                                (STAFF_MELEE, STAFF_MELEE_FROM, STAFF_MODEL, "Donald Mage's Staff (melee)")):
        copy_row(wp, src, wid, f"SoraSouls {nm}").WeaponModel = model
    for pid, t in TEMPLATES.items():
        n = copy_row(npc, t["npc"], pid, f"SoraSouls {NAMES[pid]}")
        n.NameID = pid
        # v80 (in-game v79: Donald "exists, alive, loaded" and a character stands within 6 m of Sora, yet nothing is
        # visible): the only NpcParam differences between the co-op summon rows (6520/6540) and the normal, visible
        # Solaire NPC (6000) are TeamType 7 vs 2 and IsChangeWanderGhost 0 vs 1 – TeamType 7 marks the summon-sign
        # phantom, drawn only once summoned through a sign. Use the normal NPC values.
        n.TeamType, n.IsChangeWanderGhost = 2, 1
        # v96 tried a thinner body (HitRadius 0.15): no effect in-game – every vanilla human NPC (c0000, 87 rows)
        # leaves HitRadius/HitHeight at 0, the human body comes from the model. v97: back to 0; blocking is handled
        # by the DLL's quick swap instead.
        th = copy_row(get_param(gp, "NpcThinkParam"), THINK[pid], pid, f"SoraSouls {NAMES[pid]}")
        th.SightDistance, th.HearingDistance = 30, 20
        # v84 (in-game v83: "they start to walk away until they are far enough to warp back"; "enemies attack them but
        # they do not attack enemies"): the AI measures every distance from its nest = the MSB spawn point of this map,
        # usually far from Sora. Beyond MaxRetreatDistance (75 m) it retreats home "in or out of battle", so they
        # walked off and ignored enemies. Max both retreat distances (uint16): they never head home, and fight wherever
        # the DLL has placed them next to Sora. TargetSysDamageRate 0 as on the co-op summons (damage does not make
        # them retarget).
        # v85 (in-game v84: still "walk away in the same direction together", no fighting): the walk is the AI going
        # back to its home point, which no retreat limit switches off. DLL v59 now keeps their home point on Sora, so
        # the limits go back to a short leash measured from Sora: chase enemies up to 20 m (30 m at most), then return.
        th.MaxRetreatDistance, th.BattleRetreatDistance, th.TargetSysDamageRate = 30, 20, 0
        # v90 (in-game v89: "they just walk instead of running when I'm further away"): SoraSouls' own logic 6950
        # (party_logic.py, added to every area by party_ai.py) runs to the home point when it is more than 4 m away
        # and no enemy is known; otherwise it hands over to the normal logic (10000).
        th.LogicID = party_logic.LOGIC_ID
        c = copy_row(ci, t["init"], pid, f"SoraSouls {NAMES[pid]}")
        # v100 KH2 looks: their own armor sets (tools/kh_party_model.py builds parts model 9560 / 9570), copies of the
        # Knight rows Sora's outfit uses (390000-393000), worn only by them
        for k, (src, field) in enumerate(((390000, "HeadArmor"), (391000, "BodyArmor"), (392000, "HandsArmor"),
                                          (393000, "LegsArmor"))):
            rid = ARMOR_BASE[pid] + 1000 * k
            a = copy_row(pr, src, rid, f"SoraSouls {NAMES[pid]} outfit {k}")
            a.EquipmentModel = MODEL[pid]
            setattr(c, field, rid)
            if k == 0 and pid in FACE_SCALE:
                # v103/v104: squash the hidden human head (Head bone local X/Z = height/depth); the KH2 heads are
                # skinned to the Neck bone (kh_party_model head_on_neck) so they are not squashed
                f = FACE_SCALE[pid]
                a.UseFaceScale = 1
                for fld in ("MaleFaceScaleX", "MaleFaceScaleZ", "MaleFaceMaxScaleX", "MaleFaceMaxScaleZ",
                            "FemaleFaceScaleX", "FemaleFaceScaleZ", "FemaleFaceMaxScaleX", "FemaleFaceMaxScaleZ"):
                    setattr(a, fld, f)
        # v101 set CharaInit bodyScaleHead -128 to hide the human head inside the KH2 head -> in-game long stretched
        # triangles everywhere (it scales bones, not only the face); Donald had inherited -50 from Witch Beatrice
        # (likely the v100 left-arm stretch). v102: neutral 0 for both; Goofy's KH2 head is enlarged instead.
        # v105: the v101 "stretching" was the placeholder-bone bug (fixed v104), not this; with the KH2 heads on the
        # Neck bone (v104) the NPC's own head size can shrink the hidden human head without touching them
        c.HeadScale = 0   # v106: -128 had no visible effect in-game v105 (face still fully visible)
        if pid == GOOFY:
            for k, v in GOOFY_GEAR.items():
                setattr(c, k, v)
        else:
            # v88 (in-game v87: Goofy swings his mace but Donald never casts): Donald runs the attack-magic bandit's
            # battle script (6804) with Witch Beatrice's loadout. Give him that bandit's own weapons, spells and
            # stats (CharaInitParam 6804: Sorcerer's Catalyst R1, dagger R2, Soul Arrow + Heavy Soul Arrow, INT 42),
            # keeping Beatrice's robe and hat for his look.
            b = ci[DONALD_CASTER]
            for k in DONALD_COPY:
                setattr(c, k, getattr(b, k))
            # v89 (user: "Donald shouldn't use a dagger, only cast or hit with the catalyst"): no second weapon.
            # v91 (in-game v90: with the slot empty the battle script's close-combat switch left him punching): the
            # catalyst goes in the second slot too. A Dark Souls catalyst has no physical swing – up close he casts.
            c.RightHandWeapon2 = c.RightHandWeapon1
            assert c.RightHandWeapon1 == STAFF_FROM, c.RightHandWeapon1
            c.RightHandWeapon1 = c.RightHandWeapon2 = STAFF_WEAPON      # v111: KH2 Mage's Staff (catalyst stats)
            c.RightHandWeapon2 = STAFF_MELEE                               # v112: staff swing up close
            c.LeftHandWeapon1 = c.LeftHandWeapon2 = -1                     # v112: no leather shield
            # v125 (playtest: "Donald's magic does way too much damage"): the bandit's INT 42 + Heavy Soul Arrow hit
            # far harder than Sora early on. Soul Arrow only, INT 16 (Soul Arrow needs 10).
            c.Intelligence = DONALD_INT
            c.SpellSlot2 = -1
    trig = copy_row(sp, 97525, TRIGGER_SP, "SoraSouls party call trigger")          # drive trigger: invisible, 1 s
    h = copy_row(sp, heal_template, CURE_SP, "SoraSouls Donald Cure")
    h.HPPointsLost, h.HPReductionPercentage = 0, -CURE_PCT
    g = copy_row(goods, 9710, GOODS, "SoraSouls Donald & Goofy")                    # Valor Form item: not consumed
    g.ReferenceID = TRIGGER_SP
    g.GoodIcon = 2096                 # v119: keep its old icon (the Valor Form row it copies now has the red crown)
    l = copy_row(lot, 100000, LOT, "SoraSouls Donald & Goofy")
    l.Item1ID, l.Item1Category, l.Item1Count, l.Item1ChancePoints, l.ItemFlag = GOODS, 0x40000000, 1, 100, -1
    return trig


def party_evs():
    calls = "".join(f"    Event_{e}()\n" for e in (EV_ITEM, EV_CURE_MSG, EV_GIVE))
    defs = f'''
@ContinueOnRest({EV_ITEM})
def Event_{EV_ITEM}():
    """SoraSouls: the Donald & Goofy item toggles the party flag {PARTY_FLAG} (map events do the summoning)."""
    MAIN.Await(PlayerHasSpecialEffect({TRIGGER_SP}))
    RemoveSpecialEffect(PLAYER, {TRIGGER_SP})
    if FlagEnabled({PARTY_FLAG}):
        DisableFlag({PARTY_FLAG})
        DisplayStatus({TEXT_LEAVE})
    else:
        EnableFlag({PARTY_FLAG})
        DisplayStatus({TEXT_JOIN})
    Wait(1.0)
    return RESTART


@ContinueOnRest({EV_CURE_MSG})
def Event_{EV_CURE_MSG}():
    """SoraSouls: a map's Donald cast Cure (flag {CURE_FLAG})."""
    OR_1.Add(FlagEnabled({CURE_FLAG}))
    OR_1.Add(FlagEnabled({FAIL_FLAG}))
    MAIN.Await(OR_1)
    if FlagEnabled({FAIL_FLAG}):
        DisableFlag({FAIL_FLAG})
        DisplayStatus({TEXT_FAIL})
    else:
        DisableFlag({CURE_FLAG})
        DisplayStatus({TEXT_CURE})
    Wait(1.0)
    return RESTART


@ContinueOnRest({EV_GIVE})
def Event_{EV_GIVE}():
    """SoraSouls: give the Donald & Goofy item once (kept if the player already has it)."""
    if ThisEventFlagEnabled():
        return
    Wait(4.0)
    if PlayerDoesNotHaveGood({GOODS}):
        AwardItemLot({LOT}, host_only=True)
'''
    return calls, defs


def party_text():
    return ({"Item_name_.fmg": {GOODS: "Donald & Goofy"}, "Item_description_.fmg": {GOODS: "Call or dismiss the party"},
             "Item_long_desc_.fmg": {GOODS: ITEM_LONG}, "NPC_name_.fmg": dict(NAMES)},
            {"Event_text_.fmg": dict(TEXTS)})


def _entities(msb):
    out = set()
    for attr in ("characters", "objects", "players", "collisions", "map_pieces", "navmeshes", "regions", "events"):
        for e in getattr(msb, attr, []) or []:
            eid = getattr(e, "entity_id", -1)
            if eid not in (-1, 0, None):
                out.add(eid)
    return out


def _pick(free_test, prefix, start, n=2):
    for k in range(start, start + 1000):
        ids = [int(f"{prefix}{k + i}") for i in range(n)]
        if all(free_test(i) for i in ids):
            return ids
    raise RuntimeError(f"no free ids for {prefix}")


def patch_map(stem, msb_src, emevd_src, out_root, report=print):
    m = MSB.from_path(msb_src)
    a, b = int(stem[1:3]), int(stem[4:6])
    ev_text = EMEVD.from_path(emevd_src).to_evs()
    ents = _entities(m)
    ids = _pick(lambda i: i not in ents and not re.search(rf"\b{i}\b", ev_text), f"{a}{b}", ENTITY_SUFFIX)
    tmpl = next(c for c in m.characters if c.model and c.model.name == "c0000")
    names = {c.name for c in m.characters}
    for eid, pid in zip(ids, (DONALD, GOOFY)):
        c = tmpl.copy()
        c.name = next(f"c0000_{9950 + k}" for k in range(100) if f"c0000_{9950 + k}" not in names)
        names.add(c.name)
        c.entity_id, c.character_id, c.player_id, c.ai_id, c.talk_id = eid, pid, pid, TEMPLATES[pid]["ai"], 0
        c.patrol_type, c.platoon_id, c.default_animation, c.damage_animation = 0, 0, -1, -1
        m.characters.append(c)
    return m, ids, ev_text


def map_events(stem, ids, ev_text):
    a, b = int(stem[1:3]), int(stem[4:6])
    game_map = (a, b, 0, 0)
    evs = _pick(lambda i: not re.search(rf"\b{i}\b", ev_text), f"11{a % 10}{b}", EVENT_SUFFIX, n=3)   # 8 digits like vanilla 11010xxx
    d, g = ids
    calls = ("    EnableFlag(9691)\n" if PARTY_DEBUG else "") + "".join(f"    Event_{e}()\n" for e in evs)
    defs = f'''

@RestartOnRest({evs[0]})
def Event_{evs[0]}():
    """SoraSouls: Donald & Goofy follow Sora in this map while party flag {PARTY_FLAG} is on."""
    EnableFlag(9692)
    DisableCharacter({d})
    DisableCharacter({g})
    EnableFlag(9693)
    AND_1.Add(FlagEnabled({PARTY_FLAG}))
    AND_1.Add(InsideMap(game_map={game_map}))
    MAIN.Await(AND_1)
    EnableFlag(9694)
    EnableCharacter({d})
    EnableCharacter({g})
    EnableBackread({d})
    EnableBackread({g})
    EnableAI({d})
    EnableAI({g})
    SetTeamType({d}, {PARTY_TEAM})
    SetTeamType({g}, {PARTY_TEAM})
    EnableCharacterCollision({d})
    EnableCharacterCollision({g})
    EnableGravity({d})
    EnableGravity({g})
    Move({d}, destination=PLAYER, destination_type=CoordEntityType.Character, copy_draw_parent=PLAYER)
    Move({g}, destination=PLAYER, destination_type=CoordEntityType.Character, copy_draw_parent=PLAYER)
    EnableFlag({DEBUG_FLAG})
    Wait(1.0)
    if CharacterAlive({d}):
        EnableFlag(9695)
    else:
        EnableFlag(9696)
    if CharacterBackreadEnabled({d}):
        EnableFlag(9697)
    else:
        EnableFlag(9698)
    # v110 (in-game v109: after quitting with the party on and loading the save, they don't appear until the item is
    # used twice; log: "Donald is NOT loaded (backread off)" right after loading – the enable during the load screen
    # doesn't stick). Not loaded -> start over (hide, enable, move), exactly what re-using the item did by hand.
    if not CharacterBackreadEnabled({d}):
        Wait(1.0)
        return RESTART
    if not CharacterBackreadEnabled({g}):
        Wait(1.0)
        return RESTART
    OR_2.Add(FlagDisabled({PARTY_FLAG}))
    OR_2.Add(OutsideMap(game_map={game_map}))
    MAIN.Await(OR_2)
    return RESTART


@RestartOnRest({evs[1]})
def Event_{evs[1]}():
    """SoraSouls: Donald casts Cure (1 in 3 on himself) on Sora below {int(CURE_BELOW * 100)} % HP (then waits {CURE_WAIT:.0f} s)."""
    AND_1.Add(FlagEnabled({PARTY_FLAG}))
    AND_1.Add(InsideMap(game_map={game_map}))
    AND_1.Add(CharacterAlive({d}))
    AND_1.Add(HealthRatioLessThan(PLAYER, {CURE_BELOW}))
    MAIN.Await(AND_1)
    DisableFlagRange(({FAIL_ROLL[0]}, {FAIL_ROLL[1]}))
    EnableRandomFlagInRange(({FAIL_ROLL[0]}, {FAIL_ROLL[1]}))
    if FlagEnabled({FAIL_ROLL[0]}):
        EnableFlag({FAIL_FLAG})
    else:
        AddSpecialEffect(PLAYER, {CURE_SP})
        EnableFlag({CURE_FLAG})
    Wait({CURE_WAIT})
    return RESTART


@RestartOnRest({evs[2]})
def Event_{evs[2]}():
    """SoraSouls: the DLL moved a lagging member's home point (flags {REPLAN_FLAGS}) -> re-plan so he heads there now."""
    OR_1.Add(FlagEnabled({REPLAN_FLAGS[0]}))
    OR_1.Add(FlagEnabled({REPLAN_FLAGS[1]}))
    AND_1.Add(OR_1)
    AND_1.Add(InsideMap(game_map={game_map}))
    MAIN.Await(AND_1)
    if FlagEnabled({REPLAN_FLAGS[0]}):
        DisableFlag({REPLAN_FLAGS[0]})
        ReplanAI({d})
    if FlagEnabled({REPLAN_FLAGS[1]}):
        DisableFlag({REPLAN_FLAGS[1]})
        ReplanAI({g})
    Wait(0.5)
    return RESTART
'''
    if not PARTY_DEBUG:
        defs = strip_debug(defs)
    return calls, defs, evs


def strip_debug(defs):
    """v115 (user: remove the debug messages): drop the 'Party debug' flag lines (9690-9698) from the summon event,
    including the if/else blocks that only set them. The loaded-check retry (v110) stays."""
    out, lines, i = [], defs.split("\n"), 0
    dbg = lambda l: l.strip() in {f"EnableFlag({f})" for f in range(9690, 9699)}
    while i < len(lines):
        l = lines[i]
        if l.strip().startswith(("if CharacterAlive(", "if CharacterBackreadEnabled(")) and i + 3 < len(lines) \
                and dbg(lines[i + 1]) and lines[i + 2].strip() == "else:" and dbg(lines[i + 3]):
            i += 4; continue
        if dbg(l):
            i += 1; continue
        out.append(l); i += 1
    return "\n".join(out)


def merge_events(src_path, snippet_calls, snippet_defs, out_path):
    """Adds our events to a map EMEVD WITHOUT decompiling the vanilla ones (EVS round-trips are not byte-faithful
    for every map): the snippet is compiled on its own, its events are added and its constructor's RunEvent
    instructions appended to vanilla event 0. Every vanilla event is checked byte-identical afterwards."""
    e = EMEVD.from_path(src_path)
    head = ("from soulstruct.darksouls1r.events import *\nfrom soulstruct.darksouls1r.events.instructions import *\n"
            "from soulstruct.darksouls1r.game_types import *\n\n\n@ContinueOnRest(0)\ndef Constructor():\n"
            '    """Event 0"""\n')
    snip = EMEVD.from_evs_string(head + snippet_calls + snippet_defs)
    before = {k: _event_bytes(e, k) for k in e.events}
    for k, ev in snip.events.items():
        if k == 0:
            continue
        if k in e.events:
            raise RuntimeError(f"event {k} already exists")
        e.events[k] = ev
    e.events[0].instructions[0:0] = list(snip.events[0].instructions)   # v78: at the start (before any vanilla skip/end)
    e.write(out_path)
    chk = EMEVD.from_path(out_path)
    for k, b in before.items():
        if k != 0 and _event_bytes(chk, k) != b:
            raise RuntimeError(f"vanilla event {k} changed")
    n0 = len(EMEVD.from_path(src_path).events[0].instructions)
    assert len(chk.events[0].instructions) == n0 + len(snip.events[0].instructions)
    return out_path


def _event_bytes(emevd, k):
    ev = emevd.events[k]
    return repr([repr(i) for i in ev.instructions]) + repr(ev.on_rest_behavior)


def patch_all(game, mod):
    msb_dir, ev_dir = os.path.join(game, "map", "MapStudio"), os.path.join(game, "event")
    os.makedirs(os.path.join(mod, "map", "MapStudio"), exist_ok=True)
    os.makedirs(os.path.join(mod, "event"), exist_ok=True)
    done = {}
    for stem in MAPS:
        ev_stem = stem[:-2] + "00"
        msb_src, ev_src = os.path.join(msb_dir, stem + ".msb"), os.path.join(ev_dir, ev_stem + ".emevd.dcx")
        m, ids, ev_text = patch_map(stem, msb_src, ev_src, mod)
        if ev_stem in done:                           # m12_00_00_01 (DSR Darkroot) shares m12_00_00_00's script
            ids_prev = done[ev_stem]
            for c, eid in zip(list(m.characters)[-2:], ids_prev):
                c.entity_id = eid
            ids = ids_prev
        else:
            calls, defs, evs = map_events(stem, ids, ev_text)
            merge_events(ev_src, calls, defs, os.path.join(mod, "event", ev_stem + ".emevd.dcx"))
            done[ev_stem] = ids
            print(f"{ev_stem}: events {evs}")
        out = os.path.join(mod, "map", "MapStudio", stem + ".msb")
        m.write(out)
        chk = MSB.from_path(out)
        mine = [c for c in chk.characters if c.character_id in (DONALD, GOOFY)]
        assert [c.entity_id for c in mine] == list(ids), [c.entity_id for c in mine]
        print(f"{stem}: Donald {ids[0]}, Goofy {ids[1]} ({len(list(chk.characters))} characters)")


if __name__ == "__main__":
    import sys
    patch_all(sys.argv[1], sys.argv[2])
