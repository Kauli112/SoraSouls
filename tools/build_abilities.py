"""SoraSouls – KH2 ability framework, Pack 1 + Pack 2 (hybrid: always-on passives + ability rings + KH items).

Builds four mod files from VANILLA game files (run outside Blender with the soulstruct library):
  mod/param/GameParam/GameParam.parambnd.dcx   SpEffects, ability rings, KH items, item lots, Moogle shop
  mod/event/common.emevd.dcx                    unlock events + "Sora learned ...!" messages
  mod/msg/ENGLISH/item.msgbnd.dcx               ring / item names and descriptions
  mod/msg/ENGLISH/menu.msgbnd.dcx               unlock message text

Boss-defeat flags were read from the vanilla map event scripts (EnableFlag right before KillBoss, boss named via
its health-bar NPC name):
  Asylum Demon 16 | Taurus Demon 11010901 | Bell Gargoyles 3 | Capra Demon 11010902 | Gaping Dragon 2 |
  Great Grey Wolf Sif 5 | Moonlight Butterfly 11200900 | Chaos Witch Quelaag 9 | Iron Golem 11
Moogle shop = Undead Merchant (Male), shop range 1100-1199 (vanilla rows 1100-1133).

ID plan (all verified free in vanilla):
  SpEffect 97500-97515 | accessories 160-167 | goods 9700-9702 + spells 4900-4932 | item lots 9800000+ (spaced by 10) | shop rows 1170-1175
  events 9750-9758 | flags: 9759 + 9790-9793 ring-lot pickup, 9770-9781 message shown, 9785-9787 shop stock
  event text 10975000+

Usage: python build_abilities.py <DSR game dir or staged copy> <mod dir>
"""
import copy, os, sys
# v127 ladder test: Quick Run speeds up EVERY animation (also ladder climbing) - SORASOULS_QUICK_RUN overrides it
QUICK_RUN_SPEED = float(os.environ.get("SORASOULS_QUICK_RUN", "1.10"))
from soulstruct.containers import Binder
from soulstruct.darksouls1r.params.gameparambnd import GameParamBND
from soulstruct.darksouls1r.events import EMEVD
from soulstruct.darksouls1r.text.fmg import FMG
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drive_forms  # Drive Forms (separate module)
import movement  # Step 6 movement (test kit first)
import hybrid_keyblade  # animation research experiment 1
import movement_levels  # High Jump / Glide unlock + level flags (read by dll/sora_glide.dll)
import sora_class  # starting stats, light outfit, Kingdom Key INT scaling (v44)
import drive_outfits  # Drive Form outfits (v120)
import keyblades  # Keyblade collection: six boss-drop Keyblades (v63)
import mp_drive  # KH-style MP Charge + Drive gauge messages (v68; logic in the DLL)
import party  # Donald & Goofy party summon (v76; map files: tools/party.py)

RING_CATEGORY = 0x20000000
HUD_MSG_FLAGS = {}   # v72: filled by build_events, used by build_text for dll/hud_data.h
LORE = "\nAn ability Sora learned on his journeys.\n\n"

# kind "passive": always on once the boss flag is set (re-applied by event every few seconds)
# kind "ring":    accessory awarded once when the boss flag is set
# kind "shop_ring": accessory sold once by the Moogle (Undead Merchant)
ABILITIES = [
    # ---- Pack 1 ------------------------------------------------------------------------------
    dict(key="HP Boost", kind="passive", boss_flag=16, event=9750, speffect=97500, template=2340,
         set=dict(MaxHPMultiplier=1.10)),
    dict(key="Damage Control", kind="passive", boss_flag=11010901, event=9751, speffect=97501, template=2290,
         set=dict(MaxHPPercentageForEffect=25.0)),
    dict(key="Combo Boost", kind="passive", boss_flag=3, event=9752, speffect=97502, template=2010,
         set=dict(MaxHPPercentageForEffect=-1.0, PhysicalAttackPowerMultiplier=1.10, MagicAttackPowerMultiplier=1.0,
                  FireAttackPowerMultiplier=1.0, LightningAttackPowerMultiplier=1.0, SpecialState=0, StatusIcon=-1)),
    # Quick Run v2: real speed – grabityRate (soulstruct "AnimationSpeedMultiplier") IS animation speed, verified
    # in-game 2026-10-04 (1.5 = faster, 0.5/0.25 = slower). Speeds up every animation (run, roll, attacks, casts).
    dict(key="Quick Run", kind="passive", boss_flag=11010902, event=9753, speffect=97503, template=2013,
         set=dict(SpecialState=0, StatusIcon=-1, AnimationSpeedMultiplier=QUICK_RUN_SPEED)),
    dict(key="Jackpot", kind="ring", boss_flag=2, event=9754, speffect=97504, template=2101, set=dict(),
         ring_id=160, ring_template=122, item_lot=9800000, lot_flag=9759,
         summary="Increases souls absorbed from each kill",
         long=LORE + "Increases the number of souls absorbed\nfrom each defeated foe.\n\nLearned by felling the Gaping Dragon."),
    # ---- Pack 2: boss rings ----------------------------------------------------------------------
    dict(key="Defender", kind="ring", boss_flag=11200900, event=9755, speffect=97505, template=2290,
         set=dict(MaxHPPercentageForEffect=50.0, PhysicalDefenseMultiplier=1.25, MagicDefenseMultiplier=1.25,
                  FireDefenseMultiplier=1.25, LightningDefenseMultiplier=1.25, SpecialState=0),
         ring_id=161, ring_template=147, item_lot=9800010, lot_flag=9790,
         summary="Raises defense when HP is below half",
         long=LORE + "Raises all defense while HP is\nbelow half.\n\nLearned by felling the Moonlight Butterfly."),
    dict(key="Lucky Lucky", kind="ring", boss_flag=5, event=9756, speffect=97506, template=2100, set=dict(),
         ring_id=162, ring_template=121, item_lot=9800020, lot_flag=9791,
         summary="Increases item discovery",
         long=LORE + "Foes drop items more often.\n\nDoes not stack with the\nCovetous Gold Serpent Ring.\n\nLearned by felling Great Grey Wolf Sif."),
    dict(key="Berserk Charge", kind="ring", boss_flag=9, event=9757, speffect=97507, template=2010,
         set=dict(MaxHPPercentageForEffect=25.0, PhysicalAttackPowerMultiplier=1.25, MagicAttackPowerMultiplier=1.0,
                  FireAttackPowerMultiplier=1.0, LightningAttackPowerMultiplier=1.0, PoiseAddition=30,
                  SpecialState=0),
         ring_id=163, ring_template=101, item_lot=9800030, lot_flag=9792,
         summary="Raises attack and poise when HP is low",
         long=LORE + "Strikes harder and holds firm while\nHP is critically low.\n\nLearned by felling Chaos Witch Quelaag."),
    dict(key="Experience Boost", kind="ring", boss_flag=11, event=9758, speffect=97508, template=2101,
         set=dict(SoulsFromKillsMultiplier=2.0, MaxHPPercentageForEffect=25.0, SpecialState=0),
         ring_id=164, ring_template=122, item_lot=9800040, lot_flag=9793,
         summary="Doubles souls from kills when HP is low",
         long=LORE + "Doubles the souls absorbed from\nfoes while HP is critically low.\n\nLearned by felling the Iron Golem."),
    # ---- Pack 2: Moogle shop rings ---------------------------------------------------------------
    dict(key="Fire Boost", kind="shop_ring", speffect=97509, template=2101,
         set=dict(SoulsFromKillsMultiplier=1.0, FireAttackPowerMultiplier=1.2, SpecialState=0, StatusIcon=-1),
         ring_id=165, ring_template=105, shop_row=1170, price=3000, stock_flag=9785,
         summary="Boosts fire damage",
         long=LORE + "Boosts the power of fire attacks.\n\nSold by a wandering moogle... or\nsomeone who looks like one."),
    dict(key="Blizzard Boost", kind="shop_ring", speffect=97510, template=2101,
         set=dict(SoulsFromKillsMultiplier=1.0, MagicAttackPowerMultiplier=1.2, SpecialState=0, StatusIcon=-1),
         ring_id=166, ring_template=107, shop_row=1171, price=3000, stock_flag=9786,
         summary="Boosts magic damage",
         long=LORE + "Boosts the power of magic attacks.\n\nIn Lordran, the chill of Blizzard\nanswers to sorcery."),
    dict(key="Thunder Boost", kind="shop_ring", speffect=97511, template=2101,
         set=dict(SoulsFromKillsMultiplier=1.0, LightningAttackPowerMultiplier=1.2, SpecialState=0, StatusIcon=-1),
         ring_id=167, ring_template=106, shop_row=1172, price=3000, stock_flag=9787,
         summary="Boosts lightning damage",
         long=LORE + "Boosts the power of lightning attacks."),
]

