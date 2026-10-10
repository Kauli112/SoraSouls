"""SoraSouls – Step 3: swap the Kingdom Key into the Broadsword model (WP_A_0204) and export a DSR PARTSBND.

The Knight class starts with the Broadsword (EquipParamWeapon 202000, WeaponModel 204), and only Broadsword
variants use model 204, so no param edits are needed.

Pipeline:
  1. Import WP_A_0204 (blade FLVER + sheath FLVER WP_A_0204_1) with Soulstruct.
  2. Import work/keyblade/W_EX010.fbx (OpenKH export). Drop the keychain + Mickey token (bones 3-11): DSR
     would hold that physics chain rigid.
  3. Re-orient into weapon space: grip (KH2 Bone0000) at origin, blade along -Y game (= -Z Blender), guard/teeth
     along X, same scale as Sora (0.01085) so it matches his hand.
  4. Replace the Broadsword blade geometry with the Keyblade; shrink the sheath to a point (Sora has no sheath).
  5. Export into STAGING work/export_keyblade (never the game or mod folder) and render a size comparison.
Run with tools/run_swap_keyblade.bat. Report: work/keyblade_report.txt
"""
import sys


def main():
    import bpy, bmesh, addon_utils, os, shutil, traceback, math, importlib
    from mathutils import Matrix, Vector

    ROOT = os.environ.get("SORASOULS_ROOT", "E:/SoraSouls")
    DSR = "D:/SteamLibrary/steamapps/common/DARK SOULS REMASTERED"
    FBX = os.path.join(ROOT, "work/keyblade/W_EX010.fbx")
    STAGING = os.path.join(ROOT, "work/export_keyblade")
    STEM = "WP_A_0204"
    SCALE = 0.01085                       # same KH2 -> DSR scale as Sora
    GRIP_KH = Vector((-59.7, 108.0, -2.5))  # KH2 Bone0000 (grip) in FBX coordinates (Y-up, cm)
    CHAIN_BONES = {f"Bone{i:04d}" for i in range(3, 12)}
    report = []

    def log(msg):
        print("[keyblade]", msg); report.append(str(msg))

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
        img.DDS_TEXTURE.dds_format = "DXT1"
        return img

    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)  # no startup-scene objects in renders
        addon_utils.enable("bl_ext.user_default.io_soulstruct", default_set=True)
        if os.path.isdir(STAGING):
            shutil.rmtree(STAGING)
        os.makedirs(STAGING)
        s = bpy.context.scene.soulstruct_settings
        s.game_enum = "DARK_SOULS_DSR"
        s.darksouls1r.game_root_str = DSR
        s.darksouls1r.project_root_str = STAGING
        s.prefer_import_from_project = False
        s.also_export_to_game = False
        bpy.context.scene.flver_export_settings.export_textures = True
        log(f"export target (staging): {s.project_root_path}")

        # --- 1. Broadsword --------------------------------------------------------------------------
        before = set(bpy.data.objects)
        bpy.ops.import_scene.equipment_flver(directory=os.path.join(DSR, "parts") + "/",
                                             files=[{"name": STEM + ".partsbnd.dcx"}])
        new = [o for o in bpy.data.objects if o not in before]
        log(f"imported {STEM}: {[(o.name, o.type, len(o.data.vertices) if o.type == 'MESH' else '') for o in new]}")
        meshes = [o for o in new if o.type == "MESH"]
        blade = next(o for o in meshes if o.name.split(" ")[0] == STEM)
        sheath = next((o for o in meshes if o.name.split(" ")[0] == STEM + "_1"), None)
        log(f"blade mesh {blade.name}: groups={[g.name for g in blade.vertex_groups]} "
            f"materials={[m.name for m in blade.data.materials]}")
        dummies = [o for o in new if o.type == "EMPTY"]
        log(f"dummies: {[(o.name, tuple(round(x, 3) for x in o.matrix_world.translation)) for o in dummies]}")
        bw = [blade.matrix_world @ v.co for v in blade.data.vertices]
        log(f"Broadsword Blender bbox: min {tuple(round(min(p[i] for p in bw), 3) for i in range(3))} "
            f"max {tuple(round(max(p[i] for p in bw), 3) for i in range(3))}")
        used = {x.group for v in blade.data.vertices for x in v.groups if x.weight > 0}
        bone_group = next((g.name for g in blade.vertex_groups if g.index in used), STEM)
        log(f"blade vertices are skinned to: {bone_group}")

        # --- 2. Keyblade ----------------------------------------------------------------------------
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=FBX, use_anim=False, ignore_leaf_bones=False,
                                 automatic_bone_orientation=False)
        kb_new = [o for o in bpy.data.objects if o not in before]
        for img in bpy.data.images:  # OpenKH writes texture paths without '.png'
            base = os.path.splitext(os.path.basename(bpy.path.abspath(img.filepath)))[0] or img.name
            png = os.path.join(os.path.dirname(FBX), base + ".png")
            if os.path.exists(png):
                img.filepath = png; img.reload()
        kb_meshes = [o for o in kb_new if o.type == "MESH"]
        for o in kb_meshes:
            mw = o.matrix_world.copy()
            o.parent = None
            for m in list(o.modifiers):
                o.modifiers.remove(m)
            o.data.transform(mw); o.matrix_world = Matrix.Identity(4)
            names = {g.index: g.name for g in o.vertex_groups}
            bm = bmesh.new(); bm.from_mesh(o.data)
            deform = bm.verts.layers.deform.active
            chain = [v for v in bm.verts if deform and v[deform] and
                     names[max(v[deform].items(), key=lambda kv: kv[1])[0]] in CHAIN_BONES]
            bmesh.ops.delete(bm, geom=chain, context="VERTS")
            bm.to_mesh(o.data); bm.free()
            log(f"{o.name}: removed {len(chain)} keychain verts, {len(o.data.vertices)} remain")
        kb_meshes = [o for o in kb_meshes if len(o.data.vertices)]
        for o in kb_new:
            if o.type == "ARMATURE" or (o.type == "MESH" and o not in kb_meshes):
                bpy.data.objects.remove(o, do_unlink=True)
        select_only(kb_meshes[0])
        for o in kb_meshes:
            o.select_set(True)
        bpy.ops.object.join()
        kb = bpy.context.view_layer.objects.active
        kb.name = "KEYBLADE"

        # --- 3. orient into weapon space -------------------------------------------------------------
        # FBX import maps KH2 (x,y,z) -> Blender 0.01*(x,-z,y): blade (+Z KH2) lies along -Y Blender.
        # DSR weapons point the blade along -Y game = -Z Blender, so rotate +90 deg about X, then scale.
        grip_bl = Vector((GRIP_KH.x, -GRIP_KH.z, GRIP_KH.y)) * 0.01
        M = Matrix.Scale(SCALE / 0.01, 4) @ Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Translation(-grip_bl)
        kb.data.transform(M)
        co = [v.co for v in kb.data.vertices]
        lo = Vector(tuple(min(p[i] for p in co) for i in range(3)))
        hi = Vector(tuple(max(p[i] for p in co) for i in range(3)))
        log(f"Keyblade Blender bbox: min {tuple(round(x, 3) for x in lo)} max {tuple(round(x, 3) for x in hi)} "
            f"(blade tip should be most negative Z)")

        # --- 4. materials + replace geometry ----------------------------------------------------------
        template = blade.data.materials[0]
        spec = flat_image("KEYBLADE_s", (0.25, 0.25, 0.25, 1.0))  # a little shine – it is metal
        norm = flat_image("KEYBLADE_n", (0.5, 0.5, 1.0, 1.0))
        for slot in kb.material_slots:
            fbx_mat = slot.material
            img = next(n.image for n in fbx_mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image)
            img.name = "KEYBLADE_" + os.path.splitext(os.path.basename(img.filepath))[0]
            img.pack(); img.DDS_TEXTURE.dds_format = "DXT5"
            m = template.copy(); m.name = f"{img.name}_{slot.slot_index}"
            nodes = {n.name: n for n in m.node_tree.nodes if n.type == "TEX_IMAGE"}
            nodes["g_Diffuse"].image = img
            nodes["g_Specular"].image = spec
            nodes["g_Bumpmap"].image = norm
            slot.material = m
        kb.data.uv_layers[0].name = blade.data.uv_layers[0].name
        kc = blade.data.color_attributes[0]
        cattr = kb.data.color_attributes.new(kc.name, kc.data_type, kc.domain)
        for d in cattr.data:
            d.color = (1.0, 1.0, 1.0, 1.0)
        kb.vertex_groups.clear()
        g = kb.vertex_groups.new(name=bone_group)
        g.add(list(range(len(kb.data.vertices))), 1.0, "REPLACE")

        bm = bmesh.new(); bm.to_mesh(blade.data); bm.free()
        select_only(blade)
        while blade.material_slots:
            blade.active_material_index = 0
            bpy.ops.object.material_slot_remove()
        kb.matrix_world = blade.matrix_world.copy()
        kb.select_set(True)
        bpy.ops.object.join()
        bpy.ops.object.material_slot_remove_unused()
        if any(sl.material is None for sl in blade.material_slots):
            raise RuntimeError("empty material slot after join")
        log(f"{blade.name}: now {len(blade.data.vertices)} verts, materials={[m.name for m in blade.data.materials]}")

        if sheath:
            for v in sheath.data.vertices:
                v.co *= 0.001  # collapse to a point at the grip: invisible, but keeps a valid FLVER
            # v1 failure: the sheath still referenced Broadsword textures (DDS format 'SAME') -> reuse ours.
            for slot in sheath.material_slots:
                slot.material = blade.data.materials[0]
            log(f"sheath {sheath.name}: collapsed ({len(sheath.data.vertices)} verts), "
                f"materials={[m.name for m in sheath.data.materials]}")

        # --- 5. export (same Soulstruct 3.2.1 workarounds as the Sora swap) ---------------------------
        img_types = importlib.import_module("bl_ext.user_default.io_soulstruct.soulstruct.blender.flver.image.types")
        def serial_texconv(configs):
            out = []
            for c in configs:
                try:
                    out.append(img_types.texconv_to_dds(c))
                except Exception as ex:
                    log(f"texconv failed for {c}: {ex}"); out.append(None)
            return out
        img_types.batch_texconv_to_dds = serial_texconv
        _orig = img_types.DDSTexture.tpf_platform
        img_types.DDSTexture.tpf_platform = property(
            lambda self: img_types.TPFPlatform[str(self.texture_properties.tpf_platform)], _orig.fset)
        select_only(blade)
        if sheath:
            sheath.select_set(True)
        r = bpy.ops.export_scene.equipment_flver()
        log(f"export {STEM}: {r}")
        for dp, _, fs in os.walk(STAGING):
            for f in fs:
                p = os.path.join(dp, f)
                log(f"  staged {os.path.relpath(p, STAGING)} ({os.path.getsize(p)} bytes)")

        # --- 6. preview: Keyblade next to the original Broadsword --------------------------------------
        ref_before = set(bpy.data.objects)
        bpy.ops.import_scene.equipment_flver(directory=os.path.join(DSR, "parts") + "/",
                                             files=[{"name": STEM + ".partsbnd.dcx"}])
        for o in set(bpy.data.objects) - ref_before:
            if o.type in ("MESH", "ARMATURE") and o.parent is None:
                o.location.x += 0.35  # original sword shown to the right for scale
        scn = bpy.context.scene
        scn.render.engine = "BLENDER_WORKBENCH"
        scn.display.shading.light = "FLAT"
        scn.display.shading.color_type = "TEXTURE"
        scn.render.resolution_x, scn.render.resolution_y = 900, 1100
        cam_data = bpy.data.cameras.new("cam"); cam_data.type = "ORTHO"; cam_data.ortho_scale = 1.4
        cam = bpy.data.objects.new("cam", cam_data); scn.collection.objects.link(cam); scn.camera = cam
        for label, loc, rot in (("front", (0.17, -3, -0.3), (math.radians(90), 0, 0)),
                                ("side", (3, 0, -0.3), (math.radians(90), 0, math.radians(90)))):
            cam.location, cam.rotation_euler = loc, rot
            scn.render.filepath = os.path.join(ROOT, f"work/keyblade/preview_{label}.png")
            bpy.ops.render.render(write_still=True)
            log(f"rendered work/keyblade/preview_{label}.png")
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "work/keyblade/keyblade_swap.blend"))
    except Exception:
        log("ERROR:\n" + traceback.format_exc())
    finally:
        open(os.path.join(ROOT, "work/keyblade_report.txt"), "w", encoding="utf-8").write("\n".join(report))


if __name__ == "__main__":
    _m = sys.modules.get("__main__")
    if _m is not None and hasattr(_m, "__file__"):
        try:
            del _m.__file__  # keep multiprocessing workers from re-running this script
        except AttributeError:
            pass
    main()
