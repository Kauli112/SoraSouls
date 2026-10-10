"""SoraSouls – rebuild the mod folder from vanilla DSR files and the player's own KH2 files.

Order confirmed 2026-10-10 by rebuilding from vanilla and comparing with the deployed v123 mod folder.
Byte-identical: params, events, text, maps, scripts, the five chr files, WP_A_1309, menus, and (from model recipes)
every Sora / Drive Form / Donald / Goofy part, the Kingdom Key model, the six extra Keyblades and Donald's staff /
Goofy's shield.
Findings that pinned the order down:
  * c0000.anibnd.dcx = cast_glow_tip -> ladder_fast. cast_from_weapon (v68 experiment) is NOT in the deployed build.
  * c0000_a00_md.anibnd.dcx = ladder_fast on the VANILLA md binder. swap_cast_arm is NOT in the deployed build.
  * c0000_a00_lo.anibnd.dcx = root_motion_test with JUMP_GLIDE_TEST off (plain v32 High Jump arc).
  * c0000.esd.dcx = ladder_fast's esd_seamless_v2 pass on the vanilla ESD (+ StateMachine_1 ESP text).
  * Sora + forms = model_recipe replay of the four plain *_9550 parts -> drive_outfits.py (writes all 60 files).
  * Donald / Goofy = model_recipe replay -> textures from their PNGs -> sync_part_variants.py.
Not rebuilt here: the DLL, the title video. The Kingdom Key texture is written from the KH2 artwork (v123 had
Blender's darker conversion; user choice 2026-10-10: keep the true artwork). Needs matplotlib + scikit-image.

Usage: python rebuild_mod.py <DSR game dir> <out mod dir> [--kh2 <export dir>] [--openkh <OpenKH data/kh2 dir>]
                             [--recipes <recipe dir>] [--compare <reference mod dir>]
  --kh2     folder with the player's OpenKH exports: sora/ drive/<form>/ donald/ goofy/ keyblade/ (FBX + PNG)
  --openkh  the player's OpenKH data/kh2 folder (obj/W_EX010.mdlx, remastered/itempic)
The game folder is only read. Without --kh2/--openkh the KH2-based files are skipped.
"""
import hashlib, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = ("HD_A", "BD_A", "AM_A", "LG_M")
PARTY = (("donald", "9560", "P_EX020"), ("goofy", "9570", "P_EX030"))


def run(*args):
    print(">", args[0], *(os.path.basename(a) for a in args[1:2]))
    subprocess.run([sys.executable, os.path.join(HERE, args[0]), *args[1:]], cwd=HERE, check=True)


def decompile_machine_1(esd, out):
    sys.path.insert(0, HERE)
    import esd_tool  # noqa: F401  (patches soulstruct's ESP decompiler)
    from soulstruct.darksouls1r.ezstate.esd.core import ChrESD
    with open(out, "w", encoding="utf-8") as f:
        f.write(ChrESD.from_path(esd).to_esp(state_machine_index=1))


def build_dsr(game, mod):
    chr_van, chr_out = os.path.join(game, "chr"), os.path.join(mod, "chr")
    os.makedirs(chr_out, exist_ok=True)
    run("build_abilities.py", game, mod)                  # GameParam, common event, item/menu text, dll/hud_data.h
    run("party.py", game, mod)                            # map events + MSBs (Donald & Goofy)
    run("party_ai.py", game, mod)                         # map luabnds
    with tempfile.TemporaryDirectory() as tmp:
        run("cast_glow_tip.py", os.path.join(chr_van, "c0000.anibnd.dcx"), tmp)
        esp = os.path.join(tmp, "StateMachine_1.esp.py")
        decompile_machine_1(os.path.join(chr_van, "c0000.esd.dcx"), esp)
        run("ladder_fast.py", os.path.join(chr_van, "c0000_a00_md.anibnd.dcx"), os.path.join(tmp, "c0000.anibnd.dcx"),
            os.path.join(chr_van, "c0000.esd.dcx"), esp, chr_out)
    run("root_motion_test.py", os.path.join(chr_van, "c0000_a00_lo.anibnd.dcx"), chr_out)
    run("spell_tip.py", os.path.join(chr_van, "c0000.chrbnd.dcx"), "-", mod)
    run("make_invisible_focus.py", os.path.join(game, "parts", "WP_A_0910.partsbnd.dcx"), os.path.join(mod, "parts"))


def build_menus(game, mod, kh2, openkh):
    menu = os.path.join(game, "menu")
    with tempfile.TemporaryDirectory() as tmp:
        kb = os.path.join(kh2, "keyblade")
        run("keyblade_icons.py", kb, kb, menu, mod, os.path.join(tmp, "icons.png"),
            os.path.join(openkh, "remastered", "itempic"))
        run("sora_title.py", menu, mod, os.path.join(tmp, "title.png"))