# KH healing items: goods copied from Elizabeth's Mushroom (230), heal SpEffect copied from Estus (3020)
ITEMS = [
    dict(key="Potion", goods=9700, speffect=97512, heal_pct=30.0, shop_row=1173, price=300, max_hold=8,
         summary="Restores some HP",
         long="\nA common restorative from distant\nworlds. Restores 30% of max HP."),
    dict(key="Hi-Potion", goods=9701, speffect=97513, heal_pct=60.0, shop_row=1174, price=900, max_hold=4,
         summary="Restores a good amount of HP",
         long="\nA potent restorative from distant\nworlds. Restores 60% of max HP."),
    dict(key="Elixir", goods=9702, speffect=97514, heal_pct=100.0, shop_row=1175, price=4000, max_hold=2,
         summary="Fully restores HP",
         long="\nA rare and precious restorative.\nFully restores HP."),
]
GOODS_TEMPLATE, HEAL_TEMPLATE, ITEM_ICON = 230, 3020, 2005
# v115 healing balance (user choice "Both, lightly": potions + Estus): potions were unlimited (hold 99) -> carry limit
# (max_hold above; extra bought ones go to the Bottomless Box as for any full DSR stack). Estus: the charge count per
# bonfire kindle level is not in the params; the filled-flask goods' MaxHoldQuantity (vanilla 20) caps it – 15 means
# 5/10/15 as before for the first three kindle levels and 15 instead of 20 at the last (in-game test decides whether
# the game honours the cap).
ESTUS_FILLED = range(201, 216, 2)
ESTUS_MAX = 15
SHOP_TEMPLATE_ROW = 1105  # any vanilla Undead Merchant row; only ids/type/price/stock are changed
PASSIVE_REAPPLY_SECONDS = 5.0
MSG_FLAG_BASE, MSG_TEXT_BASE = 9770, 10975000

for i, a in enumerate(ABILITIES):
    a["msg_flag"] = MSG_FLAG_BASE + i
    a["msg_text"] = MSG_TEXT_BASE + i
    a.setdefault("name", a["key"])

