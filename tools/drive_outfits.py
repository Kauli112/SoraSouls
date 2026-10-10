"""SoraSouls – Sora's Drive Form outfits (v120, test). User: "change his model so his outfit matches the form he is in
and we can take off the aura".

Finding: the user's OpenKH exports of KH2's form models (P_EX100_BTLF Valor, _MAGF Wisdom, _TRIF Master, _ULTF Final,
_HTLF Anti) have exactly Sora's normal mesh – same vertices, triangles and UVs as P_EX100 (checked: max difference 0).
Only the three textures differ. So each form outfit = Sora's finished parts (mod parts *_9550, all fitting/stretching
fixes included) with that form's textures:
  * parts HD/BD/AM/LG_M/LG_F (+_M) model 9550 -> 9551 Valor, 9552 Wisdom, 9553 Master, 9554 Final, 9555 Anti;
  * textures renamed per form (VALOR_Texture0000 ...; the game caches textures by name, so the normal SORA_ names
    could show the normal outfit) and converted the way Sora's were: sRGB -> linear (Blender's DDS export did that to
    his textures; fitted on the user's files: 2 levels mean error vs 32 without) then DXT5 at the same size;
    per-texture specular maps rebuilt from the new diffuse (sora_specular.spec_from_diffuse);
  * armor rows: copies of Sora's Knight rows 390000-393000 with the form's model: Valor 9580000, Wisdom 9590000,
    Master 9600000, Final 9610000, Anti 9620000 (+1000 body, +2000 arms, +3000 legs).
The swap itself is done by the DLL (sora_glide.c "Drive Form outfits"): events mirror "form k active" into flags
9984+k (drive_forms.py), the DLL writes the form's armor ids over the equipped ones and back.
Usage: python drive_outfits.py <mod parts dir with *_9550> <drive export dir (valor/ wisdom/ ...)> <out parts dir>
"""
import io, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SORA_MODEL, SORA_ARMOR = 9550, 390000
# v122 (user: "Sora looks a bit dark compared to Donald and Goofy"): his v1 textures came out of Blender's DDS export
# converted sRGB -> linear (measured v120), i.e. darker than the KH2 artwork; Donald and Goofy use the artwork as is.
# LINEARIZE False writes the artwork unchanged, and NORMAL rebuilds Sora's own parts *_9550 the same way (textures from
# work/sora/Texture000x.png, the export his model was fitted from), so normal Sora and every form match the party.
LINEARIZE = False
NORMAL = ("normal", "../sora", "P_EX100", SORA_MODEL, SORA_ARMOR, "SORA")
FORMS = [  # key, export folder, fbx stem, model, armor base, texture prefix
    ("valor", "valor", "P_EX100_BTLF", 9551, 9580000, "VALOR"),
    ("wisdom", "wisdom", "P_EX100_MAGF", 9552, 9590000, "WISDOM"),
    ("master", "master", "P_EX100_TRIF", 9553, 9600000, "MASTER"),
    ("final", "final", "P_EX100_ULTF", 9554, 9610000, "FINAL"),
    ("anti", "antiform", "P_EX100_HTLF", 9555, 9620000, "ANTI"),
]
PART_FILES = ["HD_A", "BD_A", "AM_A", "LG_M", "LG_F"]


def srgb_to_linear(rgb):
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def form_dds(png, size, linear=None):
    a = np.asarray(Image.open(png).convert("RGBA").resize(size, Image.LANCZOS)).astype(np.float32) / 255
    if LINEARIZE if linear is None else linear:
        a[..., :3] = srgb_to_linear(a[..., :3])
    buf = io.BytesIO(); Image.fromarray((a * 255 + 0.5).astype(np.uint8), "RGBA").save(buf, "DDS", pixel_format="DXT5")
    return buf.getvalue()


