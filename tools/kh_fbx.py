"""SoraSouls – load a skinned KH2 character exported by OpenKH Kh2MdlxEditor (FBX 7.x binary) (v100).

Returns the skeleton (name, parent, global bind matrix), every mesh as triangles with per-corner position / UV /
material, and per-control-point skin weights. Built on fbx_keyblade.read (binary FBX node reader).
Units/axes as exported: KH2 centimetres, Y up, character faces +Z.
"""
import numpy as np
from fbx_keyblade import read, find, child, props70


def _name(n):
    return n[1][1].split(b"\x00")[0].decode()


def _mat(v):
    return np.array(v, dtype=float).reshape(4, 4).T          # FBX stores column-major -> row-vector convention fix


def _euler_xyz(deg):
    rx, ry, rz = np.radians(deg)
    cx, sx, cy, sy, cz, sz = np.cos(rx), np.sin(rx), np.cos(ry), np.sin(ry), np.cos(rz), np.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx                                       # FBX eEulerXYZ: X first


def load(path):
    top = read(path)
    O = next(find(top, "Objects")); C = next(find(top, "Connections"))
    objs = {n[1][0]: n for n in O[2]}
    conns = [(c[1][1], c[1][2], c[1][0], c[1][3] if len(c[1]) > 3 else None) for c in C[2]]
    children, parents = {}, {}
    for ch, pa, t, prop in conns:
        children.setdefault(pa, []).append(ch); parents.setdefault(ch, []).append(pa)

    # ---- skeleton: LimbNode models, local TRS -> global bind matrices ----
    bones = {}
    for oid, n in objs.items():
        if n[0] == "Model" and n[1][2] in (b"LimbNode", b"Root", b"Null"):
            p = props70(n)
            t = np.array(p.get("Lcl Translation", [0, 0, 0])[:3], float)
            r = np.array(p.get("Lcl Rotation", [0, 0, 0])[:3], float)
            s = np.array(p.get("Lcl Scaling", [1, 1, 1])[:3], float)
            M = np.eye(4); M[:3, :3] = _euler_xyz(r) * s; M[:3, 3] = t
            bones[oid] = dict(name=_name(n), local=M, parent=None)
    for oid, b in bones.items():
        for pa in parents.get(oid, []):
            if pa in bones:
                b["parent"] = pa
    def glob(oid):
        b = bones[oid]
        if "glob" not in b:
            b["glob"] = (glob(b["parent"]) if b["parent"] else np.eye(4)) @ b["local"]
        return b["glob"]
    for oid in bones:
        glob(oid)
    # cluster TransformLink = the bone's global bind matrix as the skin sees it (preferred when present)
    link = {}
    for oid, n in objs.items():
        if n[0] == "Deformer" and n[1][2] == b"Cluster":
            tl = child(n, "TransformLink")
            bone = [p for p in children.get(oid, []) if p in bones]
            if tl is not None and bone:
                link[bone[0]] = _mat(tl[1][0])

    # ---- meshes ----
    tex_of_mat = {}
    for oid, n in objs.items():
        if n[0] == "Material":
            for t in children.get(oid, []):
                if objs.get(t, ("",))[0] == "Texture":
                    fn = child(objs[t], "RelativeFilename") or child(objs[t], "FileName")
                    tex_of_mat[oid] = fn[1][0].decode(errors="replace").replace("\\", "/").split("/")[-1] if fn else "?"
    meshes = []
    for gid, g in [(k, n) for k, n in objs.items() if n[0] == "Geometry" and n[1][2] == b"Mesh"]:
        V = child(g, "Vertices")[1][0].reshape(-1, 3).astype(float)
        PVI = child(g, "PolygonVertexIndex")[1][0]
        model = next((p for p in parents.get(gid, []) if objs.get(p, ("",))[0] == "Model"), None)
        mats = [c for c in children.get(model, []) if objs.get(c, ("",))[0] == "Material"] if model else []
        Ul = child(g, "LayerElementUV"); Ml = child(g, "LayerElementMaterial")
        uvdata = child(Ul, "UV")[1][0].reshape(-1, 2); uvmt = child(Ul, "MappingInformationType")[1][0]
        uvrt = child(Ul, "ReferenceInformationType")[1][0]; uvidx = child(Ul, "UVIndex")[1][0] if child(Ul, "UVIndex") else None
        mat_ids = child(Ml, "Materials")[1][0] if Ml is not None else np.zeros(1, int)
        mat_mt = child(Ml, "MappingInformationType")[1][0] if Ml is not None else b"AllSame"
        tris, polys, cur = [], [], []
        for k, i in enumerate(PVI):
            if i < 0:
                cur.append((~i, k)); polys.append(cur); cur = []
            else:
                cur.append((i, k))
        for pi, poly in enumerate(polys):
            mi = mat_ids[pi] if mat_mt == b"ByPolygon" else mat_ids[0]
            tex = tex_of_mat.get(mats[mi], "?") if mi < len(mats) else "?"
            for a in range(1, len(poly) - 1):
                tri = [poly[0], poly[a], poly[a + 1]]
                uv = []
                for cp, pv in tri:
                    j = pv if uvmt == b"ByPolygonVertex" else cp
                    if uvrt == b"IndexToDirect":
                        j = uvidx[j]
                    uv.append(uvdata[j])
                tris.append((tri[0][0], tri[1][0], tri[2][0], np.array(uv), tex))
        # skin weights per control point
        W = [dict() for _ in range(len(V))]
        for sk in children.get(gid, []):
            if objs.get(sk, ("",))[0] != "Deformer":
                continue
            for cl in children.get(sk, []):
                c = objs[cl]; ix = child(c, "Indexes"); w = child(c, "Weights")
                bone = [p for p in children.get(cl, []) if p in bones]
                if ix is None or not bone:
                    continue
                for i, ww in zip(ix[1][0], w[1][0]):
                    W[i][bone[0]] = W[i].get(bone[0], 0) + float(ww)
        meshes.append(dict(name=_name(objs[model]) if model else str(gid), V=V, tris=tris, W=W))
    return dict(bones=bones, link=link, meshes=meshes)


if __name__ == "__main__":
    import sys, collections
    d = load(sys.argv[1])
    print("bones", len(d["bones"]), "with TransformLink", len(d["link"]))
    for m in d["meshes"]:
        print(m["name"], "verts", len(m["V"]), "tris", len(m["tris"]), "textures",
              collections.Counter(t[4] for t in m["tris"]), "unweighted", sum(1 for w in m["W"] if not w))
