# SoraSouls

Personal, free fan project: Sora (Kingdom Hearts II Final Mix) as a playable character in Dark Souls Remastered,
with KH2 abilities, magic, Drive Forms, Keyblades and Donald & Goofy unlocked through progression.

**Status:** playable development build v124, offline only, tested on one PC. Progress and test results:
`ROADMAP.md`. Playtest checklist: `PLAYTEST.md`.

## Changes to vanilla controls – read this first
SoraSouls replaces the player state machine (`mod\chr\c0000.esd.dcx`) so the Kingdom Key can swing **and** cast.
This applies to every weapon that can cast: a normal catalyst in the right hand also uses L1 + R1 to cast.

| Right-hand weapon | R1 | R2 | Cast |
|---|---|---|---|
| Kingdom Key | light attack (combos) | heavy attack | **hold L1 + press R1** |
| Any other spell tool (catalyst, talisman, pyromancy flame) | light attack / bash | as vanilla | **hold L1 + press R1** |

- Works one- and two-handed. Spell tools in the **left** hand still cast with L1 as in vanilla.
- Ladders: climbing up is twice as fast; pressing down slides.
- To get vanilla controls back, delete `mod\chr\c0000.esd.dcx`.

| Extra input | Keyboard | Controller |
|---|---|---|
| Glide (while falling, once unlocked) | hold Space | hold B / Circle |
| Abilities panel | J | hold L3 for a moment |

## Getting started
**Setup, step by step: `INSTALL.md`.** In short – **what you need:** Dark Souls Remastered (Steam), the PC release of KINGDOM HEARTS HD 1.5+2.5 ReMIX, Mod Engine 2
for DSR, and OpenKH with your copy of KH2 extracted by its own extractor (that gives OpenKH's `data\kh2` folder).

**Building the mod:** run `build_sorasouls.bat`. It finds Dark Souls Remastered through Steam and asks once for the
Mod Engine 2 folder and your OpenKH folder. It checks every file it needs, exports the KH2 models with your OpenKH
(the same export OpenKH's model editor does – no clicking), builds the mod from your own game files (the game folders
are only read), checks the result against the tested build and installs it (your previous `mod` folder is kept as
`mod.backup-<date>`). The package contains no KH2 or DSR files; everything game-related is made on your PC.
The converter lists anything missing before it changes anything. Then:

1. Install Mod Engine 2 for DSR (the converter fills its `mod` folder). The Steam game files are not
   modified (one exception: the title video, see Known limitations).
2. In `config_darksoulsremastered.toml`, `external_dlls` must list `"mod/sora_glide_v91.dll"` – the add-on that
   runs Glide, High Jump levels, MP Charge, the Drive gauge, the HUD, Drive Form outfits and Donald & Goofy's
   following. It writes `mod\sora_glide.log`.
3. Start the game with `launchmod_darksoulsremastered.bat` (not Steam's Play button). Play **offline** in
   **Borderless or Windowed** mode (the HUD is a separate window; exclusive Fullscreen hides it). Back up your saves
   first (`%APPDATA%\DarkSoulsRemastered`).
4. Create a new character with the **Knight** class – it starts as Sora with the Kingdom Key and Fire.

## What's in the mod
| Feature | Notes |
|---|---|
| Sora | Replaces the Knight armor set; KH2 model and textures |
| Kingdom Key | Swings and casts (controls above); upgrades with normal Titanite to +10 |
| Six more Keyblades | Star Seeker, Hidden Dragon, Fenrir, Oathkeeper, Oblivion, Ultima Weapon – boss drops, each with a perk |
| Magic | Fire, Blizzard, Thunder and Cure families, attuned at bonfires; higher tiers unlock from bosses |
| MP Charge | Spells share one MP pool; when it runs out it refills after a short charge (bonfires refill too) |
| Drive Forms | Valor, Wisdom, Master, Final (+ Anti Form chance); the Drive gauge fills when Sora lands hits and takes damage; Sora's outfit changes with the form |
| Abilities | KH2-style passives and rings unlocked by bosses ("Sora learned …!" on the HUD); full list in the panel (J / L3) |
| Moogle shop | At the Undead Merchant (Undead Burg): Boost rings, Potion / Hi-Potion / Elixir |
| Movement | Quick Run, High Jump (LV2 after Taurus Demon, MAX after Sif), Glide (Bell Gargoyles; LV2 Gaping Dragon, MAX Moonlight Butterfly) |
| Roxas (when Hollow) | While Sora is Hollow he looks like Roxas (KH2 model, fitted with Sora's own fit) |
| Donald & Goofy | The "Donald & Goofy" item calls them (use again to send them away); KH2 models, Donald casts, Goofy bashes with his shield |
| Title screen | "SORA SOULS" logo and intro |

Full catalog: `KH2_FEATURES.md`.

## Known limitations
- Spells leave from the Kingdom Key's tip; longer Keyblades still cast from that same point.
- Thunder spells use Lightning Spear's throw animation (that is where the game plays the thunder sound).
- The title video is read from the game's own `movww` folder, not the mod folder; the vanilla copy is kept next to
  it as `frpg_title.bik.vanilla`.
- Glide has no forward boost or steering yet; gliding prevents fall damage. No Aerial Recovery yet.
- Donald & Goofy can block narrow paths; pushing into one swaps him behind Sora.

## Release & legal
Sora, Keyblades and all KH2 assets belong to Square Enix / Disney; Dark Souls belongs to FromSoftware / Bandai Namco.
SoraSouls ships no extracted KH2 or DSR assets and no KH2 or DSR code. A public release will contain only original
code, params logic, scripts and model recipes plus a converter that builds the mod from the player's own legally owned
games (`CONVERTER_PLAN.md`). Until that converter is finished, the mod is tested only on the developer's PC.
Online play with modified files is not supported.

SoraSouls's own code (tools, DLL source, scripts) is licensed under the GNU General Public License v3.0 or later –
see `LICENSE`. Bundled third-party software keeps its own licence (`THIRD_PARTY.txt` in the package).

## For developers
Architecture and learned engine facts: `ARCHITECTURE.md`. Converter plan and rebuild status: `CONVERTER_PLAN.md`.
Tools live in `tools/` and run on Python 3.13 with soulstruct 2.6.0, Pillow, numpy, matplotlib and scikit-image
(project environment: `.venv`).
- `rebuild_mod.py` – rebuilds the whole `mod` folder from vanilla DSR files and the player's KH2 exports, no Blender:
  `python tools\rebuild_mod.py <DSR folder> <out mod folder> --kh2 <exports> --openkh <OpenKH data\kh2> --compare <mod>`
- `build_abilities.py` (+ `drive_forms.py`, `mp_drive.py`, `keyblades.py`, `movement*.py`, `party.py`) – params,
  events and text; `party_ai.py` / `party_logic.py` – Donald & Goofy's AI.
- `esd_*.py`, `ladder_fast.py`, `cast_glow_tip.py`, `root_motion_test.py`, `spell_tip.py` – player state machine and
  animation patches.
- `model_recipe.py` – rebuilds Sora, the Drive Form outfits, Donald, Goofy and the Kingdom Key from the player's KH2
  exports; `drive_outfits.py`, `make_keyblades.py`, `make_party_weapons.py`, `keyblade_icons.py`, `sora_title.py`.
- `dll/sora_glide.c` – the add-on DLL: `dll\build.bat` on Windows (LLVM from winget), `dll/build.sh` on Linux.
