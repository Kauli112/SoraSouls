# Architecture

## Decision: native port into DSR (no runtime bridge)
```
KH2 install ──OpenKH (mdlx)──► conversion pipeline ──► FLVER/TPF/params ──► DSR + ModEngine2
                                (scripted, local)                           (mod folder, game files untouched)
```
**Rejected:** a runtime bridge running KH2 and DSR together – two engines with no shared world, physics or collision; fragile, slow, not releasable.
**Rejected:** a full reimplementation in another engine (that's a new game, not a mod).

## Character pipeline
1. Read Sora (`P_EX100.mdlx`) and the Kingdom Key (`W_EX010.mdlx`) from the OpenKH-extracted data.
2. Rescale (KH2 units → metres, ≈ ×0.011) and convert the coordinate convention (both are Y-up; handedness still to be confirmed).
3. **Re-weight:** collapse Sora's 228 bones onto DSR's player skeleton (c0000) using `bone_map` (Sora bone index → DSR bone name). Bones with no DSR equivalent (hair, coat tails, face) merge into their nearest mapped ancestor, so those parts move rigidly.
4. Re-pose the mesh from KH2's T-pose to the DSR bind pose.
5. Write FLVER + TPF as player part file(s) and register them via EquipParamProtector.

## Ability system (planned)
- Unlocks: EMEVD events check boss-defeated flags → award item/SpEffect.
- Passive abilities: SpEffectParam.
- Magic: Magic/Bullet/Behavior params + SFX.
- Movement abilities (High Jump, Glide, …): param/TAE edits first; DLL via ModEngine2 only if params can't do it.

## Facts established
| Fact | Source |
|---|---|
| DSR player skeleton = 80 bones (~57 deforming + dummies) | `chr\c0000.chrbnd.dcx` → c0000.flver, read with soulstruct |
| Sora = 228 bones, 4 sub-meshes, 1 texture pack; bones unnamed (index only) | `P_EX100.mdlx` header parse |
| Sora bind pose = T-pose, ~160 units tall, Y-up, max hierarchy depth 24, 59 leaf bones | bone table parse |
| Kingdom Key = 12 bones, 2 sub-meshes | `W_EX010.mdlx` header parse |

| DSR bind pose = T-pose, faces −Z, L_ bones on +X, units = metres | c0000.flver armature-space transforms |
| Sora FBX export: 4 meshes (2001/2168/98/74 verts), 228 bones `Bone0000`–`Bone0227`, 3 PNGs, Y-up, cm, faces +Z | FBX parse |
| Every Sora vertex has exactly 1 bone influence (rigid skinning) → bone merge cannot exceed DSR's 4-weight limit | FBX parse |
| Best-fit scale Sora→DSR = 0.01053 (Sora ≈ 1.83 m to hair tip); joint mismatches up to ~11 cm (Sora: higher hips, shorter arms, bigger head) | least-squares over 11 joints |

## Open questions
- Whether the Sora→DSR transform (mirror in Z) leaves Sora visually mirrored – check asymmetric details in the preview.
- Joint-mismatch fix: per-bone mesh offsets (stretches Sora toward DSR proportions) vs. keeping his proportions and accepting joint-pivot offsets. Decide after seeing deformation.
- Per-mesh bone limit for DSR FLVER meshes.
- Best mdlx → mesh route: OpenKH Kh2MdlxEditor/KhModels export (Windows GUI) vs. a custom reader.

## Soulstruct for Blender 3.2.1 – workarounds used in `tools/blender_swap_sora.py`
- Texture conversion uses `multiprocessing.Pool`; in background Blender on Windows the workers re-run the main script and cannot import `bl_ext.*` → endless hang. Fix: script body in `main()` behind `__name__` guard, `__main__.__file__` hidden, and `batch_texconv_to_dds` replaced with a serial version.
- `DDSTexture.tpf_platform` returns the EnumProperty string instead of `TPFPlatform` → TPF write crash (`'str' object has no attribute 'get_byte_order'`). Patched at runtime. Worth reporting upstream.
- New images default to DDS format `SAME` (needs an existing texture) → set `DXT5` (diffuse, keeps alpha) / `DXT1` (flat specular, normal) explicitly.
- Exporter writes TPF format byte 1 for all textures; vanilla uses 0 for DXT1 → fixed in `tools/finalize_parts.py`.

## DSR ItemLotParam rules (learned in-game 2026-10-04)
- Items inside one lot row are a **weighted random pick**, not a bundle (vanilla lot 2: nothing 375 vs item 20). The v1/v2 magic start kit put Keyblade + Fire in one row and gave only one of them.
- **Consecutive lot ids are awarded together** (vanilla 6300 ring + 6301 Humanity). Lots 97540–97544 / 97551–97561 would have handed out every later reward at the first unlock (caught before it was hit).
- Rule in `build_abilities.py`: one item per row, ids spaced by 10 (9800000+), multi-item rewards as separate lots with separate `AwardItemLot` calls (start kit: 9800300 Kingdom Key (Magic) + 9800310 Fire, event 9795); the build fails if any lot has extra items or an accidental chain.
- Spell goods (EquipParamGoods, GoodType 5) must have `Spell` = their Magic row id, or Attune Magic never offers them (v1–v3 bug: still pointed at the template's 3000).
- The bonfire talk scripts (`script/talk/*.talkesdbnd`, e.g. t181000/t100200) list "Attune Magic" (menu 5, text 15000130) only when **flag 719** is on. Vanilla `Event_719` sets it only for vanilla spell goods, so `Event_9796` sets 719 once the player owns any Sora spell (4900–4932).
- The attune list is `OpenMagicEquip(10000, 10099)` = **ShopLineupParam rows 10000–10099** (ItemType 4, ItemID = Magic id). Vanilla fills 10000–10076; Sora's spells use 10077–10088.
- A lineup row's `RequiredGood` (mtrlId) is an **EquipMtrlSetParam row id**, not a goods id (vanilla mtrl 3000 = "1× goods 3000"). Without that row the spell never appears in Attune Magic – the cause of the v1–v7 failures (confirmed in-game 2026-10-04: Blizzard appeared after v8; source: soulsmodding wiki "How To Create New Spells In DS1"). Spell goods also get unique SortIndex values (3900+).
- v7 moved spells from 4900+ to 3900+ while chasing this; the move alone did not fix it (in-game test 2026-10-04). Old 49xx goods are now plain key items (GoodType 1, Spell −1): v8 left them as spells pointing at the new ids. Fire was missing from Attune Magic after v8 because the player never received Fire 3900 (v7 start event 9797 did not deliver it; cause not yet known). v10 adds `Event_9798`, which gives Fire once from lot 9800330 if the start event has run but the player does not own it.

## Spell damage (v11)
- Projectile spells use their **own** bullet chains (Bullet 31000–31099, `31000 + 10·spell index + depth`) and AtkParam_Pc rows (9700000+), copied from the vanilla ones with attack power × `DAMAGE_SCALE` in `build_abilities.py` (Fire 0.5, Blizzard 0.8, Thunder 0.45). Vanilla bullets/attacks stay untouched (verified by diff).
- `Magic.ReferenceID` is int16 on disk, so bullet ids must stay below 32768 (an id of 97000 failed to write).
- Cure/Cura/Curaga are SpEffect spells (vanilla Heal family) and are not scaled.

## Drive Forms (v12) – `tools/drive_forms.py`
- Form items are goods (template Humanity 500) → timed SpEffect. Template SpEffect is Power Within (1090): its HP drain is **HPReductionPercentage 1 % every 1 s (UpdateInterval)** plus category 10001 – all cleared for the forms.
- Auras come from `SpEffect.SpecialState` → SpEffectVfxParam row of the same index (vanilla examples: 48 Red Tearstone, 71 Dusk Crown, 29/40 Magic Barriers, 205 Artorias self-buff).
- `@RestartOnRest` events **do fire from common.emevd** (in-game v12).
- v12 refilled by removing leftovers and re-awarding a consumable stack – a stack that reaches 0 is cleared from the quick bar, so the player had to re-equip after every rest. v13: permanent non-consumed goods (`ConsumedOnUse 0`); charges are a 4-bit event value per form (`IncrementEventValue` on use, `ClearEventValue` on rest, `EventValue >= charges` → cancel + "Not enough Drive").
- Aura notes: state 71 (Dusk Crown) renders nothing on the player; 29 and 40 (Magic Barriers) look identical (white circles); 48 shows a red glow.
- Anti roll: `EnableRandomFlagInRange(9940–9959)`, Anti if any of 9940–9942 (15 %).
- v14: event values (IncrementEventValue / EventValue ≥ n) were replaced by one plain flag per charge, and form items now apply a 1 s invisible trigger SpEffect (97525–97528) that the handler removes and answers – so every use is counted, even while a form is active.
- Aura results on the player: 48 red glow ✔, 41 blue ✔, 40 white circles ✔, 29 = same as 40, 71 nothing, 153 weapon only, 205 nothing (Artorias's effect isn't loaded for the player). v14 tries 178 (Master) and 22 (Anti).

## Seamless casting v1 (v17)
- DS1 catalysts cast from the **left hand with L1**, so an invisible off-hand catalyst gives melee (R1/R2) + magic (L1) with no weapon swap.
- Invisible model = vanilla WP_A_0910 copied to the unused id **WP_A_1309** with every vertex position set to 0 (mesh, materials and dummies kept – dummy 100 is the spell origin ~53 cm out from the hand). `tools/make_invisible_focus.py`.
- Weapon ids: the hundreds digit is the upgrade path (+100 crystal … +900 chaos), so new weapons need a clean base id (focus = 1310000, not 1309100).

## Animation research (v20) – `tools/tae32.py`
- Player TAEs (`chr/c0000.anibnd.dcx` → `taeNew/x64/aNN.tae`) are **version 0x1000B with 32-bit offsets**. Layout: header 0x50 tae id / 0x54 anim count / 0x58 anim table; anim table = (int32 id, int32 offset); anim struct 0x1C = event count, event headers, group count, groups, times count, times, anim-file offset; event header = 3 offsets (start, end, data); event data = int32 type, int32 pointer (data+8, or 0 when the event has no payload).
- Anim-file entries: type 0 = own HKX, type 1 = reference to another animation id (e.g. 414300 = a41_4300).
- HKX motion data lives in the split packs `c0000_a00_lo/md/hi`, `c0000_aNx.anibnd.dcx`.
- Spell casts: a00 6200/6300/6400 (right/left/two-handed). Bullet origin is not in the TAE – it is the catalyst hand's weapon dummy (100).