def build_parts(mod_parts, drive_dir, out_dir):
    from soulstruct.containers import Binder
    from soulstruct.containers.tpf import TPF
    from soulstruct.flver import FLVER
    from sora_specular import spec_from_diffuse
    import tempfile, sync_part_variants
    # v123: the "_M" variants and LG_F of Sora's parts never got the later fixes (arms, normals, normal map, specular), so
    # every variant is first rebuilt from the finished plain parts (sync_part_variants.py) and all forms derive from those.
    synced = tempfile.mkdtemp(prefix="sora_sync_")
    sync_part_variants.sync(mod_parts, synced, SORA_MODEL)
    mod_parts = synced
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for key, folder, fbx, model, armor, prefix in [NORMAL] + FORMS:
        for part in PART_FILES:
            for suffix in ("", "_M"):
                src = os.path.join(mod_parts, f"{part}_{SORA_MODEL}{suffix}.partsbnd.dcx")
                b = Binder.from_path(src)
                old, new = f"{part}_{SORA_MODEL}", f"{part}_{model}"
                for e in b.entries:
                    if e.path.endswith(".tpf"):
                        tpf = TPF.from_bytes(e.data)
                        diffuse = {}
                        for t in tpf.textures:
                            if t.stem.startswith("SORA_Texture") and not t.stem.endswith("_s"):
                                n = t.stem[len("SORA_"):]                      # Texture0000
                                size = Image.open(io.BytesIO(t.data)).size
                                png = os.path.join(drive_dir, folder, n + ".png")
                                t.data, t.format = form_dds(png, size), 5
                                # specular mask from the linear (darker) version: sora_specular's thresholds were tuned
                                # on those values, so the shiny parts stay exactly what they were
                                diffuse[t.stem] = form_dds(png, size, linear=True)
                        for t in tpf.textures:
                            if t.stem.endswith("_s") and t.stem[:-2] in diffuse:
                                sz = Image.open(io.BytesIO(t.data)).size
                                s = spec_from_diffuse(diffuse[t.stem[:-2]])[0]
                                if Image.open(io.BytesIO(s)).size != sz:
                                    raise RuntimeError(f"{src}: specular size mismatch {t.stem}")
                                t.data = s
                        for t in tpf.textures:
                            t.stem = t.stem.replace("SORA_", prefix + "_")
                        e.set_from_binary_file(tpf)
                    elif e.path.endswith(".flver"):
                        f = FLVER.from_bytes(e.data)
                        for m in f.meshes:
                            for tx in m.material.textures:
                                tx.path = tx.path.replace("SORA_", prefix + "_")
                            m.material.name = m.material.name.replace("SORA_", prefix + "_")
                        for bone in f.bones:
                            bone.name = bone.name.replace(old, new)
                        e.data = f.to_bytes()
                for e in b.entries:
                    e.path = e.path.replace(old, new)
                out = os.path.join(out_dir, f"{new}{suffix}.partsbnd.dcx")
                b.write(out)
                written.append(out)
        print(f"{key}: model {model}, {len(PART_FILES) * 2} parts, textures {prefix}_Texture0000-0002")
    return written


# v126 (user: "When humanity is lost on death sora should look like roxas"): Roxas's parts (model 9556, tools/
# roxas_model.py) as one more outfit, armor rows 9630000 (+1000 body, +2000 arms, +3000 legs). Event ROXAS_EVENT mirrors
# "the player is Hollow" into ROXAS_FLAG; the DLL swaps the armor ids like a Drive Form (forms win while active).
ROXAS_MODEL, ROXAS_ARMOR, ROXAS_FLAG, ROXAS_EVENT = 9556, 9630000, 9991, 9918


def build_params(gp, get_param, copy_row):
    pr = get_param(gp, "EquipParamProtector")
    for key, folder, fbx, model, armor, prefix in FORMS + [("roxas", None, None, ROXAS_MODEL, ROXAS_ARMOR, "ROXAS")]:
        for k in range(4):
            r = copy_row(pr, SORA_ARMOR + 1000 * k, armor + 1000 * k, f"SoraSouls {key} outfit {k}")
            r.EquipmentModel = model


def roxas_evs():
    return f"    Event_{ROXAS_EVENT}()\n", f'''

@ContinueOnRest({ROXAS_EVENT})
def Event_{ROXAS_EVENT}():
    """SoraSouls: flag {ROXAS_FLAG} on while the player is Hollow (Sora then looks like Roxas – DLL outfit swap)."""
    if CharacterIsHollow(PLAYER):
        EnableFlag({ROXAS_FLAG})
    else:
        DisableFlag({ROXAS_FLAG})
    Wait(1.0)
    return RESTART
'''


if __name__ == "__main__":
    build_parts(sys.argv[1], sys.argv[2], sys.argv[3])