# ---- Step 5: KH2 magic (casts per rest) ------------------------------------------------------------
# Spells are sorceries with no stat requirements, cast from "Kingdom Key (Magic)": a catalyst (copy of Sorcerer's
# Catalyst) that reuses the Kingdom Key model (WeaponModel 204). Its weapon dummy 100 sits at the Keyblade tip, so
# spells leave from the tip. It lives in the right hand's 2nd slot: weapon-swap between melee and magic.
# (v1 used pyromancies + a left-hand Pyromancy Flame; changed on request: "spells should be used from the keyblade".)
# mp_cost = KH2 MP cost, kept for a possible future real-MP-bar backend (not used by casts-per-rest).
# unlock: "start" | boss flag | tuple of flags where ANY one suffices. Ornstein & Smough: only the super form of
# whichever dies last runs KillBoss, so exactly one of 11510902 (Ornstein) / 11510903 (Smough) gets set.
ONS = (11510902, 11510903)
KEY_MAGIC, KEY_MAGIC_TEMPLATE, KEY_MODEL = 1309000, 1300000, 204   # new catalyst weapon / Sorcerer's Catalyst
SORC_TEMPLATE, SORC_SELF_TEMPLATE, SPELL_GOODS_TEMPLATE = 3000, 3530, 3000  # Soul Arrow (anim 0), Repair (anim 2)
PYRO_TEMPLATE = PYRO_SELF_TEMPLATE = None  # kept names below map to sorcery templates
KEY_MAGIC_NAME = "Kingdom Key (Magic)"
# Seamless casting v1 (user: invisible off-hand focus, no shield): DS1 catalysts in the LEFT hand cast with L1 while
# the right hand keeps R1/R2 melee. The focus is a Sorcerer's Catalyst copy on model WP_A_1309 – the catalyst mesh
# collapsed onto the grip by tools/make_invisible_focus.py (dummies kept; dummy 100 = spell origin).
FOCUS, FOCUS_MODEL, FOCUS_NAME = 1310000, 1309, "Keyblade Focus"  # clean base id: the hundreds digit of a DS1 weapon id is its upgrade path (1309100 would read as "Crystal" 1309000)
FOCUS_EVENT, FOCUS_LOT = 9907, 9800350   # gives the focus once to existing saves
GOODS_LOT_TEMPLATE, GOODS_CATEGORY = 100000, 0x40000000
# v124 (in-game 2026-10-10: "the thunder spell has no sound"): the lightning crack is not in the bullet or its
# effect – vanilla plays it from the Lightning Spear throw animation (a00_6519: sound type 5 at the release). With
# Soul Arrow's animation (type 0) Thunder only had the quiet wind-up. Thunder family now uses Lightning Spear's
# animation type 19 (a00_6319 / 6519), like the vanilla spells whose bullets it fires.
THUNDER_ANIM = 19
SPELLS = [
    # id, name, template, overrides(ReferenceID [bullet or SpEffect], casts, icon), unlock, mp
    dict(id=3900, old_id=4900, name="Fire", tmpl=SORC_TEMPLATE, ref=6000, casts=16, icon=3020, unlock="start", mp=12,
         desc="Fires a ball of flame."),
    dict(id=3901, old_id=4901, name="Fira", tmpl=SORC_TEMPLATE, ref=6100, casts=12, icon=3021, unlock=11010902, mp=12,
         desc="Fires a larger ball of flame that bursts on impact."),
    dict(id=3902, old_id=4902, name="Firaga", tmpl=SORC_TEMPLATE, ref=6200, casts=8, icon=3022, unlock=ONS, mp=12,
         desc="Fires a great ball of flame with a wide blast."),
    dict(id=3910, old_id=4910, name="Blizzard", tmpl=SORC_TEMPLATE, ref=3000, casts=16, icon=3000, unlock=16, mp=12,
         desc="Fires a shard of chilling magic."),
    dict(id=3911, old_id=4911, name="Blizzara", tmpl=SORC_TEMPLATE, ref=3010, casts=12, icon=3001, unlock=11200900, mp=12,
         desc="Fires a heavier shard of chilling magic."),
    dict(id=3912, old_id=4912, name="Blizzaga", tmpl=SORC_TEMPLATE, ref=3090, casts=6, icon=3059, unlock=ONS, mp=12,
         desc="Fires a piercing spear of crystal ice."),
    dict(id=3920, old_id=4920, name="Thunder", tmpl=SORC_TEMPLATE, ref=9000, casts=12, icon=3048, unlock=3, mp=12, anim=THUNDER_ANIM,
         desc="Hurls a bolt of lightning."),
    dict(id=3921, old_id=4921, name="Thundara", tmpl=SORC_TEMPLATE, ref=9100, casts=8, icon=3049, unlock=9, mp=12, anim=THUNDER_ANIM,
         desc="Hurls a great bolt of lightning."),
    dict(id=3922, old_id=4922, name="Thundaga", tmpl=SORC_TEMPLATE, ref=9200, casts=5, icon=3050, unlock=ONS, mp=12, anim=THUNDER_ANIM,
         desc="Hurls a blinding spear of sunlight."),
    dict(id=3930, old_id=4930, name="Cure", tmpl=SORC_SELF_TEMPLATE, ref=1400, casts=3, icon=3037, unlock=11010901, mp="all",
         desc="Restores HP."),
    dict(id=3931, old_id=4931, name="Cura", tmpl=SORC_SELF_TEMPLATE, ref=1410, casts=3, icon=3039, unlock=5, mp="all",
         desc="Restores a large amount of HP."),
    dict(id=3932, old_id=4932, name="Curaga", tmpl=SORC_SELF_TEMPLATE, ref=1420, casts=3, icon=3038, unlock=ONS, mp="all",
         desc="Greatly restores HP."),
]
ATTUNEMENT_SPEFFECT, ATTUNEMENT_TEMPLATE, EXTRA_SLOTS = 97515, 2040, 3
# Damage tuning (v11, after in-game test: "Blizzard = sword damage, Fire even stronger"). Projectile spells get
# their own copy of the vanilla bullet chain + AtkParam_Pc rows, with attack power scaled by the family factor, so
# vanilla spells/enemies are untouched. Vanilla bases: Fireball 200/245/300 fire, Soul Arrow 110/150 & Crystal
# Soul Spear 360 magic, Lightning 270-370 lightning (6-bullet chains).
DAMAGE_SCALE = {"Fire": 0.5, "Blizzard": 0.8, "Thunder": 0.45}   # v11-v114 (superseded by SPELL_POWER)
# v115 (user: "fine-tune spell damage to feel natural", choice "Match DSR progress"): each spell's first hit is set to
# the vanilla sorcery tier of the boss that unlocks it (rest of the chain keeps its vanilla ratios):
#   start / Asylum Demon      110  (Soul Arrow)
#   Capra / Bell Gargoyles    150  (Great Soul Arrow)
#   Moonlight Butterfly       170  (Heavy Soul Arrow 160 .. Great Heavy Soul Arrow 200)
#   Quelaag                   200  (Great Heavy Soul Arrow)
#   Ornstein & Smough         300  (Soul Spear 260 .. Crystal Soul Spear 360)
# Before: Fire 100 Fira 122 Firaga 150, Blizzard 88 Blizzara 120 Blizzaga 288, Thunder 121 Thundara 135 Thundaga 166.
SPELL_POWER = {"Fire": 110, "Fira": 150, "Firaga": 300, "Blizzard": 110, "Blizzara": 170, "Blizzaga": 320,
               "Thunder": 150, "Thundara": 200, "Thundaga": 300}
