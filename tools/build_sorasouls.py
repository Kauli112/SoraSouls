"""SoraSouls – one-click converter: build the mod from the player's own Dark Souls Remastered and KH2 files and
install it into Mod Engine 2 (v124).

Steps:
  1. Find the folders: DSR (from Steam's library list), Mod Engine 2, the player's OpenKH and its data/kh2 folder
     (KH2 extracted with OpenKH). The model exports are made automatically with OpenKH's own code (kh2_export.py);
     --kh2 uses hand-made exports instead. Answers are remembered in sorasouls_settings.json next to the package; flags override them.
  2. Check them: DSR exe version (image size the DLL was built against), every KH2 file the build reads, Mod Engine 2.
  3. Build into a temporary folder with rebuild_mod.py (the game folder is only read).
  4. Compare every built file with the SHA-256 list of the tested build (data/expected_build.json – checksums only,
     no content). Differences are listed; installing then needs --force (a different export can give a different
     model).
  5. Install: the current Mod Engine 2 mod folder is moved to mod.backup-<time>, the new one copied in with the
     add-on DLL, and config_darksoulsremastered.toml pointed at it. build_report.txt lists every file + checksum.

  python build_sorasouls.py [--dsr DIR] [--modengine DIR] [--openkh-app DIR] [--openkh DIR] [--kh2 DIR] [--recipes DIR]
                            [--dll FILE]
                            [--force] [--no-install] [--yes]
  python build_sorasouls.py --write-expected <reference mod dir>     (developer: record the tested build)
"""
import datetime, glob, hashlib, json, os, re, shutil, struct, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SETTINGS = os.path.join(ROOT, "sorasouls_settings.json")
EXPECTED = os.path.join(ROOT, "data", "expected_build.json")
DSR_IMAGE_SIZE = 0x319B000          # DarkSoulsRemastered.exe the DLL's offsets were measured on
DLL_NAME = "sora_glide_v94.dll"
FORMS = ("valor", "wisdom", "master", "final", "antiform")
KEYBLADE_FBX = ("W_EX010", "W_EX010_30", "W_EX010_40", "W_EX010_M0", "W_EX010_10", "W_EX010_20", "W_EX010_N0")
ITEMPIC = (43, 44, 45, 46, 47, 63, 64, 344)
# files that differ from the tested build by design or are not built here
NOT_COMPARED = {"event/common.emevd.dcx.evs.py"}


def kh2_required(kh2, openkh):
    t = [f"Texture000{i}.png" for i in range(3)]
    need = [os.path.join(kh2, "sora", "P_EX100.fbx")] + [os.path.join(kh2, "sora", x) for x in t]
    need += [os.path.join(kh2, "roxas", "P_EX110.fbx")] + [os.path.join(kh2, "roxas", x) for x in t[:2]]
    need += [os.path.join(kh2, "drive", f, x) for f in FORMS for x in t]
    for who, body, weapon in (("donald", "P_EX020", "W_EX020"), ("goofy", "P_EX030", "W_EX030")):
        need += [os.path.join(kh2, who, body + ".fbx"), os.path.join(kh2, who, weapon + ".fbx"),
                 os.path.join(kh2, who, weapon + "_Texture0000.png")] + [os.path.join(kh2, who, x) for x in t]
    need += [os.path.join(kh2, "keyblade", k + ".fbx") for k in KEYBLADE_FBX]
    need += [os.path.join(openkh, "obj", k + ".mdlx") for k in KEYBLADE_FBX]
    need += [os.path.join(openkh, "remastered", "itempic", f"item-{n:03d}.imd", "-0.dds") for n in ITEMPIC]
    return need


