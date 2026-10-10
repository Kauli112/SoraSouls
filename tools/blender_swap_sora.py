"""SoraSouls – Step 2c: swap Sora into the Knight armor set (model 9550) and export DSR PARTSBNDs.

Pipeline:
  1. Import Knight parts HD_A / BD_A / AM_A / LG_M / LG_F (9550) with Soulstruct (correct armature + FLVER materials).
  2. Append Sora's fitted meshes from work/sora/sora_dsr_fit_v3.blend (DSR bone vertex groups, DSR space).
  3. Build Sora FLVER materials: copies of a Knight material (same MTD/shader) with Sora's diffuse texture,
     flat specular and flat normal maps.
  4. Split Sora by bone into head / body / arms / legs and replace each Knight part's geometry.
  5. Export each part with Soulstruct's Equipment exporter into a STAGING folder: work/export_sora/parts/.
     Nothing is written to the game folder or the mod folder by this script.
Run with tools/run_swap_sora.bat. Report: work/swap_report.txt
"""

# --- multiprocessing guard -------------------------------------------------------------------
# Soulstruct converts textures with multiprocessing.Pool. On Windows each worker re-runs the main
# script; v3 imported bpy at module level, so every worker crashed and the pool respawned them
# forever (log grew to 7 MB, Blender never finished). Now: nothing runs unless this is the real
# main script, and __main__.__file__ is hidden so workers don't re-run us at all.
import sys