OWN_BULLET_BASE, OWN_ATK_BASE = 31000, 9700000  # + 10 * spell index + depth; Magic.ReferenceID is int16 on disk -> bullet ids < 32768 (31000-31999 free in vanilla)
ATK_POWER_FIELDS = ("PhysicalAttackPower", "MagicAttackPower", "FireAttackPower", "LightningAttackPower")
# ItemLotParam rules learned the hard way (in-game test 2026-10-04):
#  * items inside ONE lot row are a weighted RANDOM pick (vanilla lot 2: nothing 375 vs item 20)
#  * consecutive lot ids are awarded TOGETHER (vanilla 6300 ring + 6301 humanity)
# So: one item per row, every lot followed by a gap, and multi-item rewards are deliberate chains.
# v7: spells moved from 4900+ (pyromancy id range – the game silently refused them in Attune Magic although
# params matched Soul Arrow) to 3900+ (sorcery range). Events/lots/lot flags renumbered so saves that already
# ran the old unlocks receive the new spell items.
MAGIC_EVENT_BASE, MAGIC_LOT_BASE, MAGIC_LOT_FLAG_BASE = 9860, 9800400, 9880
LOT_SPACING = 10
MAGIC_MSG_FLAG_BASE, MAGIC_MSG_TEXT_BASE = 9840, 10975100
# start kit v4: two separate lots, two AwardItemLot calls (no reliance on chaining). Event 9795 is new, so saves
# that ran v1-v3 (random-pick lot / chain) receive it again – v3 delivered the Keyblade but no usable spell.
START_EVENT, ATTUNE_EVENT, START_LOT, START_LOT_FLAG = 9797, 9799, 9800300, 9815
OLD_START_EVENT = 9795  # set on saves that already received the Kingdom Key (Magic)
START_SPELL_LOT, START_SPELL_LOT_FLAG = 9800320, 9818  # v7 Fire (3900); 9800310/9816 = obsolete 4900 Fire
# v9 safety net: on a save that finished the start event but does not own the start spell (seen in-game after v7),
# hand it over once from a fresh lot. Waits for the start event so a new save never gets two.
RESTORE_EVENT, RESTORE_LOT, RESTORE_LOT_FLAG = 9798, 9800330, 9819
# The bonfire talk script (t*1000.esd) only lists "Attune Magic" when flag 719 is on; vanilla Event_719 sets it
# only for vanilla spell goods, so our spells need their own trigger.
ATTUNE_MENU_EVENT, ATTUNE_MENU_FLAG = 9796, 719
# The attune list itself is ShopLineupParam rows 10000-10099 (OpenMagicEquip in the bonfire script): one row per
# spell, ItemType 4 = Magic row id, shown only while the player owns RequiredGood. Vanilla uses 10000-10076.
ATTUNE_LIST_TEMPLATE, ATTUNE_LIST_BASE, ATTUNE_LIST_LAST = 10000, 10077, 10099
# A lineup row's "RequiredGood" (mtrlId) is an EquipMtrlSetParam row id, NOT a goods id: vanilla mtrl row 3000 =
# "1x goods 3000". Without a mtrl row the spell never appears in Attune Magic (v1-v7 bug). Source: soulsmodding
# wiki "How To Create New Spells In DS1" + vanilla params.
MTRL_TEMPLATE = 3000
SPELL_GOODS_SORT_BASE = 3900  # unique menu sort ids (v1-v7 duplicated the template's 3001)
for i, s in enumerate(SPELLS):
    s.update(event=MAGIC_EVENT_BASE + i, lot=MAGIC_LOT_BASE + LOT_SPACING * i, lot_flag=MAGIC_LOT_FLAG_BASE + i,
             msg_flag=MAGIC_MSG_FLAG_BASE + i, msg_text=MAGIC_MSG_TEXT_BASE + i)
KNIGHT_INIT_ROWS = (2001, 3001)


def get_param(gp, name):
    # soulstruct 2.6 keys params by bare name; older versions used the binder path
    return next(v for k, v in gp.params.items() if k == name or k.endswith("\\" + name))


def copy_row(param, src_id, dst_id, name):
    if dst_id in param.rows:
        raise ValueError(f"{dst_id} already exists")
    row = copy.deepcopy(param.rows[src_id])
    row.Name = name
    param.rows[dst_id] = row
    param.rows = dict(sorted(param.rows.items()))
    return row


