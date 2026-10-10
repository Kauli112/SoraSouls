r"""SoraSouls – assemble the tester package: a folder + zip that runs build_sorasouls.bat with its own Python (v124).

Contents (all original or redistributable – no file from KH2 or DSR, nothing made from them):
  build_sorasouls.bat, README.md, PLAYTEST.md, THIRD_PARTY.txt
  tools\*.py                  our Python tools
  data\expected_build.json    SHA-256 checksums of the tested build (no content), data\bone_map_sora.json
  bin\sora_glide_v79.dll      our add-on DLL
  python\                     the official embeddable CPython (python.org, signed by the PSF) + the libraries from
                              the project environment (.venv): soulstruct, soulstruct-havok, numpy, scipy, Pillow,
                              matplotlib, scikit-image and their dependencies
  data\recipes\               model recipes (tools\model_recipe.py): no usable KH2/DSR geometry, see CONVERTER_PLAN.md

  python make_package.py <embeddable python folder> <out folder>   -> <out>\SoraSouls\ + <out>\SoraSouls-v124.zip
"""
import glob, os, shutil, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VERSION = "v124"
DLL = "sora_glide_v79.dll"
SKIP_PACKAGES = ("pip",)


def _license(meta_dir):
    name = version = lic = "?"
    p = os.path.join(meta_dir, "METADATA")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            if line.startswith("Name:"):
                name = line[5:].strip()
            elif line.startswith("Version:"):
                version = line[8:].strip()
            elif line.startswith("License-Expression:") or (line.startswith("License:") and lic == "?"):
                lic = line.split(":", 1)[1].strip()[:80] or "?"
            elif line.strip() == "":
                break
    return name, version, lic


def build(embed_dir, out):
    pkg = os.path.join(out, "SoraSouls")
    if os.path.exists(pkg):
        shutil.rmtree(pkg)
    os.makedirs(os.path.join(pkg, "tools"))
    for f in ("build_sorasouls.bat", "INSTALL.md", "README.md", "PLAYTEST.md", "LICENSE"):
        shutil.copy(os.path.join(ROOT, f), pkg)
    for f in glob.glob(os.path.join(HERE, "*.py")):
        shutil.copy(f, os.path.join(pkg, "tools"))
    os.makedirs(os.path.join(pkg, "data"))
    for f in ("expected_build.json", "bone_map_sora.json"):
        shutil.copy(os.path.join(ROOT, "data", f), os.path.join(pkg, "data"))
    shutil.copytree(os.path.join(ROOT, "data", "recipes"), os.path.join(pkg, "data", "recipes"))
    os.makedirs(os.path.join(pkg, "bin"))
    shutil.copy(os.path.join(ROOT, "bin", DLL), os.path.join(pkg, "bin"))

    py = os.path.join(pkg, "python")
    shutil.copytree(embed_dir, py)
    pth = next(glob.glob(os.path.join(py, "python3*._pth")).__iter__())
    zipname = os.path.basename(pth).replace("._pth", ".zip")
    with open(pth, "w", encoding="ascii") as f:
        f.write(f"{zipname}\n.\nLib\\site-packages\n..\\tools\nimport site\n")   # ._pth: no script dir on sys.path
    site = os.path.join(ROOT, ".venv", "Lib", "site-packages")
    dest = os.path.join(py, "Lib", "site-packages")
    third = []
    for name in sorted(os.listdir(site)):
        if name.lower().startswith(SKIP_PACKAGES) or name == "__pycache__":
            continue
        src = os.path.join(site, name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dest, name), ignore=shutil.ignore_patterns("__pycache__"))
            if name.endswith(".dist-info"):
                third.append(_license(src))
        else:
            os.makedirs(dest, exist_ok=True)
            shutil.copy(src, dest)
    with open(os.path.join(pkg, "THIRD_PARTY.txt"), "w", encoding="utf-8") as f:
        f.write("Third-party software bundled in python\\ (each under its own licence, see its .dist-info folder):\n\n")
        f.write("Python (embeddable CPython from python.org)  PSF-2.0\n")
        f.writelines(f"{n} {v}  {l}\n" for n, v, l in third)
    z = os.path.join(out, f"SoraSouls-{VERSION}.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(pkg):
            for fn in files:
                p = os.path.join(root, fn)
                zf.write(p, os.path.relpath(p, out))
    print(f"package: {pkg}\nzip: {z} ({os.path.getsize(z) / 1e6:.1f} MB)")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
