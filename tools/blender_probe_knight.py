"""SoraSouls – Step 2b probe: learn how the Soulstruct add-on represents DSR armor before we swap in Sora.

Imports the Knight armor set parts (the Knight class starts wearing them) with Soulstruct, writes a report of
objects / bones / materials / texture slots, and round-trips the body piece through the Equipment exporter into a
SCRATCH folder (work/export_test) – never into the mod folder or the game folder.

Run with tools/run_probe_knight.bat. Output: work/knight_probe_report.txt
"""
import bpy, addon_utils, os, sys, traceback

ROOT = os.environ.get("SORASOULS_ROOT", "E:/SoraSouls")
DSR = "D:/SteamLibrary/steamapps/common/DARK SOULS REMASTERED"
SCRATCH = os.path.join(ROOT, "work/export_test")
PARTS = ["HD_A_9550.partsbnd.dcx", "BD_A_9550.partsbnd.dcx", "AM_A_9550.partsbnd.dcx", "LG_M_9550.partsbnd.dcx"]
report = []

def log(msg):
    print("[probe]", msg); report.append(str(msg))

def save():
    open(os.path.join(ROOT, "work/knight_probe_report.txt"), "w", encoding="utf-8").write("\n".join(report))

try:
    mod = addon_utils.enable("bl_ext.user_default.io_soulstruct", default_set=True)
    log(f"addon enabled: {mod is not None}")
    os.makedirs(SCRATCH, exist_ok=True)

    s = bpy.context.scene.soulstruct_settings
    s.game_enum = "DARK_SOULS_DSR"
    s.darksouls1r.game_root_str = DSR
    s.darksouls1r.project_root_str = SCRATCH
    s.prefer_import_from_project = False
    s.also_export_to_game = False
    log(f"settings: game={s.game_enum} root={s.game_root_path} project={s.project_root_path} "
        f"can_auto_export={s.can_auto_export}")

    for name in PARTS:
        before = set(bpy.data.objects)
        r = bpy.ops.import_scene.equipment_flver(directory=os.path.join(DSR, "parts") + "/", files=[{"name": name}])
        new = [o for o in bpy.data.objects if o not in before]
        log(f"\n=== import {name}: {r} -> {[(o.name, o.type) for o in new]}")
        for o in new:
            if o.type == "ARMATURE":
                bones = [b.name for b in o.data.bones]
                log(f"  armature {o.name}: {len(bones)} bones: {bones}")
            elif o.type == "MESH":
                log(f"  mesh {o.name}: {len(o.data.vertices)} verts, groups={[g.name for g in o.vertex_groups]}")
                log(f"  mesh custom props: {dict((k, str(v)[:80]) for k, v in o.items())}")
                log(f"  modifiers: {[(m.name, m.type, getattr(m, 'object', None) and m.object.name) for m in o.modifiers]}")
                log(f"  uv layers: {[u.name for u in o.data.uv_layers]} | color attrs: {[c.name for c in o.data.color_attributes]}")
                for slot in o.material_slots:
                    m = slot.material
                    if not m: continue
                    props = {k: str(v)[:100] for k, v in m.items()}
                    log(f"  material {m.name}: props={props}")
                    try:
                        log(f"    flver_material: {dict((k, str(getattr(m.FLVER_MATERIAL, k))[:100]) for k in m.FLVER_MATERIAL.bl_rna.properties.keys() if k != 'rna_type')}")
                    except Exception as ex:
                        log(f"    (no FLVER_MATERIAL props: {ex})")
                    for n in m.node_tree.nodes:
                        if n.type == "TEX_IMAGE":
                            img = n.image
                            log(f"    tex node name={n.name!r} label={n.label!r} image={img.name if img else None} "
                                f"size={tuple(img.size) if img else None} colorspace={img.colorspace_settings.name if img else None}")
            else:
                log(f"  other {o.name} ({o.type}) parent={o.parent.name if o.parent else None}")

    # Round-trip export of the unmodified body into the scratch project folder.
    body = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("BD_A_9550"))
    for o in bpy.context.selected_objects: o.select_set(False)
    body.select_set(True); bpy.context.view_layer.objects.active = body
    r = bpy.ops.export_scene.equipment_flver()
    log(f"\n=== export BD_A_9550 round-trip: {r}")
    for dp, _, fs in os.walk(SCRATCH):
        for f in fs:
            p = os.path.join(dp, f); log(f"  wrote {os.path.relpath(p, SCRATCH)} ({os.path.getsize(p)} bytes)")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "work/knight_probe.blend"))
    log("saved work/knight_probe.blend")
except Exception:
    log("ERROR:\n" + traceback.format_exc())
finally:
    save()
