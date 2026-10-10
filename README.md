# SoraSouls

Personal, free fan project: Sora (Kingdom Hearts II Final Mix) as a playable character in Dark Souls Remastered, with KH2 abilities unlocked through progression.

**Status:** playable development build (offline only). Progress and test results: `ROADMAP.md`.

## ⚠ Changes to vanilla controls – read this first
SoraSouls replaces the player state machine (`mod\chr\c0000.esd.dcx`) so the Kingdom Key can swing **and** cast. **This applies to every weapon that can cast. A normal catalyst in the right hand also now uses L1 + R1 to cast.**

| Right-hand weapon | R1 | R2 | Cast |
|---|---|---|---|
| Kingdom Key | light attack (combos) | heavy attack | **hold L1 + press R1** |
| Any other spell tool (catalyst, talisman, pyromancy flame) | light attack / bash | as vanilla | **hold L1 + press R1** |

- Works one-handed and two-handed: hold L1 (guard) and press R1 to cast.
- Spell tools in the **left** hand still cast with L1 as in vanilla (Sora uses the right-arm cast animation).
- To get vanilla controls back, delete `mod\chr\c0000.esd.dcx` (and `mod\chr\c0000_a00_md.anibnd.dcx` for the vanilla cast arm).
- Tested in-game with the Kingdom Key (2026-10-06); other spell tools use the same patched transitions.

## Getting started
1. Install ModEngine2 for DSR and put the SoraSouls files in its `mod` folder.
2. Start the game with `launchmod_darksoulsremastered.bat` inside the ModEngine2 folder (not Steam's Play button). The Steam game files are never modified.
3. Play **offline**. Back up your saves first (`%APPDATA%\DarkSoulsRemastered`).
4. Glide needs the add-on `mod\sora_glide.dll`: add `"mod/sora_glide.dll"` to `external_dlls` in `config_darksoulsremastered.toml`. It only changes Sora's own gravity and height while you glide (no game code is patched) and writes `mod\sora_glide.log`. Offline only.
5. Create a new character with the **Knight** class – it starts as Sora with the Kingdom Key in the right hand and an empty left hand.

## What's in the mod
| Feature | Notes |
|---|---|
| Sora | Replaces the Knight armor set (head/body/arms/legs) |
| Kingdom Key | Swings and casts (controls above); requires no stats |
| Abilities | KH2-style rings and passives unlocked by defeating bosses ("Sora learned …!") |
| Moogle shop | At the Undead Merchant (Undead Burg): Boost rings, Potion / Hi-Potion / Elixir |
| Magic | Fire, Blizzard, Thunder and Cure families, attuned at bonfires; higher tiers unlock from bosses |
| Drive Forms | Valor, Wisdom, Master, Final (+ Anti Form chance); permanent items, charges refill when you rest |
| Quick Run | Small run-speed passive (Capra Demon unlock) |
| High Jump (prototype) | Running jump rises about 1.5 m higher; always on (see Known limitations) |
| High Jump levels | LV2 after Taurus Demon, MAX after Great Grey Wolf Sif (needs the add-on DLL) |
| Glide (prototype) | Unlocks at Bell Gargoyles; LV2 after Gaping Dragon, MAX after Moonlight Butterfly (each level sinks slower). While falling, **hold B / Circle (Space on keyboard)**; release to fall normally. Needs the add-on DLL (see below) |

Full catalog: `KH2_FEATURES.md`.

## Known limitations
- Spells leave Sora's hand, not the Keyblade tip.
- Kingdom Key spell damage is not tuned yet (no INT scaling); overall balance pass still to come.
- High Jump is a **prototype**: every running jump rises about 1.5 m higher (Sora can land on chest-high ledges). Always on, no unlock or levels yet. Delete `mod\chr\c0000_a00_lo.anibnd.dcx` for the vanilla jump.
- Glide is a **prototype**: no forward boost or steering yet. Gliding prevents fall damage. This build still has test keys (F9 / F10 cycle the Glide / High Jump level). No Aerial Recovery yet.
- Model polish pending (elbows, some transparent texels drawn opaque).
- Thunder/Cure families and -ra/-ga tiers are not all tested in-game yet.

## Release & legal
Sora, Keyblades and all KH2 assets belong to Square Enix / Disney; Dark Souls belongs to FromSoftware / Bandai Namco. This project ships no extracted KH2 or DSR assets and no KH2 or DSR code. A public release will contain only original code, params and scripts plus a converter that builds the assets from the player's own legally owned games. Online play with modified files is not supported.

## For developers
Architecture and learned engine facts: `ARCHITECTURE.md`. Build tools live in `tools/`:
- `build_abilities.py` (+ `drive_forms.py`, `movement.py`, `hybrid_keyblade.py`) – GameParam, events and text.
- `esd_tool.py`, `esd_layout.py`, `esd_rewrite.py`, `esd_seamless_v2.py` – layout-preserving player state machine patch.
- `swap_cast_arm.py` – right-arm cast animations; `tae32.py` – reader for DSR's 32-bit player TAE.
- `blender_swap_sora.py`, `blender_swap_keyblade.py`, `finalize_parts.py` – model conversion.