def build_params(game, mod):
    src = os.path.join(game, "param/GameParam/GameParam.parambnd.dcx")
    gp = GameParamBND.from_path(src)
    binder = Binder.from_path(src)
    sp, acc, lot, goods, shop = (get_param(gp, n) for n in
                                 ("SpEffectParam", "EquipParamAccessory", "ItemLotParam", "EquipParamGoods",
                                  "ShopLineupParam"))
    for a in ABILITIES:
        row = copy_row(sp, a["template"], a["speffect"], f"SoraSouls {a['key']}")
        for f, v in a["set"].items():
            setattr(row, f, v)
        if a["kind"] in ("ring", "shop_ring"):
            ring = copy_row(acc, a["ring_template"], a["ring_id"], f"SoraSouls {a['key']}")
            ring.SpecialEffect = a["speffect"]
        if a["kind"] == "ring":
            l = copy_row(lot, 1310140, a["item_lot"], f"SoraSouls {a['key']}")  # vanilla single-ring lot
            l.Item1ID, l.Item1Category, l.Item1Count, l.Item1ChancePoints = a["ring_id"], RING_CATEGORY, 1, 100
            l.ItemFlag = a["lot_flag"]
        if a["kind"] == "shop_ring":
            s = copy_row(shop, SHOP_TEMPLATE_ROW, a["shop_row"], f"SoraSouls {a['key']}")
            s.ItemID, s.ItemType, s.SoulCost = a["ring_id"], 2, a["price"]
            s.InitialQuantity, s.QuantityFlag = 1, a["stock_flag"]
    for it in ITEMS:
        h = copy_row(sp, HEAL_TEMPLATE, it["speffect"], f"SoraSouls {it['key']}")
        h.HPPointsLost, h.HPReductionPercentage = 0, -it["heal_pct"]
        g = copy_row(goods, GOODS_TEMPLATE, it["goods"], f"SoraSouls {it['key']}")
        g.ReferenceType, g.ReferenceID, g.GoodIcon = 2, it["speffect"], ITEM_ICON
        g.MaxHoldQuantity = it["max_hold"]
        s = copy_row(shop, SHOP_TEMPLATE_ROW, it["shop_row"], f"SoraSouls {it['key']}")
        s.ItemID, s.ItemType, s.SoulCost, s.InitialQuantity, s.QuantityFlag = it["goods"], 3, it["price"], -1, -1
    for gid in ESTUS_FILLED:
        assert goods.rows[gid].MaxHoldQuantity == 20, gid
        goods.rows[gid].MaxHoldQuantity = ESTUS_MAX
    # ---- magic ----
    mg, ci, mtrl = get_param(gp, "Magic"), get_param(gp, "CharaInitParam"), get_param(gp, "EquipMtrlSetParam")
    att = copy_row(sp, ATTUNEMENT_TEMPLATE, ATTUNEMENT_SPEFFECT, "SoraSouls Magic attunement")
    att.AttunementSlotCountChange, att.SpecialState, att.StatusIcon = EXTRA_SLOTS, 0, -1
    for s in SPELLS:
        m = copy_row(mg, s["tmpl"], s["id"], f"SoraSouls {s['name']}")
        m.ReferenceID, m.BaseCastCount, m.SpellIcon, m.SpellCategory = s["ref"], s["casts"], s["icon"], 0
        m.RequiredIntelligence = m.RequiredFaith = 0
        if "anim" in s:
            m.AnimationType = s["anim"]
        gd = copy_row(goods, SPELL_GOODS_TEMPLATE, s["id"], f"SoraSouls {s['name']}")
        gd.GoodIcon = s["icon"]
        gd.Spell = s["id"]  # links the spell item to its Magic row (v1-v3 bug: still pointed at the template's spell)
        old = copy_row(goods, SPELL_GOODS_TEMPLATE, s["old_id"], f"SoraSouls obsolete {s['name']}")
        # leftover v1-v6 item: a plain key item, NOT a spell – v7/v8 pointed it at the new spell (Spell = new id),
        # and owning "Fire (old)" x2 kept the real Fire out of Attune Magic while Blizzard (no old copy) showed.
        old.GoodIcon, old.Spell, old.GoodType = s["icon"], -1, 1
        a_id = ATTUNE_LIST_BASE + SPELLS.index(s)
        if a_id > ATTUNE_LIST_LAST:
            raise RuntimeError("attune list range 10000-10099 is full")
        al = copy_row(shop, ATTUNE_LIST_TEMPLATE, a_id, f"SoraSouls attune {s['name']}")
        mt = copy_row(mtrl, MTRL_TEMPLATE, s["id"], f"SoraSouls attune {s['name']}")
        mt.UpgradeGood, mt.UpgradeQuantity = s["id"], 1
        gd.SortIndex = SPELL_GOODS_SORT_BASE + SPELLS.index(s)
        al.ItemID, al.RequiredGood = s["id"], s["id"]  # ItemType 4 / ShopMenuType 2 / cost 0 kept from template
        if s["unlock"] != "start":
            l = copy_row(lot, GOODS_LOT_TEMPLATE, s["lot"], f"SoraSouls {s['name']}")
            l.Item1ID, l.Item1Category, l.Item1Count, l.Item1ChancePoints, l.ItemFlag = \
                s["id"], GOODS_CATEGORY, 1, 100, s["lot_flag"]
    bullets, atks = get_param(gp, "Bullet"), get_param(gp, "AtkParam_Pc")
    for i, s in enumerate(SPELLS):
        if s["name"] not in SPELL_POWER:
            continue
        first = s["ref"]                                   # first bullet in the chain that deals damage
        while bullets.rows[first].BulletAttack in (-1, 0):
            first = bullets.rows[first].BulletOnHit
        a0 = atks.rows[bullets.rows[first].BulletAttack]
        scale = SPELL_POWER[s["name"]] / max(getattr(a0, f) for f in ATK_POWER_FIELDS)
        src, prev, depth = s["ref"], None, 0
        while src not in (-1, 0):
            nb = OWN_BULLET_BASE + 10 * i + depth
            b = copy_row(bullets, src, nb, f"SoraSouls {s['name']} {depth}")
            if b.BulletAttack not in (-1, 0):
                na = OWN_ATK_BASE + 10 * i + depth
                at = copy_row(atks, b.BulletAttack, na, f"SoraSouls {s['name']} {depth}")
                for f in ATK_POWER_FIELDS:
                    setattr(at, f, int(round(getattr(at, f) * scale)))
                b.BulletAttack = na
            if prev is None:
                mg.rows[s["id"]].ReferenceID = nb
            else:
                prev.BulletOnHit = nb
            prev, src, depth = b, b.BulletOnHit, depth + 1
            if depth > 9:
                raise RuntimeError(f"{s['name']}: bullet chain longer than 10")
    wp = get_param(gp, "EquipParamWeapon")
    kw = copy_row(wp, KEY_MAGIC_TEMPLATE, KEY_MAGIC, f"SoraSouls {KEY_MAGIC_NAME}")
    kw.WeaponModel, kw.RequiredIntelligence, kw.RequiredStrength = KEY_MODEL, 0, 0
    fw = copy_row(wp, KEY_MAGIC_TEMPLATE, FOCUS, f"SoraSouls {FOCUS_NAME}")
    fw.WeaponModel, fw.RequiredIntelligence, fw.RequiredStrength, fw.Weight = FOCUS_MODEL, 0, 0, 0.0
    lf = copy_row(lot, GOODS_LOT_TEMPLATE, FOCUS_LOT, f"SoraSouls {FOCUS_NAME}")
    lf.Item1ID, lf.Item1Category, lf.Item1Count, lf.Item1ChancePoints, lf.ItemFlag = FOCUS, 0, 1, 100, -1
    start = next(s for s in SPELLS if s["unlock"] == "start")
    l = copy_row(lot, GOODS_LOT_TEMPLATE, START_LOT, "SoraSouls start kit: Kingdom Key (Magic)")
    l.Item1ID, l.Item1Category, l.Item1Count, l.Item1ChancePoints = KEY_MAGIC, 0, 1, 100
    l.ItemFlag = START_LOT_FLAG
    l2 = copy_row(lot, GOODS_LOT_TEMPLATE, START_SPELL_LOT, f"SoraSouls start kit: {start['name']}")
    l2.Item1ID, l2.Item1Category, l2.Item1Count, l2.Item1ChancePoints = start["id"], GOODS_CATEGORY, 1, 100
    l2.ItemFlag = START_SPELL_LOT_FLAG
    for row_id in KNIGHT_INIT_ROWS:  # new Knights: cast-capable Kingdom Key right, empty left (v30), Fire attuned
        ci.rows[row_id].RightHandWeapon1, ci.rows[row_id].RightHandWeapon2 = 1311000, -1  # cast-capable Kingdom Key (v30)
        ci.rows[row_id].LeftHandWeapon1, ci.rows[row_id].LeftHandWeapon2 = -1, -1  # empty: L1 = guard, L1+R1 = cast
        ci.rows[row_id].SpellSlot1 = start["id"]
    ours = {a["item_lot"] for a in ABILITIES if "item_lot" in a} | {s["lot"] for s in SPELLS if s["unlock"] != "start"}
    l3 = copy_row(lot, GOODS_LOT_TEMPLATE, RESTORE_LOT, f"SoraSouls restore: {start['name']}")
    l3.Item1ID, l3.Item1Category, l3.Item1Count, l3.Item1ChancePoints = start["id"], GOODS_CATEGORY, 1, 100
    l3.ItemFlag = RESTORE_LOT_FLAG
    for lid in ours | {START_LOT, START_SPELL_LOT, RESTORE_LOT, FOCUS_LOT}:
        row = lot.rows[lid]
        extra = [n for n in range(2, 9) if getattr(row, f"Item{n}ID") not in (0, -1)]
        if extra or lid + 1 in lot.rows:
            raise RuntimeError(f"lot {lid}: extra random items {extra} or accidental chain to {lid + 1}")
    drive_forms.build_drive_params(gp, get_param, copy_row)
    movement.build_movement_params(gp, get_param, copy_row)
    hybrid_keyblade.build_hybrid_params(gp, get_param, copy_row)
    sora_class.build_class_params(gp, get_param)  # after hybrid_keyblade, which creates the Kingdom Key row
    # v116: Kingdom Key rows (melee, magic, hybrid B) get the Kingdom Key menu icon (keyblade_icons.py)
    for wid in (hybrid_keyblade.HYBRID_A, hybrid_keyblade.HYBRID_B, KEY_MAGIC):
        get_param(gp, "EquipParamWeapon").rows[wid].WeaponIcon = keyblades.keyblade_icons.ICON_ID["KingdomKey"]
    keyblades.build_keyblade_params(gp, get_param, copy_row)
    keyblades.build_keyblade_upgrades(gp, get_param, copy_row)   # v118: +0..+10 with Titanite
    drive_outfits.build_params(gp, get_param, copy_row)           # v120: Drive Form outfit armor rows
    mp_drive.build_mp_drive_params(gp, get_param, copy_row)  # Drive hit sensor (v71)
    mp_drive.build_drive_items(gp, get_param, copy_row)      # v122: Drive Recovery / High Drive Recovery
    party.build_party_params(gp, get_param, copy_row, GOODS_TEMPLATE, HEAL_TEMPLATE)  # after drive_forms (item 9710)
    changed = ("SpEffectParam", "EquipParamAccessory", "ItemLotParam", "EquipParamGoods", "ShopLineupParam",
               "Magic", "CharaInitParam", "EquipParamWeapon", "EquipMtrlSetParam", "Bullet",
               "AtkParam_Pc", "EquipParamProtector", "NpcParam", "NpcThinkParam",   # v81: NpcParam (party) was never written back
               "ReinforceParamWeapon")                                           # v118: Keyblade upgrade rows
    for e in binder.entries:
        stem = e.path.split("\\")[-1][:-len(".param")]
        if stem in changed:
            e.data = get_param(gp, stem).to_bytes()
    out = os.path.join(mod, "param/GameParam/GameParam.parambnd.dcx")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    binder.write(out)
    return out


