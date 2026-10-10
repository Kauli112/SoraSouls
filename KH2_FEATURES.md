# KH2 → Dark Souls Remastered feature catalog

Every KH2 (Final Mix) system considered, mapped to the DSR mechanism that can carry it, with a difficulty tier.
Tiers describe *how* it is built, not how important it is:

| Tier | Built with | Risk |
|---|---|---|
| **A** | params + event scripts + text only (what step 4 already uses) | low – same pipeline as the ability framework |
| **B** | A + new spells/bullets/effects reusing DSR animations and SFX | medium – param-heavy, testable in-game |
| **C** | B + animation-timeline (TAE) edits, new HKX animations, or new models on enemy/NPC skeletons | high – needs new tooling (DSAnimStudio-class work) |
| **D** | engine code via a ModEngine2 DLL, or new UI | very high – reverse-engineering, crash risk |

Verified facts this catalog relies on (from DSR's own files, 2026-10-04): SpEffectParam fields (HP/attack/defense
multipliers, low-HP triggers, stamina regen, soul gain, poise, on-attack effects; animation speed via `grabityRate` – verified in-game 2026-10-04 (soulstruct name `AnimationSpeedMultiplier`); gravity, IgnoreGravity and fall-damage changes do **not** work on the player); event
instructions `AddSpecialEffect`, `AwardItemLot`, `ForceAnimation`, `DisplayStatus`, `DisplayDialog`,
`PlaceSummonSign`, `HealthRatio`; params `Magic`, `Bullet`, `ShopLineupParam`, `MoveParam`, `EquipParamGoods`.

---

## 1. Support abilities (KH2 "Support" list)

| KH2 ability | DSR implementation | Tier |
|---|---|---|
| HP Boost, Damage Control, Combo Boost, Jackpot | **done (step 4)** | A |
| Quick Run (real) | **done (v19):** passive animation speed ×1.10 (speeds every animation, not only running) | A |
| Defender | defense ×1.5 at low HP (Blue Tearstone clone, separate from Damage Control) | A |
| Lucky Lucky | item-discovery effect (Covetous Gold Serpent clone, SpecialState 66) | A |
| Experience Boost | souls ×2 while HP below 25 % | A |
| Fire / Blizzard / Thunder Boost | fire / magic / lightning attack ×1.2 – rings | A |
| Draw | larger soul/item pickup radius – no param for it | D |
| MP Rage / MP Haste / Hastera / Hastega | only meaningful once an MP system exists (see §4) | A after §4 |
| Second Chance | can't react at 0 HP (death has already triggered); instead a brief "Immortal" SpEffect when `HealthRatio(PLAYER)` < 5 %, once per rest – needs in-game verification | B |
| Once More | full combo can't be interrupted → poise boost while attacking (SpEffect on attack) | B |
| Leaf Bracer | poise boost while casting Cure | B |
| Berserk Charge | attack ×1.25 + infinite poise while low HP | A/B |
| Item Boost | stronger healing items (only our own KH items, §5) | A |
| Light & Darkness (FM) | Anti-Form avoidance – only after Drive Forms | C |
| Combo Plus / Air Combo Plus / Finishing Plus / Negative Combo | DSR combos are fixed animation chains → TAE edits | C |
| Scan (enemy HP bars) | no hook for this | D |
| Aerial Recovery | DSR has no air-control state | D |

## 2. Action abilities / combo finishers

| KH2 | DSR implementation | Tier |
|---|---|---|
| Guard | map to DSR guard/parry (already exists – just text/flavor) | A |
| Counterguard / Retaliating Slash | parry → riposte already exists; KH timing would need TAE | C |
| Upper/Horizontal Slash, Explosion, Finishing Leap, Magnet Burst, Aerial finishers | new attack animations or bullets spawned from TAE events | C |
| Guard Break, Slapshot, Dodge Slash, Flash Step, Slide Dash, Vicinity Break | as above | C |

## 3. Magic (Fire, Blizzard, Thunder, Cure, Magnet, Reflect) – planned step 5

Built as custom spells (Magic + Bullet + SpEffect params), cast with the Keyblade acting as a catalyst or via a
spell tool. -ra / -ga upgrades unlock by boss flags (same framework as abilities).

| Spell | Closest DSR base | Tier |
|---|---|---|
| Fire / Fira / Firaga | Fireball / Fire Orb / Great Fireball (pyromancy) re-tuned: faster, lower damage, recolour | B |
| Blizzard / Blizzara / Blizzaga | Soul Arrow family with ice VFX, or Crystal Soul Spear | B |
| Thunder / Thundara / Thundaga | lightning bullet spawned *above* targets (AoE in front of Sora) | B |
| Cure / Cura / Curaga | Heal / Great Heal Excerpt / Great Heal | B |
| Reflect / Reflera / Reflega | short Magic-Barrier-style guard + damage burst on expiry | B/C |
| Magnet / Magnera / Magnega | gravity pull doesn't exist in DSR; nearest: AoE hold (Wrath-of-the-Gods-style knock-in) | C |

