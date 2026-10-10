"""SoraSouls – one-click converter: build the mod from the player's own Dark Souls Remastered and KH2 files and
install it into Mod Engine 2 (v124).

Steps:
  1. Find the folders: DSR (from Steam's library list), Mod Engine 2, the KH2 export folder, the OpenKH data/kh2
     folder. Answers are remembered in sorasouls_settings.json next to the package; flags override them.
  2. Check them: DSR exe version (image size the DLL was built against), every KH2 file the build reads, Mod Engine 2.
  3. Build into a temporary folder with rebuild_mod.py (the game folder is only read).
  4. Compare every built file with the SHA-256 list of the tested build (data/expected_build.json – checksums only,
     no content). Differences are listed; installing then needs --force (a different export can give a different
     model).
  5. Install: the current Mod Engine 2 mod folder is moved to mod.backup-<time>, the new one copied in with the
     add-on DLL, and config_darksoulsremastered.toml pointed at it. build_report.txt lists every file + checksum.

  python build_sorasouls.py [--dsr DIR] [--modengine DIR] [--kh2 DIR] [--openkh DIR] [--recipes DIR] [--dll FILE]
                            [--force] [--no-install] [--yes]
  python build_sorasouls.py --write-expected <reference mod dir>     (developer: record the tested build)
"""
import datetime, hashlib, json, os, re, shutil, struct, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SETTINGS = os.path.join(ROOT, "sorasouls_settings.json")
EXPECTED = os.path.join(ROOT, "data", "expected_build.json")
DSR_IMAGE_SIZE = 0x319B000          # DarkSoulsRemastered.exe the DLL's offsets were measured on
DLL_NAME = "sora_glide_v77.dll"
FORMS = ("valor", "wisdom", "master", "final", "antiform")
KEYBLADE_FBX = ("W_EX010", "W_EX010_30", "W_EX010_40", "W_EX010_M0", "W_EX010_10", "W_EX010_20", "W_EX010_N0")
ITEMPIC = (43, 44, 45, 46, 47, 63, 64, 344)
# files that differ from the tested build by design or are not built here
NOT_COMPARED = {"event/common.emevd.dcx.evs.py"}


def kh2_required(kh2, openkh):
    t = [f"Texture000{i}.png" for i in range(3)]
    need = [os.path.join(kh2, "sora", "P_EX100.fbx")] + [os.path.join(kh2, "sora", x) for x in t]
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
            json.dump(dict(build="v124", files=data), f, indent=1, sort_keys=True)
        print(f"wrote {EXPECTED}: {len(data)} files")
        return 0

    interactive = sys.stdin.isatty() and "--yes" not in flags
    saved = json.load(open(SETTINGS, encoding="utf-8")) if os.path.exists(SETTINGS) else {}
    print("SoraSouls converter\n1. Folders")
    dsr = ask("Dark Souls Remastered", opts.get("--dsr") or saved.get("dsr") or steam_dsr(),
              lambda p: os.path.exists(os.path.join(p, "DarkSoulsRemastered.exe")), interactive)
    me = ask("Mod Engine 2 (the folder with launchmod_darksoulsremastered.bat)",
             opts.get("--modengine") or saved.get("modengine"),
             lambda p: os.path.exists(os.path.join(p, "config_darksoulsremastered.toml")), interactive)
    kh2 = ask("KH2 exports (sora/ drive/ donald/ goofy/ keyblade/)", opts.get("--kh2") or saved.get("kh2"),
              lambda p: os.path.isdir(os.path.join(p, "sora")), interactive)
    openkh = ask("OpenKH data\\kh2", opts.get("--openkh") or saved.get("openkh"),
                 lambda p: os.path.isdir(os.path.join(p, "obj")), interactive)
    recipes = opts.get("--recipes") or saved.get("recipes") or os.path.join(ROOT, "data", "recipes")
    dll = opts.get("--dll") or saved.get("dll") or os.path.join(ROOT, "bin", DLL_NAME)
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(dict(dsr=dsr, modengine=me, kh2=kh2, openkh=openkh, recipes=recipes, dll=dll), f, indent=1)

    print("2. Checks")
    problems = []
    size = pe_image_size(os.path.join(dsr, "DarkSoulsRemastered.exe"))
    if size != DSR_IMAGE_SIZE:
        problems.append(f"DarkSoulsRemastered.exe has image size {size:#x}, SoraSouls was made for {DSR_IMAGE_SIZE:#x}"
                        " (different game version – the add-on DLL may not work)")
    missing = [p for p in kh2_required(kh2, openkh) if not os.path.exists(p)]
    problems += [f"missing KH2 file: {p}" for p in missing]
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
    cmd = [sys.executable, os.path.join(HERE, "rebuild_mod.py"), dsr, mod, "--kh2", kh2, "--openkh", openkh,
           "--recipes", recipes]
    log = os.path.join(out_root, "build_log.txt")
    with open(log, "w", encoding="utf-8") as lf:
        r = subprocess.run(cmd, cwd=HERE, stdout=lf, stderr=subprocess.STDOUT)
    if r.returncode:
        print(f"  build FAILED – see {log}")
        return 1
    built = {k: v for k, v in listing(mod).items() if k not in NOT_COMPARED}
    for k in NOT_COMPARED:
        p = os.path.join(mod, k)
        if os.path.exists(p):
            os.remove(p)
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