EVENT_TEMPLATES = {
    "passive": '''
@ContinueOnRest({event})
def Event_{event}():
    """SoraSouls: {key} – always on after boss flag {boss_flag}."""
    MAIN.Await(FlagEnabled({boss_flag}))
    if FlagDisabled({msg_flag}):
        DisplayStatus({msg_text})
        EnableFlag({msg_flag})
    AddSpecialEffect(PLAYER, {speffect})
    Wait({wait})
    return RESTART
''',
    "ring": '''
@ContinueOnRest({event})
def Event_{event}():
    """SoraSouls: award the {key} ability ring once boss flag {boss_flag} is set."""
    if ThisEventFlagEnabled():
        return
    MAIN.Await(FlagEnabled({boss_flag}))
    AwardItemLot({item_lot}, host_only=True)
    DisplayStatus({msg_text})
    EnableFlag({msg_flag})
''',
}


MAGIC_EVENTS = {
    "start": '''
@ContinueOnRest({START_EVENT})
def Event_{START_EVENT}():
    """SoraSouls: start kit – {name}, once per save (v125: the old Kingdom Key (Magic) catalyst is no longer given;
    the Knight starts with the Kingdom Key itself)."""
    if ThisEventFlagEnabled():
        return
    AwardItemLot({START_LOT_2}, host_only=True)
    DisplayStatus({msg_text})
    EnableFlag({msg_flag})
''',
    "attune": '''
@ContinueOnRest({ATTUNE_EVENT})
def Event_{ATTUNE_EVENT}():
    """SoraSouls: +{EXTRA_SLOTS} attunement slots, always on."""
    AddSpecialEffect(PLAYER, {ATTUNEMENT_SPEFFECT})
    Wait({wait})
    return RESTART
''',
    "restore": '''
@ContinueOnRest({RESTORE_EVENT})
def Event_{RESTORE_EVENT}():
    """SoraSouls: give {name} again if the start kit ran but the player does not own it."""
    if ThisEventFlagEnabled():
        return
    MAIN.Await(FlagEnabled({START_EVENT}))
    Wait(2.0)
    if PlayerDoesNotHaveGood({id}, including_storage=True):
        AwardItemLot({RESTORE_LOT}, host_only=True)
        DisplayStatus({msg_text})
''',
    "focus": '''
@ContinueOnRest({FOCUS_EVENT})
def Event_{FOCUS_EVENT}():
    """SoraSouls: give the Keyblade Focus (left-hand casting) once, unless the player already has it."""
    if ThisEventFlagEnabled():
        return
    Wait(2.0)
    if PlayerDoesNotHaveWeapon({FOCUS}, including_storage=True):
        AwardItemLot({FOCUS_LOT}, host_only=True)
''',
    "attune_menu": '''
@ContinueOnRest({ATTUNE_MENU_EVENT})
def Event_{ATTUNE_MENU_EVENT}():
    """SoraSouls: show "Attune Magic" at bonfires (flag {ATTUNE_MENU_FLAG}) once the player owns a Sora spell."""
    if FlagEnabled({ATTUNE_MENU_FLAG}):
        return
{has_block}
    MAIN.Await(OR_1)
    EnableFlag({ATTUNE_MENU_FLAG})
''',
    "spell": '''
@ContinueOnRest({event})
def Event_{event}():
    """SoraSouls: Sora learns {name} ({condition_doc})."""
    if ThisEventFlagEnabled():
        return
{await_block}
    AwardItemLot({lot}, host_only=True)
    DisplayStatus({msg_text})
    EnableFlag({msg_flag})
''',
}


