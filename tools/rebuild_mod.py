"""SoraSouls – rebuild the non-model part of the mod folder from vanilla DSR files (+ KH2 item pictures for menus).

Order confirmed 2026-10-10 by rebuilding from vanilla and comparing with the deployed v123 mod folder: every file
below came out byte-identical. Findings that pinned the order down:
  * c0000.anibnd.dcx = cast_glow_tip -> ladder_fast. cast_from_weapon (v68 experiment) is NOT in the deployed build.
  * c0000_a00_md.anibnd.dcx = ladder_fast on the VANILLA md binder. swap_cast_arm is NOT in the deployed build.
  * c0000_a00_lo.anibnd.dcx = root_motion_test with JUMP_GLIDE_TEST off (plain v32 High Jump arc).
  * c0000.esd.dcx = ladder_fast's esd_seamless_v2 pass on the vanilla ESD (+ StateMachine_1 ESP text).
Not covered yet: Sora / form / party / Keyblade parts (KH2 models), the DLL, the title video.

Usage: python rebuild_mod.py <DSR game dir> <out mod dir> [<keyblade export dir> <OpenKH remastered itempic dir>]
       [--compare <reference mod dir>]
The game folder is only read. Without the KH2 arguments the menu textures are skipped.
"""
import hashlib, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def run(*args):
    print(">", " ".join(os.path.basename(a) if os.path.isabs(a) else a for a in args[:1]), *args[1:2])
    subprocess.run([sys.executable, os.path.join(HERE, args[0]), *args[1:]], cwd=HERE, check=True)


def decompile_machine_1(esd, out):
    sys.path.insert(0, HERE)
    import esd_tool  # noqa: F401  (patches soulstruct's ESP decompiler)
    from soulstruct.darksouls1r.ezstate.esd.core import ChrESD
    with open(out, "w", encoding="utf-8") as f:
        f.write(ChrESD.from_path(esd).to_esp(state_machine_index=1))


def build(game, mod, keyblade_dir=None, itempic_dir=None):
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
    if keyblade_dir and itempic_dir:
        menu = os.path.join(game, "menu")
        with tempfile.TemporaryDirectory() as tmp:
            run("keyblade_icons.py", keyblade_dir, keyblade_dir, menu, mod, os.path.join(tmp, "icons.png"), itempic_dir)
            run("sora_title.py", menu, mod, os.path.join(tmp, "title.png"))
        for root, _, files in os.walk(os.path.join(mod, "menu")):
            for f in files:
                if f.endswith(".bak"):                    # soulstruct's automatic backup of overwritten files
                    os.remove(os.path.join(root, f))
    else:
        print("menu textures skipped (no KH2 keyblade/itempic folders given)")


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def compare(mod, ref):
    same = diff = 0
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
                diff += 1
                print("  DIFFERENT:", rel)
    print(f"compare: {same} identical, {diff} different")
    return diff == 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    ref = None
    if "--compare" in argv:
        i = argv.index("--compare")
        ref = argv[i + 1]
        del argv[i:i + 2]
    build(*argv[:4])
    if ref and not compare(argv[1], ref):
        sys.exit(1)