def build_sounds(game, mod, openkh):
    # v127: Sora's KH2 voice – death voice in the sound bank, cast voices for the add-on (tools/sora_sounds.py)
    run("sora_sounds.py", os.path.join(openkh, "voice", "us", "battle"), game, mod)


def build_models(game, mod, kh2, openkh, recipes):
    parts = os.path.join(mod, "parts")
    with tempfile.TemporaryDirectory() as tmp:
        sora = os.path.join(kh2, "sora", "P_EX100.fbx")
        for p in PARTS:
            run("model_recipe.py", "replay", recipes, f"{p}_9550", sora, tmp, game)
        run("drive_outfits.py", tmp, os.path.join(kh2, "drive"), parts)
    for who, model, fbx in PARTY:
        for p in PARTS:
            run("model_recipe.py", "replay", recipes, f"{p}_{model}", os.path.join(kh2, who, fbx + ".fbx"), parts, game)
            run("model_recipe.py", "pngs", os.path.join(parts, f"{p}_{model}.partsbnd.dcx"), os.path.join(kh2, who))
    run("sync_part_variants.py", parts, parts, *(m for _, m, _ in PARTY))
    # v126: Roxas (Sora's look while Hollow), fitted with Sora's own fit (tools/roxas_model.py)
    with tempfile.TemporaryDirectory() as tmp:
        skel = os.path.join(tmp, "skeleton.json")
        run("dsr_skeleton.py", os.path.join(game, "chr", "c0000.chrbnd.dcx"), skel)
        run("roxas_model.py", os.path.join(kh2, "roxas"), os.path.join(kh2, "sora"), parts, recipes, skel, parts)
    run("make_party_weapons.py", kh2, os.path.join(game, "parts"), parts)
    run("model_recipe.py", "replay", recipes, "WP_A_0204", os.path.join(kh2, "keyblade", "W_EX010.fbx"), parts, game)
    run("model_recipe.py", "texture", os.path.join(parts, "WP_A_0204.partsbnd.dcx"),
        os.path.join(openkh, "obj", "W_EX010.mdlx"))
    # the six extra Keyblades: FBX exports + texture sheets read from the .mdlx (OpenKH's export overwrites
    # Texture0000.png for every Keyblade), built on the Kingdom Key binder
    sys.path.insert(0, HERE)
    from keyblades import KEYBLADES
    with tempfile.TemporaryDirectory() as tmp:
        for kb in KEYBLADES:
            shutil.copy(os.path.join(kh2, "keyblade", kb["fbx"] + ".fbx"), tmp)
            run("kh2_weapon_texture.py", os.path.join(openkh, "obj", kb["fbx"] + ".mdlx"),
                os.path.join(tmp, kb["fbx"] + ".png"))
        run("make_keyblades.py", tmp, os.path.join(parts, "WP_A_0204.partsbnd.dcx"), parts)


def tidy(mod):
    for root, _, files in os.walk(mod):
        for f in files:
            if f.endswith(".bak"):                        # soulstruct's automatic backup of overwritten files
                os.remove(os.path.join(root, f))


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def compare(mod, ref):
    same, diff = 0, []
    for root, _, files in os.walk(mod):
        for f in files:
            p = os.path.join(root, f)
            rel = os.path.relpath(p, mod)
            r = os.path.join(ref, rel)
            if not os.path.exists(r):
                print("  only rebuilt:", rel)
            elif sha(p) == sha(r):
                same += 1
            else:
                diff.append(rel)
    for rel in diff:
        print("  DIFFERENT:", rel)
    print(f"compare: {same} identical, {len(diff)} different")
    return not diff


def main(argv):
    opts = {}
    for name in ("--kh2", "--openkh", "--recipes", "--compare"):
        if name in argv:
            i = argv.index(name)
            opts[name] = argv[i + 1]
            del argv[i:i + 2]
    game, mod = argv[:2]
    build_dsr(game, mod)
    kh2, openkh = opts.get("--kh2"), opts.get("--openkh")
    if kh2 and openkh:
        build_menus(game, mod, kh2, openkh)
        build_models(game, mod, kh2, openkh, opts.get("--recipes", os.path.join(os.path.dirname(HERE), "data", "recipes")))
        build_sounds(game, mod, openkh)
    else:
        print("KH2-based files skipped (no --kh2 / --openkh)")
    tidy(mod)
    if "--compare" in opts:
        return compare(mod, opts["--compare"])
    return True


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1:]) else 1)