def magic_evs():
    # v125 (playtest: "he starts with many items and double of some items"): the Keyblade Focus gift (v1 left-hand
    # casting experiment) is no longer started; its event stays defined so the event file layout is unchanged
    out, calls = [], [f"    Event_{START_EVENT}()\n", f"    Event_{ATTUNE_EVENT}()\n",
                      f"    Event_{ATTUNE_MENU_EVENT}()\n", f"    Event_{RESTORE_EVENT}()\n"]
    start = next(s for s in SPELLS if s["unlock"] == "start")
    consts = dict(START_EVENT=START_EVENT, ATTUNE_EVENT=ATTUNE_EVENT, START_LOT=START_LOT,
                  START_LOT_2=START_SPELL_LOT, OLD_START_EVENT=OLD_START_EVENT,
                  EXTRA_SLOTS=EXTRA_SLOTS, ATTUNEMENT_SPEFFECT=ATTUNEMENT_SPEFFECT, wait=PASSIVE_REAPPLY_SECONDS)
    out.append(MAGIC_EVENTS["start"].format(**consts, **start))
    out.append(MAGIC_EVENTS["attune"].format(**consts))
    out.append(MAGIC_EVENTS["focus"].format(FOCUS_EVENT=FOCUS_EVENT, FOCUS=FOCUS, FOCUS_LOT=FOCUS_LOT))
    out.append(MAGIC_EVENTS["restore"].format(RESTORE_EVENT=RESTORE_EVENT, RESTORE_LOT=RESTORE_LOT,
                                              START_EVENT=START_EVENT, **start))
    has = "\n".join(f"    OR_1.Add(PlayerHasGood({sp['id']}))" for sp in SPELLS)
    out.append(MAGIC_EVENTS["attune_menu"].format(ATTUNE_MENU_EVENT=ATTUNE_MENU_EVENT,
                                                  ATTUNE_MENU_FLAG=ATTUNE_MENU_FLAG, has_block=has))
    for s in SPELLS:
        if s["unlock"] == "start":
            continue
        flags = s["unlock"] if isinstance(s["unlock"], tuple) else (s["unlock"],)
        if len(flags) == 1:
            block = f"    MAIN.Await(FlagEnabled({flags[0]}))"
        else:
            block = "\n".join(f"    OR_1.Add(FlagEnabled({f}))" for f in flags) + "\n    MAIN.Await(OR_1)"
        out.append(MAGIC_EVENTS["spell"].format(await_block=block, condition_doc=" or ".join(map(str, flags)), **s))
        calls.append(f"    Event_{s['event']}()\n")
    return "".join(calls), "".join(out)


def build_events(game, mod):
    src = os.path.join(game, "event/common.emevd.dcx")
    vanilla = EMEVD.from_path(src)
    evs = vanilla.to_evs()
    evented = [a for a in ABILITIES if a["kind"] in EVENT_TEMPLATES]
    anchor = "    Event_761()\n"
    if anchor not in evs:
        raise RuntimeError("constructor anchor not found in common.evs")
    m_calls, m_defs = magic_evs()
    evs = evs.replace(anchor, anchor + "".join(f"    Event_{a['event']}()\n" for a in evented) + m_calls, 1)
    for a in evented:
        evs += EVENT_TEMPLATES[a["kind"]].format(wait=PASSIVE_REAPPLY_SECONDS, **a)
    evs += m_defs
    d_calls, d_defs = drive_forms.drive_evs()
    mv_calls, mv_defs = movement.movement_evs()
    hy_calls, hy_defs = hybrid_keyblade.hybrid_evs()
    lv_calls, lv_defs = movement_levels.levels_evs()
    kb_calls, kb_defs = keyblades.keyblade_evs()
    pa_calls, pa_defs = party.party_evs()
    md_calls, md_defs = mp_drive.mp_drive_evs([s["lot"] for s in SPELLS if s["unlock"] != "start"])
    di_calls, di_defs = mp_drive.drive_item_evs()            # v122: Drive Recovery items
    rx_calls, rx_defs = drive_outfits.roxas_evs()             # v126: Roxas look while Hollow
    di_calls, di_defs = di_calls + rx_calls, di_defs + rx_defs
    md_calls, md_defs = md_calls + di_calls, md_defs + di_defs
    evs = evs.replace(anchor, anchor + d_calls + mv_calls + hy_calls + lv_calls + kb_calls + md_calls + pa_calls, 1)
    evs += d_defs + mv_defs + hy_defs + lv_defs + kb_defs + md_defs + pa_defs
    global HUD_MSG_FLAGS
    evs, HUD_MSG_FLAGS = mp_drive.hud_messages(evs)   # v72: our pop-ups -> HUD flags (pop-ups block input)
    out = os.path.join(mod, "event/common.emevd.dcx")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    emevd = EMEVD.from_evs_string(evs)
    emevd.dcx_type = vanilla.dcx_type
    emevd.write(out)
    with open(out + ".evs.py", "w", encoding="utf-8") as f:  # readable copy; ModEngine ignores it
        f.write(evs)
    return out


def edit_fmgs(src, out, edits):
    """edits: {fmg file name: {text id: string}} – applied to every copy of that FMG in the binder."""
    b = Binder.from_path(src)
    for e in b.entries:
        new = edits.get(e.path.split("\\")[-1])
        if not new:
            continue
        fmg = FMG.from_bytes(e.data)
        fmg.entries.update(new)
        fmg.sort()
        e.data = fmg.to_bytes()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    b.write(out)
    return out


