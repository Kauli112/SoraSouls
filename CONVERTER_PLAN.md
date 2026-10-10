# SoraSouls converter – plan and build inventory

Written 2026-10-10 (after v123). Goal: a tester who owns Dark Souls Remastered and Kingdom Hearts II runs one
`build_sorasouls.bat`, and the finished `mod` folder is built on their PC from their own game files. The SoraSouls
package itself contains only original material: the DLL, the Python tools, original data (recipes, params logic,
scripts) and documents. No file from KH2 or DSR, and no file made from them, is ever shipped.

Status legend: **scripted** = a tool already builds it from game files without manual steps · **chain** = scripted, but
the tested file came out of several tools run in sequence over time; the exact order must be confirmed by a rebuild
from vanilla that matches the deployed file · **Blender** = needs Blender today · **manual** = needs a step the tester
does by hand.

## 1. What a tester needs

| Need | Notes |
|---|---|
| Dark Souls Remastered (Steam), current version | The DLL finds its addresses by pattern scan; layout offsets were measured on the exe with image size 0x319B000. The converter checks the exe before building. |
| Kingdom Hearts II from the PC release of KINGDOM HEARTS HD 1.5+2.5 ReMIX | The converter reads **exports** of the game's files (FBX models, PNG textures, HD item pictures), see section 4. |
| Mod Engine 2 for DSR | Not shipped by us; the guide links the official release. |
| Windows 10/11 | The converter ships with its own Python, so nothing else to install. |

## 2. Inventory: every file in the deployed `mod` folder

### Built from DSR files only

| Output | Tool(s) | DSR input | Status |
|---|---|---|---|
| `param/GameParam/GameParam.parambnd.dcx` | build_abilities.py (+ drive_forms, keyblades, mp_drive, movement, movement_levels, sora_class, party, drive_outfits.build_params) | vanilla GameParam | scripted |
| `event/common.emevd.dcx`, `event/m*.emevd.dcx` (18 maps) | build_abilities.py, party.py | vanilla events | scripted |
| `msg/ENGLISH/item.msgbnd.dcx`, `menu.msgbnd.dcx` | build_abilities.py | vanilla text | scripted (English only) |
| `map/MapStudio/*.msb` (18) | party.py (patch_maps: two disabled characters per map) | vanilla MSBs | scripted |
| `script/m*.luabnd.dcx` (17) | party_ai.py + party_logic.py (own AI logic, written with lua50.py) | vanilla luabnds | scripted |
| `chr/c0000.esd.dcx` | esd_seamless_v2.py (via esd_tool/esd_rewrite), ladder_fast.py | vanilla c0000.esd | chain |
| `chr/c0000_a00_md.anibnd.dcx` | swap_cast_arm.py, ladder_fast.py | vanilla anibnd | chain |
| `chr/c0000.anibnd.dcx` | cast_glow_tip.py, glide_test.py / movement, cast_from_weapon.py, ladder_fast.py | vanilla anibnd | chain |
| `chr/c0000_a00_lo.anibnd.dcx` | root_motion_test.py / glide_test.py (High Jump) | vanilla anibnd | chain |
| `chr/c0000.chrbnd.dcx` | spell_tip.py (spell origin at the Keyblade tip) | vanilla chrbnd + WP_A_0204 | chain |
| `menu/menu_0.tpf.dcx`, `menu_4.tpf.dcx`, `ENGLISH/menu_local.tpf.dcx` | keyblade_icons.py, then sora_title.py | vanilla menu textures | scripted (needs KH2 item pictures too) |
| `menu/menu_3.tpf.dcx`, `menu.drb`, `menu.drb.dcx` | keyblade_icons.py | vanilla menu | scripted (needs KH2 item pictures) |
| `movww/frpg_title.bik` (intro video) | sora_title_movie.py writes the frames | vanilla frpg_title.bik + menu_local | **manual**: the frames must be encoded with RAD Video Tools (Bink 1, free from RAD). There is no open Bink encoder. The game also reads this file from its own folder, not from the mod folder (v123 finding), so it has to be swapped there. |
| `parts/WP_A_1309.partsbnd.dcx` | make_invisible_focus.py | vanilla WP_A_0910 | scripted (still used by row 1310000 "Keyblade Focus", an early experiment) |
| `sora_glide_v77.dll` | our C code (dll/build.sh) | none | ships as is |

### Built from KH2 exports (plus DSR templates)