def steam_dsr():
    """DSR folder from Steam's library list (registry + libraryfolders.vdf)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            steam = winreg.QueryValueEx(k, "SteamPath")[0]
    except OSError:
        return None
    libs = [steam]
    vdf = os.path.join(steam, "steamapps", "libraryfolders.vdf")
    if os.path.exists(vdf):
        with open(vdf, encoding="utf-8", errors="replace") as f:
            libs += [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', f.read())]
    for lib in libs:
        p = os.path.join(lib, "steamapps", "common", "DARK SOULS REMASTERED")
        if os.path.exists(os.path.join(p, "DarkSoulsRemastered.exe")):
            return os.path.normpath(p)
    return None


def pe_image_size(exe):
    with open(exe, "rb") as f:
        d = f.read(4096)
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    return struct.unpack_from("<I", d, pe + 24 + 56)[0]          # OptionalHeader.SizeOfImage (PE32+)


def ask(label, current, check, interactive):
    while True:
        if current and check(current):
            return os.path.normpath(current)
        if current:
            print(f"  {label}: not valid: {current}")
        if not interactive:
            sys.exit(f"Missing or invalid {label}. Pass it on the command line.")
        current = input(f"  Folder for {label}: ").strip().strip('"')


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def listing(mod):
    out = {}
    for root, _, files in os.walk(mod):
        for f in files:
            p = os.path.join(root, f)
            out[os.path.relpath(p, mod).replace("\\", "/")] = sha(p)
    return out


def write_config(modengine, dll_rel):
    cfg = os.path.join(modengine, "config_darksoulsremastered.toml")
    with open(cfg, encoding="utf-8") as f:
        t = f.read()
    new = f'external_dlls = [\n    "{dll_rel}"\n]'
    t2, n = re.subn(r"external_dlls\s*=\s*\[[^\]]*\]", new, t)
    if n != 1:
        sys.exit(f"{cfg}: could not find external_dlls – add \"{dll_rel}\" there yourself")
    if t2 != t:
        shutil.copy(cfg, cfg + ".backup-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        with open(cfg, "w", encoding="utf-8", newline="\n") as f:
            f.write(t2)


def main(argv):
    opts, flags = {}, set()
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--force", "--no-install", "--yes"):
            flags.add(a); i += 1
        else:
            opts[a] = argv[i + 1]; i += 2
    if "--write-expected" in opts:
        # the reference may be a deployed mod folder: the add-on DLL, its log and the title video are not built here
        data = {k: v for k, v in listing(opts["--write-expected"]).items()
                if k not in NOT_COMPARED and not k.endswith((".dll", ".log", ".txt")) and not k.startswith("movww/")}
        os.makedirs(os.path.dirname(EXPECTED), exist_ok=True)
        with open(EXPECTED, "w", encoding="utf-8") as f:
            json.dump(dict(build="v126", files=data), f, indent=1, sort_keys=True)
        print(f"wrote {EXPECTED}: {len(data)} files")
        return 0

    interactive = sys.stdin.isatty() and "--yes" not in flags
    saved = json.load(open(SETTINGS, encoding="utf-8")) if os.path.exists(SETTINGS) else {}
    print("SoraSouls converter\n1. Folders")
    print("  (setup guide: INSTALL.md)")
    dsr = ask("Dark Souls Remastered (INSTALL.md step 1)", opts.get("--dsr") or saved.get("dsr") or steam_dsr(),
              lambda p: os.path.exists(os.path.join(p, "DarkSoulsRemastered.exe")), interactive)
    me = ask("Mod Engine 2 (the folder with launchmod_darksoulsremastered.bat – INSTALL.md step 5)",
             opts.get("--modengine") or saved.get("modengine"),
             lambda p: all(os.path.exists(os.path.join(p, n)) for n in
                           ("config_darksoulsremastered.toml", "launchmod_darksoulsremastered.bat")), interactive)
    okh = ask("OpenKH (the folder with OpenKh.Tools.Kh2MdlxEditor.exe – INSTALL.md step 4)", opts.get("--openkh-app") or saved.get("openkh_app"),
              lambda p: os.path.exists(os.path.join(p, "OpenKh.Tools.Kh2MdlxEditor.dll")), interactive)
    openkh = ask("OpenKH data\\kh2 (KH2 extracted with OpenKH: obj\\, remastered\\ – INSTALL.md step 4)",
                 opts.get("--openkh") or saved.get("openkh") or os.path.join(okh, "data", "kh2"),
                 lambda p: os.path.isdir(os.path.join(p, "obj")), interactive)
    kh2 = opts.get("--kh2")                       # optional: hand-made exports instead of the automatic ones
    recipes = opts.get("--recipes") or saved.get("recipes") or os.path.join(ROOT, "data", "recipes")
    dll = opts.get("--dll") or saved.get("dll") or os.path.join(ROOT, "bin", DLL_NAME)
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(dict(dsr=dsr, modengine=me, openkh_app=okh, openkh=openkh, recipes=recipes, dll=dll), f, indent=1)

    print("2. Checks")
    problems = []
    size = pe_image_size(os.path.join(dsr, "DarkSoulsRemastered.exe"))
    if size != DSR_IMAGE_SIZE:
        problems.append(f"DarkSoulsRemastered.exe has image size {size:#x}, SoraSouls was made for {DSR_IMAGE_SIZE:#x}"
                        " (different game version – the add-on DLL may not work; INSTALL.md step 1)")
    sys.path.insert(0, HERE)
    from kh2_export import JOBS
    need = [os.path.join(openkh, "obj", m + ".mdlx") for _, m, _, _ in JOBS] if not kh2 else kh2_required(kh2, openkh)
    need += [os.path.join(openkh, "obj", k + ".mdlx") for k in KEYBLADE_FBX]
    need += [os.path.join(openkh, "remastered", "itempic", f"item-{n:03d}.imd", "-0.dds") for n in ITEMPIC]
    need += [os.path.join(openkh, "voice", "us", "battle", "tt0_sora.win32.scd")]      # v127 Sora's voice
    missing = sorted(set(p for p in need if not os.path.exists(p)))
    if missing:
        problems.append(f"{len(missing)} KH2 files missing from {openkh} (first: {missing[0]}) – extract your KH2 with "
                        "OpenKH's Mods Manager wizard, last screen (INSTALL.md step 4)")
    if not kh2 and not glob.glob(os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "dotnet", "shared",
                                              "Microsoft.WindowsDesktop.App", "8.*")):
        problems.append(".NET 8 Desktop Runtime not found – OpenKH needs it (INSTALL.md step 3)")
    if not os.path.isdir(recipes) or not any(n.endswith(".recipe.json") for n in os.listdir(recipes)):
        problems.append(f"model recipes not found in {recipes}")
    if not os.path.exists(dll):
        problems.append(f"add-on DLL not found: {dll}")
    for p in problems:
        print("  PROBLEM:", p)
    if problems:
        print("Nothing was changed.")
        return 1
    print("  all inputs found")

    print("3. Build (this takes a few minutes)")
    out_root = tempfile.mkdtemp(prefix="sorasouls_build_")
    mod = os.path.join(out_root, "mod")
    log = os.path.join(out_root, "build_log.txt")
    if not kh2:                                   # the exports OpenKH's model editor would make, done automatically
        kh2 = os.path.join(out_root, "kh2_exports")
        with open(log, "a", encoding="utf-8") as lf:
            r = subprocess.run([sys.executable, os.path.join(HERE, "kh2_export.py"), okh, openkh, kh2], cwd=HERE,
                               stdout=lf, stderr=subprocess.STDOUT)
        if r.returncode:
            print(f"  exporting the KH2 models with OpenKH FAILED – see {log}. Check that OpenKH runs and is version 26.x "
                  "(INSTALL.md steps 3-4).")
            return 1
        print("  KH2 models exported with your OpenKH")
    cmd = [sys.executable, os.path.join(HERE, "rebuild_mod.py"), dsr, mod, "--kh2", kh2, "--openkh", openkh,
           "--recipes", recipes]
    with open(log, "a", encoding="utf-8") as lf:
        r = subprocess.run(cmd, cwd=HERE, stdout=lf, stderr=subprocess.STDOUT)
    if r.returncode:
        print(f"  build FAILED – see {log}")
        return 1
    built = {k: v for k, v in listing(mod).items() if k not in NOT_COMPARED}
    for k in NOT_COMPARED:
        p = os.path.join(mod, k)
        if os.path.exists(p):
            os.remove(p)
    if kh2.startswith(out_root):
        shutil.rmtree(kh2, ignore_errors=True)    # the temporary exports are not needed any more
    print(f"  {len(built)} files built")

    print("4. Compare with the tested build")
    diff = []
    if os.path.exists(EXPECTED):
        exp = json.load(open(EXPECTED, encoding="utf-8"))["files"]
        diff = [k for k in sorted(set(exp) | set(built)) if exp.get(k) != built.get(k)]
        for k in diff:
            print("  differs:" if k in exp and k in built else ("  missing:" if k in exp else "  extra:"), k)
        print(f"  {len(built) - len([k for k in diff if k in built])} of {len(exp)} files identical")
    else:
        print("  no expected_build.json – skipped")
    report = os.path.join(out_root, "build_report.txt")
    with open(report, "w", encoding="utf-8") as f:
        f.write(f"SoraSouls build {datetime.datetime.now():%Y-%m-%d %H:%M}\nDSR: {dsr}\nKH2: {kh2}\nOpenKH: {openkh}\n\n")
        f.writelines(f"{v}  {k}{'  (differs from tested build)' if k in diff else ''}\n" for k, v in sorted(built.items()))
    if diff and "--force" not in flags:
        print(f"Not installed: the build differs from the tested one (report: {report}). Re-run with --force to "
              "install anyway.")
        return 1

    if "--no-install" in flags:
        print(f"Built in {mod} (not installed). Report: {report}")
        return 0
    print("5. Install")
    target = os.path.join(me, "mod")
    if os.path.exists(target):
        backup = target + ".backup-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        os.rename(target, backup)
        print(f"  old mod folder kept as {backup}")
    shutil.copytree(mod, target)
    shutil.copy(dll, os.path.join(target, DLL_NAME))
    shutil.copy(report, os.path.join(target, "build_report.txt"))
    write_config(me, f"mod/{DLL_NAME}")
    shutil.rmtree(out_root, ignore_errors=True)
    print(f"  installed into {target}\nDone. Start the game with launchmod_darksoulsremastered.bat and play offline.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
