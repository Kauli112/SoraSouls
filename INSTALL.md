# SoraSouls – setup guide

SoraSouls is built on your PC from **your own** copies of Dark Souls Remastered and Kingdom Hearts II. This package
contains only SoraSouls' own tools; it contains no game files. Follow the steps in order. `build_sorasouls.bat`
checks every step and tells you which one to look at if something is missing.

| # | What | Where to get it |
|---|---|---|
| 1 | Dark Souls Remastered (Steam) | Your Steam library – install it and start it once |
| 2 | KINGDOM HEARTS HD 1.5+2.5 ReMIX (PC, Steam or Epic) | Your Steam or Epic library – install it |
| 3 | .NET 8 Desktop Runtime (x64) | https://dotnet.microsoft.com/download/dotnet/8.0 – "Desktop Runtime", Windows x64 |
| 4 | OpenKH | https://github.com/OpenKH/OpenKh/releases (tested with 26.4) |
| 5 | Mod Engine 2 | https://github.com/soulsmods/ModEngine2/releases – release 2.1.0 (supports Dark Souls Remastered) |
| 6 | SoraSouls | this folder – run `build_sorasouls.bat` |

## 1. Dark Souls Remastered
Install it from Steam and start it once so it is fully set up. SoraSouls does not change the game's own files.
SoraSouls was made for the current Steam version; the converter warns you if your game version is different.

## 2. Kingdom Hearts II (KINGDOM HEARTS HD 1.5+2.5 ReMIX)
Install it from Steam or the Epic Games Store. Nothing else to do here – OpenKH reads it in step 4.

## 3. .NET 8 Desktop Runtime
OpenKH needs it. Download "**.NET Desktop Runtime 8**" for **Windows x64** from the link above and install it.
(If OpenKH's tools open without an error, you already have it.)

## 4. OpenKH – extract your copy of Kingdom Hearts II
1. Download the latest OpenKH release zip from the link above and unzip it to a folder you will remember,
   for example `C:\Games\OpenKH`.
2. Start `OpenKh.Tools.ModsManager.exe` from that folder. The setup wizard opens on first start.
3. Choose **PC Release**, then **Steam** or **Epic Games Store**, and select your KINGDOM HEARTS HD 1.5+2.5 install
   folder (browse to it by hand if it isn't found).
4. Go through the next screens (Panacea and Lua Backend are not needed for SoraSouls).
5. On the last screen, **extract the game data**. This takes a long time. When it's done, the OpenKH folder has
   `data\kh2\obj` (the KH2 models) and `data\kh2\remastered` (the HD pictures) – that is what SoraSouls needs.

You do **not** need to export any models yourself: the converter does that with your OpenKH.

## 5. Mod Engine 2
1. Download the Mod Engine 2 zip (release 2.1.0) from the link above and unzip it to a folder you will remember,
   for example `C:\Games\ModEngine2`. It does not have to be inside the game folder.
2. The folder must contain `launchmod_darksoulsremastered.bat` and `config_darksoulsremastered.toml`.
   The converter fills its `mod` folder and sets up the config – you don't edit anything by hand.

## 6. Build and install SoraSouls
1. Double-click `build_sorasouls.bat` in this folder.
2. It finds Dark Souls Remastered through Steam and asks once for:
   - your **Mod Engine 2** folder (step 5), and
   - your **OpenKH** folder (step 4 – the one with `OpenKh.Tools.Kh2MdlxEditor.exe`).
   It remembers them for next time.
3. It checks everything, exports the KH2 models with your OpenKH, builds the mod from your game files, checks the
   result against the tested build and installs it into Mod Engine 2. This takes a few minutes. If anything is
   missing it tells you which step above to look at, and nothing is changed.
4. Your previous Mod Engine 2 `mod` folder (if any) is kept as `mod.backup-<date>`.

## 7. Play
1. Back up your saves: copy `%APPDATA%\DarkSoulsRemastered` somewhere safe.
2. Set the game to **Borderless** or **Windowed** (the SoraSouls HUD does not show in exclusive Fullscreen).
3. Start the game with `launchmod_darksoulsremastered.bat` in your Mod Engine 2 folder – **not** Steam's Play button.
4. Play **offline**. Create a new **Knight** – he starts as Sora with the Kingdom Key.
5. Controls and features: `README.md`. What to test and report: `PLAYTEST.md`.

## Problems
- The converter's messages name the step to look at. Its full log is in the folder it prints.
- To remove SoraSouls: delete the `mod` folder in Mod Engine 2 (or rename a `mod.backup-<date>` back to `mod`) and
  start the game from Steam as usual.
- The SoraSouls title video is optional and not installed by the converter.