| Output | Tool(s) | KH2 input | Status |
|---|---|---|---|
| Sora `HD_A/BD_A/AM_A/LG_M/LG_F_9550[_M]` | **Blender**: blender_fit_sora.py, blender_swap_sora.py (Soulstruct Blender add-on) → finalize_parts.py → reskin_sora_head.py → fit_sora_arms.py → smooth_sora_normals.py → fix_sora_normalmap.py → sora_specular.py → fix_seam_normals.py → drive_outfits.py (textures) → sync_part_variants.py | `sora/P_EX100.fbx`, `Texture0000-0002.png` | **Blender** + chain |
| Form outfits `*_9551..9555[_M]` | drive_outfits.py (+ sync_part_variants) | `drive/<form>/Texture0000-0002.png` (5 forms) | scripted (from Sora's parts) |
| Kingdom Key `WP_A_0204` | blender_swap_keyblade.py → fix_keyblade_normalmap.py → spell_tip.py | `keyblade/W_EX010.fbx` + png | **Blender** |
| Keyblades `WP_A_0292..0297` | make_keyblades.py (+ thicken_cards.py) | `keyblade/W_EX010_10/20/30/40/M0/N0.fbx` | scripted (no Blender) |
| Donald & Goofy `*_9560`, `*_9570` | kh_party_model.py (kh_fbx.py) | `donald/P_EX020.fbx`, `goofy/P_EX030.fbx` + png | scripted, but uses Sora's finished parts as its template |
| Staff & shield `WP_A_0298`, `WP_A_0299` | make_party_weapons.py | `W_EX020.fbx`, `W_EX030.fbx` | scripted |
| Keyblade / crown / Drive item icons | keyblade_icons.py | `remastered/itempic/item-043…064, 344, 007, 008` | scripted |

### Leftovers to remove before testers get it
- `sora_glide.dll` and `sora_glide_v42`–`v76.dll` (only v77 is loaded).
- `WP_A_1311`, `WP_A_1312` (no param row uses these models any more).
- Config: `debug = true` and `scylla_hide` on; the disabled `dsr-lighting.dll-` entry.
- README/PLAYTEST: still describe v43-era features and the removed F9/F10 test keys.

## 3. Removing Blender from the tester's side

Today Sora and the Kingdom Key pass through Blender once, then through about ten scripted fix-ups. Rebuilding that
fitting automatically would not reproduce the model that has been tested. Plan instead: a **recipe** that replays
the finished result from the tester's own export.

- For each finished vertex, the recipe stores the KH2 vertex it comes from, the DSR bones and weights we assigned,
  and our position/normal adjustment relative to that vertex. Geometry, UVs and textures always come from the
  tester's export, so the recipe holds only our own work and is useless without the game.
- Feasibility check done (v123): UVs survive the pipeline (V flipped, rounded to 1/1024), so source vertices can be
  matched by UV + position. Many UVs are shared by several vertices (seams), so the matcher also needs position and
  triangle neighbours. Not built yet.
- The same recipe approach covers the Kingdom Key. Donald & Goofy and the six Keyblades are already Blender-free;
  Donald & Goofy would take Sora's rebuilt parts as their template, as now.

## 4. KH2 exports – open question

The converter reads FBX/PNG exports like the ones in `work/` (OpenKH Kh2MdlxEditor exports and the HD item pictures
from OpenKH's data folder). As far as I know, the PC release keeps its files in encrypted archives, and OpenKH's
extractor decrypts them. I will not build that decryption into the converter or write steps for it, so the converter
starts from exports the tester already has. Before going further, this needs a decision from you (see the chat).

The converter will check each export before using it (expected files, vertex/triangle counts, texture sizes) and stop
with a clear message if anything differs, instead of building a broken model.

## 5. Converter steps (target)

1. Check: DSR folder and exe version, Mod Engine 2 folder, KH2 export folder (every required file present and matching).
2. Copy the needed vanilla DSR files to a temporary folder (the game install is only read).
3. DSR-only builds in a fixed order (section 2, first table); the chain items get one script each that replays the
   order confirmed by the rebuild test.
4. KH2 builds: Sora and Kingdom Key from recipes, then forms, Keyblades, Donald & Goofy, weapons, icons.
5. Write `mod\`, the DLL and the config; write `build_report.txt` (every file with its checksum).
6. Optional: intro frames + instructions for RAD Video Tools and the game-folder swap.

## 6. Work order

1. Rebuild test: run the whole build from vanilla files here and compare every output with the deployed `mod`
   folder; fix or record each difference (this pins down the chain items).
   **Done for every non-model file (2026-10-10):** `tools/rebuild_mod.py` rebuilds params, events, text, maps,
   scripts, the five `chr` files, `WP_A_1309` and the menu textures; all 68 match the deployed v123 files byte for
   byte. The chain turned out to be shorter than the table above: `swap_cast_arm.py` and `cast_from_weapon.py` are
   not in the shipped build (md binder = vanilla + ladder_fast; c0000.anibnd = cast_glow_tip + ladder_fast).
   Tools run on Python 3.13 + soulstruct 2.6.0 (`.venv`). Still open: the KH2 model parts.
2. Recipe extractor + replayer for Sora and the Kingdom Key; prove that the replay reproduces the deployed parts.
3. `build_sorasouls.py` (one entry point) and the Windows package (embedded Python, wheels, .bat).
4. Clean-up list above; new README (install, build, play, uninstall) and PLAYTEST.
5. Fresh-machine test: unpack the package into a new folder, build, compare with the reference, play.
6. Licences of bundled third-party code (Python, numpy, Pillow, Soulstruct, soulstruct-havok) checked and listed.
