"""SoraSouls – shiny metal for Sora's chain, crown, buckles and zippers (v60). User 2026-10-07: "his necklace is kinda
dull for metal".

Finding: every Sora material (MTD P_Leather[DSB]) samples ONE shared specular map, SORA_s – a 64x64 DXT1 that is pure
black, so nothing on Sora reflects light. A shared map also cannot single out metal, because the parts use three
different diffuse textures (SORA_Texture0000/0001/0002) with different layouts.
Fix: each diffuse texture gets its own specular map <diffuse>_s at the same resolution/UV layout, and each material's
g_Specular slot points to the one matching its diffuse. Specular = METAL where a texel is grey and bright (silver:
saturation < METAL_SAT and value > METAL_VAL – chain, crown pendant, buckles, zipper pulls), a faint BASE sheen
elsewhere. The old SORA_s stays in the TPF (unused). Mesh data is untouched.
Usage: python sora_specular.py <parts dir (input)> <out parts dir>
"""
import copy, io, os, sys
import numpy as np
from PIL import Image
from soulstruct.containers import Binder
from soulstruct.containers.tpf import TPF
from soulstruct.flver import FLVER

PARTS = ("HD_A_9550", "BD_A_9550", "AM_A_9550", "LG_M_9550", "LG_F_9550")
METAL_SAT, METAL_VAL = 0.18, 0.32   # v0.45 missed most chain links (darker grey)
METAL, BASE = 190, 0   # v61: BASE 12 made all clothes and hair look shiny in-game


def spec_from_diffuse(dds_bytes):
    rgb = np.asarray(Image.open(io.BytesIO(dds_bytes)).convert("RGB")).astype(np.float32) / 255.0
    mx, mn = rgb.max(2), rgb.min(2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    metal = (sat < METAL_SAT) & (mx > METAL_VAL)
    out = np.where(metal[..., None], METAL, BASE).astype(np.uint8).repeat(3, axis=2)
    buf = io.BytesIO()
    Image.fromarray(out, "RGB").save(buf, "DDS", pixel_format="DXT1")
    return buf.getvalue(), float(metal.mean())


def main(src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for part in PARTS:
        for name in (f"{part}.partsbnd.dcx", f"{part}_M.partsbnd.dcx"):
            path = os.path.join(src_dir, name)
            if not os.path.exists(path):
                continue
            b = Binder.from_path(path)
            te = next(e for e in b.entries if e.name.lower().endswith(".tpf"))
            fe = next(e for e in b.entries if e.name.lower().endswith(".flver"))
            tpf, f = TPF.from_bytes(te.data), FLVER.from_bytes(fe.data)
            by_stem = {t.stem: t for t in tpf.textures}
            made = {}
            for m in f.meshes:
                texs = m.material.textures
                diff = next(t for t in texs if t.texture_type == "g_Diffuse")
                spec = next(t for t in texs if t.texture_type == "g_Specular")
                dstem = os.path.splitext(os.path.basename(diff.path))[0]
                sstem = f"{dstem}_s"
                if sstem not in by_stem:
                    new = copy.deepcopy(by_stem["SORA_s"])
                    new.stem = sstem
                    new.data, frac = spec_from_diffuse(bytes(by_stem[dstem].data))
                    new.format = 0
                    tpf.textures.append(new)
                    by_stem[sstem] = new
                    made[sstem] = round(frac, 3)
                spec.path = spec.path.replace("SORA_s", sstem)
            te.set_from_binary_file(tpf)
            fe.data = f.to_bytes()
            b.write(os.path.join(out_dir, name))
            print(f"{name}: specular maps {made} (fraction of texels = metal)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