def main():
    import bpy, bmesh, addon_utils, os, shutil, traceback, math

    ROOT = os.environ.get("SORASOULS_ROOT", "E:/SoraSouls")
    DSR = "D:/SteamLibrary/steamapps/common/DARK SOULS REMASTERED"
    FIT_BLEND = os.path.join(ROOT, "work/sora/sora_dsr_fit_v3.blend")
    STAGING = os.path.join(ROOT, "work/export_sora")
    KNIGHT = {"HD": "HD_A_9550", "BD": "BD_A_9550", "AM": "AM_A_9550", "LG_M": "LG_M_9550", "LG_F": "LG_F_9550"}
    PIECE_OF_BONE = {}  # DSR bone -> piece
    for b in ("Head", "Neck"):
        PIECE_OF_BONE[b] = "HD"
    for side in ("L_", "R_"):
        PIECE_OF_BONE[side + "UpperArm"] = "BD"  # Knight AM has no usable L_UpperArm; BD rigs both upper arms
        for b in ("Forearm", "Hand", "Finger0", "Finger01", "Finger02", "Finger1", "Finger11",
                  "Finger12", "Finger2", "Finger21", "Finger22"):
            PIECE_OF_BONE[side + b] = "AM"
        for b in ("Thigh", "Calf", "Foot", "Toe0"):
            PIECE_OF_BONE[side + b] = "LG"
    # everything else (Pelvis, Spine, Spine1, Clavicles) -> BD
    TEMPLATE_MTD_PREFERENCE = ("P_Leather[DSB].mtd", "P_DullLeather[DSB].mtd", "P_Metal[DSB].mtd")
    report = []

    def log(msg):
        print("[swap]", msg); report.append(str(msg))

    def save_report():
        open(os.path.join(ROOT, "work/swap_report.txt"), "w", encoding="utf-8").write("\n".join(report))

    def select_only(obj):
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

    def flat_image(name, rgba, size=64):
        img = bpy.data.images.new(name, size, size, alpha=True)
        img.pixels = list(rgba) * (size * size)
        img.colorspace_settings.name = "Non-Color"
        img.pack()
        img.DDS_TEXTURE.dds_format = "DXT1"  # v2 failed: default 'SAME' needs an existing texture to copy from
        return img

    try:
        addon_utils.enable("bl_ext.user_default.io_soulstruct", default_set=True)
        if os.path.isdir(STAGING):
            shutil.rmtree(STAGING)  # staging only – always start clean
        os.makedirs(STAGING)
        s = bpy.context.scene.soulstruct_settings
        s.game_enum = "DARK_SOULS_DSR"
        s.darksouls1r.game_root_str = DSR
        s.darksouls1r.project_root_str = STAGING
        s.prefer_import_from_project = False
        s.also_export_to_game = False
        bpy.context.scene.flver_export_settings.export_textures = True
        log(f"export target (staging): {s.project_root_path} | can_auto_export={s.can_auto_export}")

        # --- 1. Knight parts -------------------------------------------------------------------------
        knight = {}
        for key, stem in KNIGHT.items():
            before = set(bpy.data.objects)
            bpy.ops.import_scene.equipment_flver(directory=os.path.join(DSR, "parts") + "/",
                                                 files=[{"name": stem + ".partsbnd.dcx"}])
            new = [o for o in bpy.data.objects if o not in before]
            mesh = next(o for o in new if o.type == "MESH")
            arm = next(o for o in new if o.type == "ARMATURE")
            knight[key] = (mesh, arm)
            log(f"imported {stem}: mesh {mesh.name} ({len(mesh.data.vertices)} verts), armature {len(arm.data.bones)} bones")

        # Bones each Knight part actually skins to ("native"). Unused bones in a part FLVER are parentless
        # leftovers; in-game test v1 showed vertices on them collapse to the floor (bars from R shoulder
        # and L arm: AM used R_Clavicle / L_UpperArm, which the Knight gauntlets never use).
        native = {}
        for key, (mesh, _) in knight.items():
            gn = {g.index: g.name for g in mesh.vertex_groups}
            native[key] = {gn[g.group] for v in mesh.data.vertices for g in v.groups if g.weight > 0}
            log(f"native bones {key}: {sorted(native[key])}")
        native["LG"] = native["LG_M"] & native["LG_F"]

        # Skeleton agreement check: Knight armature vs the c0000 skeleton Sora was fitted to.
        bd_arm = knight["BD"][1]
        for b in ("L_Hand", "Head", "L_Foot"):
            if b in bd_arm.data.bones:
                h = bd_arm.matrix_world @ bd_arm.data.bones[b].head_local
                log(f"Knight armature {b} head (Blender): {tuple(round(x, 3) for x in h)}")

        # --- 2. Sora meshes ------------------------------------------------------------------------
        with bpy.data.libraries.load(FIT_BLEND, link=False) as (src, dst):
            dst.objects = [n for n in src.objects if n.startswith("MeshNode")]
        sora_parts = []
        for o in dst.objects:
            bpy.context.scene.collection.objects.link(o)
            o.parent = None
            for m in list(o.modifiers):
                o.modifiers.remove(m)
            sora_parts.append(o)
        select_only(sora_parts[0])
        for o in sora_parts:
            o.select_set(True)
        bpy.ops.object.join()
        sora = bpy.context.view_layer.objects.active
        sora.name = "SORA_ALL"
        log(f"Sora joined: {len(sora.data.vertices)} verts, {len(sora.data.polygons)} faces, "
            f"{len(sora.material_slots)} material slots, groups={len(sora.vertex_groups)}")

        # --- 3. FLVER materials ------------------------------------------------------------------
        template = None
        for pref in TEMPLATE_MTD_PREFERENCE:
            for slot in knight["BD"][0].material_slots:
                m = slot.material
                if m and m.FLVER_MATERIAL.mat_def_path.endswith("\\" + pref):
                    template = m; break
            if template: break
        log(f"template material: {template.name} ({template.FLVER_MATERIAL.mat_def_path})")
        spec = flat_image("SORA_s", (0.08, 0.08, 0.08, 1.0))
        norm = flat_image("SORA_n", (0.5, 0.5, 1.0, 1.0))
        sora_mats = {}  # FBX material name -> FLVER material
        for slot in sora.material_slots:
            fbx_mat = slot.material
            img = next((n.image for n in fbx_mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image), None) \
                if fbx_mat and fbx_mat.node_tree else None
            if img is None:
                raise RuntimeError(f"Sora material {fbx_mat.name if fbx_mat else None} has no texture image")
            tex_name = "SORA_" + os.path.splitext(os.path.basename(img.filepath))[0]  # e.g. SORA_Texture0000
            img.name = tex_name
            img.pack()
            img.DDS_TEXTURE.dds_format = "DXT5"  # keeps KH2 alpha (Texture0000/0002 have ~3-4% transparent texels)
            m = template.copy()
            m.name = f"{tex_name}_{len(sora_mats)}"
            nodes = {n.name: n for n in m.node_tree.nodes if n.type == "TEX_IMAGE"}
            nodes["g_Diffuse"].image = img
            nodes["g_Specular"].image = spec
            nodes["g_Bumpmap"].image = norm
            sora_mats[fbx_mat.name] = m
            slot.material = m
            log(f"material {m.name}: diffuse={img.name} {tuple(img.size)}")

        # UV + vertex colour layout must match the Knight meshes.
        k_mesh = knight["BD"][0].data
        uv_name = k_mesh.uv_layers[0].name
        if sora.data.uv_layers:
            sora.data.uv_layers[0].name = uv_name
        kc = k_mesh.color_attributes[0]
        sc = sora.data.color_attributes.new(kc.name, kc.data_type, kc.domain)
        for d in sc.data:
            d.color = (1.0, 1.0, 1.0, 1.0)
        log(f"Sora layers: uv={[u.name for u in sora.data.uv_layers]} colors={kc.name} ({kc.data_type}/{kc.domain}) = white")

        # --- 4. split by bone and replace Knight geometry -----------------------------------------
        gname = {g.index: g.name for g in sora.vertex_groups}
        vert_bone = []
        for v in sora.data.vertices:
            g = max(v.groups, key=lambda x: x.weight)
            vert_bone.append(gname[g.group])
        face_piece = []
        moved, unresolved = 0, []
        for poly in sora.data.polygons:
            bones = {vert_bone[i] for i in poly.vertices}
            votes = [PIECE_OF_BONE.get(vert_bone[i], "BD") for i in poly.vertices]
            preferred = max(set(votes), key=votes.count)
            choice = next((p for p in [preferred, "BD", "HD", "AM", "LG"] if bones <= native[p]), None)
            if choice is None:
                unresolved.append(sorted(bones)); choice = preferred
            elif choice != preferred:
                moved += 1
            face_piece.append(choice)
        log(f"face assignment: {len(face_piece)} faces, {moved} moved to a part that rigs all their bones, "
            f"{len(unresolved)} unresolved {unresolved[:5]}")
        if unresolved:
            raise RuntimeError("faces use bones no Knight part supports – see report")

        targets = {"HD": ["HD"], "BD": ["BD"], "AM": ["AM"], "LG": ["LG_M", "LG_F"]}
        for piece, keys in targets.items():
            for key in keys:
                k_obj, k_arm = knight[key]
                part = sora.copy(); part.data = sora.data.copy(); part.name = f"SORA_{key}"
                bpy.context.scene.collection.objects.link(part)
                bm = bmesh.new(); bm.from_mesh(part.data)
                drop = []
                for f in bm.faces:
                    if face_piece[f.index] != piece:
                        drop.append(f)
                bmesh.ops.delete(bm, geom=drop, context="FACES")
                loose = [v for v in bm.verts if not v.link_faces]
                bmesh.ops.delete(bm, geom=loose, context="VERTS")
                bm.to_mesh(part.data); bm.free()
                # empty the Knight mesh, keep its object (Soulstruct type data, armature modifier, parent).
                # v1 bug: data.materials.clear() left an empty slot behind -> remove slots via the operator instead.
                bm = bmesh.new(); bm.to_mesh(k_obj.data); bm.free()
                select_only(k_obj)
                while k_obj.material_slots:
                    k_obj.active_material_index = 0
                    bpy.ops.object.material_slot_remove()
                part.matrix_world = k_obj.matrix_world.copy()  # both should be identity
                part.select_set(True)
                bpy.ops.object.join()
                bpy.ops.object.material_slot_remove_unused()
                empty = [i for i, sl in enumerate(k_obj.material_slots) if sl.material is None]
                if empty:
                    raise RuntimeError(f"{k_obj.name}: empty material slots {empty} after join")
                log(f"{k_obj.name}: now {len(k_obj.data.vertices)} verts / {len(k_obj.data.polygons)} faces, "
                    f"materials={[m.name for m in k_obj.data.materials]}")
        bpy.data.objects.remove(sora, do_unlink=True)

        # --- 5. export into staging ---------------------------------------------------------------
        # Soulstruct's batch_texconv_to_dds uses multiprocessing.Pool; its worker processes cannot import the
        # add-on package (bl_ext.*) outside Blender, so they die and the pool waits forever (v4 hang).
        # Replace it, in the module that calls it, with a serial in-process version.
        import importlib
        img_types = importlib.import_module("bl_ext.user_default.io_soulstruct.soulstruct.blender.flver.image.types")
        def serial_texconv(configs):
            results = []
            for c in configs:
                try:
                    results.append(img_types.texconv_to_dds(c))
                except Exception as ex:
                    log(f"texconv failed for {c}: {ex}")
                    results.append(None)
            return results
        img_types.batch_texconv_to_dds = serial_texconv
        log("texture conversion: serial (multiprocessing pool bypassed)")
        # Add-on 3.2.1 bug (v5 failure): DDSTexture.tpf_platform returns the raw EnumProperty string ('PC'),
        # but TPF writing expects a TPFPlatform enum ('str' object has no attribute 'get_byte_order').
        _orig_platform = img_types.DDSTexture.tpf_platform
        img_types.DDSTexture.tpf_platform = property(
            lambda self: img_types.TPFPlatform[str(self.texture_properties.tpf_platform)], _orig_platform.fset)
        log("patched DDSTexture.tpf_platform -> TPFPlatform enum")
        for key, (k_obj, _) in knight.items():
            select_only(k_obj)
            r = bpy.ops.export_scene.equipment_flver()
            log(f"export {KNIGHT[key]}: {r}")
        for dp, _, fs in os.walk(STAGING):
            for f in fs:
                p = os.path.join(dp, f)
                log(f"  staged {os.path.relpath(p, STAGING)} ({os.path.getsize(p)} bytes)")

        # --- 6. preview render of the assembled set -------------------------------------------------
        sc_ = bpy.context.scene
        sc_.render.engine = "BLENDER_WORKBENCH"
        sc_.display.shading.light = "FLAT"
        sc_.display.shading.color_type = "TEXTURE"
        sc_.render.resolution_x, sc_.render.resolution_y = 900, 1100
        for key in ("LG_F",):
            knight[key][0].hide_render = True  # show male legs only
        cam_data = bpy.data.cameras.new("cam"); cam_data.type = "ORTHO"; cam_data.ortho_scale = 2.1
        cam = bpy.data.objects.new("cam", cam_data); sc_.collection.objects.link(cam); sc_.camera = cam
        cam.location, cam.rotation_euler = (0, -4, 0.95), (math.radians(90), 0, 0)
        sc_.render.filepath = os.path.join(ROOT, "work/swap_preview_front.png")
        bpy.ops.render.render(write_still=True)
        log("rendered work/swap_preview_front.png")
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "work/sora_knight_swap.blend"))
        log("saved work/sora_knight_swap.blend")
    except Exception:
        log("ERROR:\n" + traceback.format_exc())
    finally:
        save_report()


if __name__ == "__main__":
    _m = sys.modules.get("__main__")
    if _m is not None and hasattr(_m, "__file__"):
        try:
            del _m.__file__
        except AttributeError:
            pass
    main()
