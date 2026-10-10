r"""SoraSouls – make the KH2 exports the converter needs from the player's own OpenKH data folder, no clicking (v125).

The converter reads OpenKH Kh2MdlxEditor exports (FBX + PNG). Instead of the player exporting each model by hand,
this calls the same OpenKH code the editor's "Export as FBX" runs (found by reflection, OpenKH 26.4):
  Main2_VM(path) -> Kh2MdlxAssimp.getAssimpScene(ModelFile) -> AssimpGeneric.ExportScene(.., fbx, ..)  (the editor's
  current window, Main2_Window; the older Main_Window path writes unshared vertices and other mesh groups)
  textures: TextureFile.Images[i] -> ImageReadExtensions.GetBimapSource -> AssimpGeneric.ExportBitmapSourceAsPng
It runs inside the player's own OpenKH installation (its .NET 8 assemblies, loaded with pythonnet); SoraSouls ships
none of OpenKH and no KH2 file. Input: OpenKH's data\kh2 folder (obj\*.mdlx, extracted by the player with OpenKH).

  python kh2_export.py <OpenKH folder (with OpenKh.Tools.Kh2MdlxEditor.dll)> <OpenKH data\kh2 folder> <out folder>
"""
import os, shutil, sys, tempfile

# (out subfolder, mdlx name, fbx name or None, texture names or None) – the layout rebuild_mod.py reads
JOBS = [("sora", "P_EX100", "P_EX100", "Texture{:04d}.png")]
JOBS += [(f"drive/{f}", m, None, "Texture{:04d}.png") for f, m in
         (("valor", "P_EX100_BTLF"), ("wisdom", "P_EX100_MAGF"), ("master", "P_EX100_TRIF"),
          ("final", "P_EX100_ULTF"), ("antiform", "P_EX100_HTLF"))]
for who, body, weapon in (("donald", "P_EX020", "W_EX020"), ("goofy", "P_EX030", "W_EX030")):
    JOBS += [(who, body, body, "Texture{:04d}.png"), (who, weapon, weapon, weapon + "_Texture{:04d}.png")]
JOBS += [("keyblade", k, k, None) for k in
         ("W_EX010", "W_EX010_10", "W_EX010_20", "W_EX010_30", "W_EX010_40", "W_EX010_M0", "W_EX010_N0")]


def load_openkh(okh):
    from pythonnet import load
    load("coreclr", runtime_config=os.path.join(okh, "OpenKh.Tools.Kh2MdlxEditor.runtimeconfig.json"))
    import clr
    from System.Reflection import Assembly
    asm = {n: Assembly.LoadFrom(os.path.join(okh, n + ".dll")) for n in
           ("OpenKh.Tools.Kh2MdlxEditor", "OpenKh.AssimpUtils", "OpenKh.Engine", "OpenKh.Tools.Common.Wpf")}
    # AssimpNet finds its native library relative to the host exe (python.exe here), so load OpenKH's copy explicitly
    assimp = Assembly.LoadFrom(os.path.join(okh, "AssimpNet.dll"))
    lib = assimp.GetType("Assimp.Unmanaged.AssimpLibrary").GetProperty("Instance").GetValue(None)
    lib.LoadLibrary(os.path.join(okh, "runtimes", "win-x64", "native", "assimp.dll"))
    T = lambda a, t: asm[a].GetType(t)
    return dict(
        vm=T("OpenKh.Tools.Kh2MdlxEditor", "OpenKh.Tools.Kh2MdlxEditor.ViewModels.Main2_VM"),
        parser=T("OpenKh.Engine", "OpenKh.Engine.Parsers.MdlxParser"),
        kh2assimp=T("OpenKh.AssimpUtils", "OpenKh.AssimpUtils.Kh2MdlxAssimp"),
        generic=T("OpenKh.AssimpUtils", "OpenKh.AssimpUtils.AssimpGeneric"),
        fmt=T("OpenKh.AssimpUtils", "OpenKh.AssimpUtils.AssimpGeneric+FileFormat"),
        img=T("OpenKh.Tools.Common.Wpf", "OpenKh.Tools.Common.Wpf.ImageReadExtensions"))


def _static(t, name, *args):
    from System import Array, Object
    for m in t.GetMethods():
        if m.Name == name and m.IsStatic and len(m.GetParameters()) == len(args) and all(
                p.ParameterType.IsInstanceOfType(a) for p, a in zip(m.GetParameters(), args)):
            return m.Invoke(None, Array[Object](list(args)))
    raise RuntimeError(f"OpenKH: {t.FullName}.{name} not found (different OpenKH version?)")


def export(okh, data, out):
    api = load_openkh(okh)
    from System import Activator, Array, Object, Enum
    fbx_fmt = Enum.Parse(api["fmt"], "fbx", True)
    os.makedirs(out, exist_ok=True)
    for sub, mdlx, fbx, tex in JOBS:
        src = os.path.join(data, "obj", mdlx + ".mdlx")
        if not os.path.exists(src):
            raise FileNotFoundError(src)
        dst = os.path.join(out, sub)
        os.makedirs(dst, exist_ok=True)
        vm = Activator.CreateInstance(api["vm"], Array[Object]([src]))
        if fbx:
            scene = _static(api["kh2assimp"], "getAssimpScene", vm.ModelFile)
            _static(api["generic"], "ExportScene", scene, fbx_fmt, os.path.join(dst, fbx + ".fbx"))
        if tex:
            images = vm.TextureFile.Images
            for i in range(images.Count):
                bmp = _static(api["img"], "GetBimapSource", images[i])
                _static(api["generic"], "ExportBitmapSourceAsPng", bmp, os.path.join(dst, tex.format(i))[:-4])  # adds .png
        print(f"{sub}: {mdlx}" + (f" -> {fbx}.fbx" if fbx else "") + (" + textures" if tex else ""))


if __name__ == "__main__":
    export(*sys.argv[1:4])