## 4. MP system

DSR has no MP bar – spells use per-rest "uses". Options:
- **Uses = MP** (Tier A): each spell gets KH-like uses (Fire 8, Cure 3…); MP Haste etc. become +1 use rings.
- **Stamina as MP** (Tier B): spells cost stamina instead of uses.
- **Real MP bar** (Tier D): new HUD + resource.

## 5. Items, shops, progression

| KH2 | DSR implementation | Tier |
|---|---|---|
| Potion / Hi-Potion / Mega-Potion, Ether, Elixir, Megalixir | new consumables (EquipParamGoods) with healing SpEffects + KH names/descriptions | A |
| Power Up / Defense Up / Magic Up / AP Up | consumables that set event flags → permanent stat SpEffects | A |
| Moogle shop | add KH items to a merchant's ShopLineupParam (e.g. Undead Merchant) | A |
| Synthesis | materials as drops + "upgrade" via a shop or blacksmith reinforcement | B |
| Keyblades (Oathkeeper, Oblivion, Ultima, Fenrir…) | same pipeline as the Kingdom Key, replacing other straight-sword models; stats via EquipParamWeapon | A/B |
| Keychains / Mickey token | fixed (non-physics) charm on the Keyblade mesh | B |
| Level-up / bonus abilities | already covered by boss-flag unlocks | A |
| Unlock messages ("Sora learned HP Boost!") | `DisplayStatus` + event text | A |

## 6. Drive Forms

**Status:** Valor, Wisdom, Master, Final + Anti built as quick-bar items refilled on rest (`tools/drive_forms.py`, ROADMAP 5b), incl. animation speed ×1.10–1.25 (v19).

| Form | DSR implementation | Tier |
|---|---|---|
| Drive gauge | resource: Humanity counter, or event-counted kills | B |
| Valor | timed SpEffect: attack speed (animation speed), attack ×1.3, no magic; colour-tinted VFX aura | B |
| Wisdom | timed: magic ×1.5, faster cast | B |
| Master / Final | timed buffs; floating Keyblades / glide need models + DLL | B (buffs) / D (visuals, glide) |
| Limit (FM) | grants access to Limits (§7) while active | C |
| Anti Form | random chance on activation: big attack, no healing, can't revert | B |
| Outfit colour change | swap armor model on activation – events can't change equipment; needs DLL or SpEffect material params | D |

## 7. Limits (Sora's FM limits) and summons

| KH2 | DSR implementation | Tier |
|---|---|---|
| Sonic Blade, Ragnarok, Ars Arcanum, Strike Raid | "limit" item/spell that `ForceAnimation`s existing DSR multi-hit animations + spawns bullets (e.g. Ragnarok's rising burst) | C |
| Trinity Limit | needs Donald/Goofy | D |
| Summons: Chicken Little, Genie, Stitch, Peter Pan | summon-sign NPC phantoms using KH2 models rigged to an NPC skeleton + AI params | C/D |
| Donald & Goofy party | as above, permanent companions – AI/behaviour work | D |

## 8. World, enemies, presentation

| KH2 | DSR implementation | Tier |
|---|---|---|
| Heartless / Nobody enemy reskins (Shadow, Soldier, Dusk…) | KH2 models rigged onto matching DSR enemy skeletons (Hollow → Soldier etc.) | C |
| Organization XIII bosses | model on an existing boss skeleton + new movesets | D |
| Reaction Commands | context button prompts via ObjAct/talk events on bosses | C |
| KH2 music | replace DSR FSB sound banks (personal use only) | B |
| Save points instead of bonfires | bonfire object model swap | C |
| KH HUD (HP/MP/Drive gauge) | menu/HUD layout edits | D |
| High Jump, Dodge Roll, Aerial Dodge, Glide | movement code / animations (step 6) – SpEffect gravity/fall fields verified **not** to work on the player (v18 test), so jump/glide need TAE root-motion edits | C–D |

---

## Recommended order
1. **Ability Pack 2** (Tier A, all testable now): Defender, Lucky Lucky, Experience Boost, Berserk Charge,
   element-boost rings, unlock messages, KH items (Potion → Megalixir, Ether, Power/Defense Up), Moogle shop.
2. **Magic** (Tier B): Fire / Blizzard / Thunder / Cure with -ra/-ga upgrades; decide the MP model first.
3. **Drive Forms as timed buffs** (Tier B): Valor + Wisdom + Anti Form chance, gauge via Humanity.
4. **More Keyblades** (Tier A/B, existing pipeline).
5. **Limits** (Tier C) – first Tier C tooling investment (animation timelines).
6. Enemy reskins, summons, movement (Tier C/D) once the tooling exists.

Legal reminder: KH2 names/assets stay local; a public release ships only code/params/scripts plus a converter.
