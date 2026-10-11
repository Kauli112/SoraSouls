r"""SoraSouls – move a finished set of armor parts to another model id (v128).

Playtest 2026-10-11: "Havel is showing Goofy in game". Donald (9560) and Goofy (9570) were built on armor model ids
that vanilla Dark Souls already uses: 9570 is Havel's set (EquipParamProtector 440000-443000) and 9560 is another
vanilla set (420000-423000), so every character wearing those sets looked like Goofy / Donald. Their parts now get
model ids no vanilla file or param row uses (9557 / 9558, checked against DSR's parts folder and EquipParamProtector).
The recipes keep their old names; this step renames the built files and the paths inside them (textures already
have unique names: DONALD_ / GOOFY_).

  python rename_parts_model.py <parts dir> <old model> <new model>
"""
import os, re, sys
from soulstruct.containers import Binder


def rename(parts, old, new):
    done = 0
    for f in sorted(os.listdir(parts)):
        m = re.fullmatch(rf"((?:HD|BD|AM|LG)_[AMF])_{old}(_M)?\.partsbnd\.dcx", f)
        if not m:
            continue
        b = Binder.from_path(os.path.join(parts, f))
        for e in b.entries:
            e.path = e.path.replace(f"{m.group(1)}_{old}", f"{m.group(1)}_{new}")
        b.write(os.path.join(parts, f"{m.group(1)}_{new}{m.group(2) or ''}.partsbnd.dcx"))
        os.remove(os.path.join(parts, f))
        done += 1
    if not done:
        raise RuntimeError(f"no parts of model {old} in {parts}")
    print(f"model {old} -> {new}: {done} files")


if __name__ == "__main__":
    rename(sys.argv[1], sys.argv[2], sys.argv[3])
