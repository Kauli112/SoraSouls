"""SoraSouls – make every variant of a character's armor parts identical to the finished one (v123).
User (v122 in game): "Sora texture colour looks uneven".

Finding (audit of the deployed v122 parts, 2026-10-10): the later fixes (reskin_sora_head, fit_sora_arms,
smooth_sora_normals, fix_sora_normalmap, sora_specular, fix_seam_normals) are present only in the plain files
HD_A / BD_A / AM_A / LG_M; the other copies still hold older data.
Two sets of files are affected:
  * the "_M" variants of Sora and of every form outfit (9550-9555): arms not fitted (AM_A_9550_M differs from AM_A_9550 by
    up to 1.7 m), neck seam differs by 6 cm, normals not smoothed or repaired (BD_M 3 and LG_M_M 8 zero-length normals),
    the normal map SORA_n still pure black (R = 0: every surface lit as if bent to one side) and the shared black specular
    map instead of the per-texture ones;
  * LG_F (the legs a female character wears), plain and "_M": same flaws (8 zero normals, black normal map, no specular).
Donald and Goofy (9560, 9570) were already consistent (kh_party_model writes all variants itself).
A vanilla "_M" binder is byte-identical to its plain binder except that the FLVER entry is named <stem>_M.flver
(tools/finalize_parts.py), and Sora's LG_F has exactly the geometry of LG_M (checked: max position difference 0), so:
  <part>_<model>_M  = <part>_<model> with the FLVER entry renamed,
  LG_F_<model>[_M]  = LG_M_<model>[_M] with every entry path renamed LG_M_ -> LG_F_.
Nothing else changes. Usage: python sync_part_variants.py <parts dir (input)> <out parts dir> [model ...]  (default 9550)
"""
import os, sys
from soulstruct.containers import Binder

PLAIN = ("HD_A", "BD_A", "AM_A", "LG_M")


def _rename_flver(b):
    fe = next(e for e in b.entries if e.path.endswith(".flver"))
    if not fe.path.endswith("_M.flver"):
        fe.path = fe.path[: -len(".flver")] + "_M.flver"


def sync(src_dir, out_dir, model):
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for part in PLAIN:
        src = os.path.join(src_dir, f"{part}_{model}.partsbnd.dcx")
        b = Binder.from_path(src)
        out = os.path.join(out_dir, f"{part}_{model}.partsbnd.dcx")
        b.write(out); written.append(out)
        m = Binder.from_path(src)
        _rename_flver(m)
        out = os.path.join(out_dir, f"{part}_{model}_M.partsbnd.dcx")
        m.write(out); written.append(out)
        if part == "LG_M":
            for suffix in ("", "_M"):
                f = Binder.from_path(os.path.join(out_dir, f"LG_M_{model}{suffix}.partsbnd.dcx"))
                for e in f.entries:
                    e.path = e.path.replace(f"LG_M_{model}", f"LG_F_{model}")
                out = os.path.join(out_dir, f"LG_F_{model}{suffix}.partsbnd.dcx")
                f.write(out); written.append(out)
    return written


if __name__ == "__main__":
    for mdl in (sys.argv[3:] or ["9550"]):
        w = sync(sys.argv[1], sys.argv[2], int(mdl))
        print(f"model {mdl}: {len(w)} files written")