def build_text(game, mod):
    rings = [a for a in ABILITIES if "ring_id" in a]
    item_edits = {
        "Accessory_name_.fmg": {a["ring_id"]: a["name"] for a in rings},
        "Accessory_description_.fmg": {a["ring_id"]: a["summary"] for a in rings},
        "Accessory_long_desc_.fmg": {a["ring_id"]: a["long"] for a in rings},
        "Item_name_.fmg": {**{it["goods"]: it["key"] for it in ITEMS}, **{it["goods"]: it["name"] for it in mp_drive.DRIVE_ITEMS}},
        "Item_description_.fmg": {**{it["goods"]: it["summary"] for it in ITEMS}, **{it["goods"]: it["summary"] for it in mp_drive.DRIVE_ITEMS}},
        "Item_long_desc_.fmg": {**{it["goods"]: it["long"] for it in ITEMS}, **{it["goods"]: it["long"] for it in mp_drive.DRIVE_ITEMS}},
    }
    spell_long = {s["id"]: f"\nKH magic. {s['desc']}\n\nAttune at a bonfire, hold the\n{FOCUS_NAME} in the left hand and\ncast with L1.\nKH2 MP cost: {s['mp']}." + mp_drive.MAGIC_NOTE for s in SPELLS}
    item_edits["Weapon_name_.fmg"] = {KEY_MAGIC: KEY_MAGIC_NAME, FOCUS: FOCUS_NAME}
    item_edits["Weapon_description_.fmg"] = {KEY_MAGIC: "Casts Sora's magic", FOCUS: "Off-hand magic focus"}
    item_edits["Weapon_long_desc_.fmg"] = {FOCUS: "\nThe Keyblade's magic, gathered in\nSora's free hand.\n\nEquip in the LEFT hand: the Keyblade\nkeeps attacking with R1/R2 while L1\ncasts attuned magic. Invisible.\nRequires no intelligence.",
                                           KEY_MAGIC: "\nThe Kingdom Key, held ready for magic.\n\nSwitch to it to cast Fire, Blizzard,\nThunder and Cure. Requires no\nintelligence."}
    for fmg_name, field in (("Magic_name_.fmg", "name"), ("Item_name_.fmg", "name"),
                            ("Magic_description_.fmg", "desc"), ("Item_description_.fmg", "desc")):
        item_edits.setdefault(fmg_name, {}).update({s["id"]: s[field] for s in SPELLS})
    for fmg_name in ("Magic_long_desc_.fmg", "Item_long_desc_.fmg"):
        item_edits.setdefault(fmg_name, {}).update(spell_long)
    item_edits["Item_name_.fmg"].update({s["old_id"]: f"{s['name']} (old)" for s in SPELLS})
    item_edits["Item_description_.fmg"].update({s["old_id"]: "Obsolete test copy" for s in SPELLS})
    item_edits["Item_long_desc_.fmg"].update({s["old_id"]: "\nLeftover from an earlier SoraSouls test\nbuild. Does nothing." for s in SPELLS})
    menu_edits = {"Event_text_.fmg": {a["msg_text"]: f"Sora learned {a['name']}!"
                                      for a in ABILITIES if a["kind"] in EVENT_TEMPLATES}}
    menu_edits["Event_text_.fmg"].update({s["msg_text"]: f"Sora learned {s['name']}!" for s in SPELLS})
    d_item, d_menu = drive_forms.drive_text()
    for fmg_name, entries in d_item.items():
        item_edits.setdefault(fmg_name, {}).update(entries)
    menu_edits["Event_text_.fmg"].update(d_menu)
    menu_edits["Event_text_.fmg"].update(movement_levels.levels_text())
    for fmg_name, entries in hybrid_keyblade.hybrid_text().items():
        item_edits.setdefault(fmg_name, {}).update(entries)
    pa_item, pa_menu = party.party_text()
    for fmg_name, entries in pa_item.items():
        item_edits.setdefault(fmg_name, {}).update(entries)
    md_item, md_menu = mp_drive.mp_drive_text()
    for fmg_name, entries in md_item.items():
        item_edits.setdefault(fmg_name, {}).update(entries)
    for fmg_name, entries in keyblades.keyblade_text().items():
        item_edits.setdefault(fmg_name, {}).update(entries)
    for fmg_name, entries in sora_class.class_text().items():
        item_edits.setdefault(fmg_name, {}).update(entries)
    for fmg_name, entries in movement.movement_text().items():
        item_edits.setdefault(fmg_name, {}).update(entries)
    menu_edits["Event_text_.fmg"].update(md_menu["Event_text_.fmg"])   # after drive_text (overrides its EMPTY_TEXT)
    menu_edits["Event_text_.fmg"].update(pa_menu["Event_text_.fmg"])
    abil = [("Abilities", a["key"], a.get("stock_flag", a.get("msg_flag", -1)), -1) for a in ABILITIES]
    abil += [("Magic", s["name"], s["msg_flag"], s["lot_flag"]) for s in SPELLS]
    abil += [("Movement", "High Jump", 0, -1)] + [("Movement", msg.replace("Sora learned ", "").rstrip("!"), ev, -1)
                                                  for ev, _, _, msg in movement_levels.LEVELS]
    abil += [("Drive Forms", f["name"], f["unlock_event"], -1) for f in drive_forms.FORMS]
    abil += [("Keyblades", "Kingdom Key", 0, -1)] + [("Keyblades", k["name"], k["event"], -1) for k in keyblades.KEYBLADES]
    dll_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dll")
    if os.path.isdir(dll_dir):                     # developer checkout only; the tester package ships the built DLL
        hdr = mp_drive.write_hud_header(os.path.join(dll_dir, "hud_data.h"),
                                        HUD_MSG_FLAGS, menu_edits["Event_text_.fmg"], abil,
                                        extra_msgs=({party.DEBUG_FLAG: party.DEBUG_TEXT, **party.DEBUG_STEPS} if party.PARTY_DEBUG else {}))
        print("wrote", os.path.normpath(hdr))
    return [edit_fmgs(os.path.join(game, "msg/ENGLISH/item.msgbnd.dcx"),
                      os.path.join(mod, "msg/ENGLISH/item.msgbnd.dcx"), item_edits),
            edit_fmgs(os.path.join(game, "msg/ENGLISH/menu.msgbnd.dcx"),
                      os.path.join(mod, "msg/ENGLISH/menu.msgbnd.dcx"), menu_edits)]


if __name__ == "__main__":
    game, mod = sys.argv[1], sys.argv[2]
    for fn in (build_params, build_events, build_text):
        print("wrote", fn(game, mod))
