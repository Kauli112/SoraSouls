"""SoraSouls – equipment-menu icons for the Keyblades (v116). User: "add the keyblade images to the equipment menu so
it looks like the item it is instead of a broadsword".

How DSR draws item icons (measured on the user's menu/menu.drb): the dialog "Icon" holds one entry per icon,
named EquIcon_<id> (<id> = EquipParamWeapon.WeaponIcon etc.), each a Sprite that crops a 160x180 cell out of an icon
sheet (TEXI index -> texture in menu/menu_*.tpf). The sheet Icon40 (TEXI 1, menu_0.tpf, 2048x1024 DXT5, 12 mips) has
an empty strip below v=734, room for 12 cells.

This tool:
  1. renders each Keyblade from the user's OpenKH export (same geometry as make_keyblades.py) as a 160x180 icon,
     diagonal like the vanilla weapon icons, with simple lighting and a soft dark outline;
  2. paints the icons into that strip of Icon40 – every mip level; only the DXT5 blocks that overlap an icon are
     re-encoded, every other block of the sheet stays byte-identical;
  3. adds EquIcon_0205.. entries to menu.drb (strings, sprite data, shape/control records appended; the new dialog
     entries are inserted at the end of the "Icon" dialog and later dialogs' offsets moved to match);
  4. keyblades.py / build_abilities.py set WeaponIcon to those ids.
Usage: python keyblade_icons.py <keyblade dir (FBX)> <kb texture dir (png)> <game menu dir> <out mod dir> [preview.png]
       [<OpenKH remastered itempic dir>]   (v118: with it, KH2's own HD item pictures replace the renders)
"""
import io, os, struct, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ICON_W, ICON_H = 160, 180
SHEET, SHEET_TEXI, SHEET_TPF = "Icon40", 1, "menu_0.tpf.dcx"
CELL_V0, CELL_U0, CELL_STEP = 740, 4, 164          # 4-aligned cells in the free strip (vanilla use ends at v=734)
FIRST_ID = 205                                      # EquIcon_0205+ are unused in vanilla (0204 is the last of its run)
TEMPLATE_ICON = "EquIcon_0204"
# (key, label, fbx stem, texture png stem)
ICONS = [
    ("KingdomKey", "Kingdom Key", "W_EX010", "W_EX010"),
    ("StarSeeker", "Star Seeker", "W_EX010_30", "W_EX010_30"),
    ("HiddenDragon", "Hidden Dragon", "W_EX010_40", "W_EX010_40"),
    ("Fenrir", "Fenrir", "W_EX010_M0", "W_EX010_M0"),
    ("Oathkeeper", "Oathkeeper", "W_EX010_10", "W_EX010_10"),
    ("Oblivion", "Oblivion", "W_EX010_20", "W_EX010_20"),
    ("Ultima", "Ultima Weapon", "W_EX010_N0", "W_EX010_N0"),
]
ICON_ID = {k: FIRST_ID + i for i, (k, *_r) in enumerate(ICONS)}
# v118 (user: "use KH2's icons"): KH2's own menu pictures for these Keyblades (OpenKH data/kh2/remastered/itempic/
# item-NNN.imd/-0.dds, 512x512 HD; identified on a contact sheet of the user's files)
KH2_ITEMPIC = {"KingdomKey": 43, "Oathkeeper": 44, "Oblivion": 45, "StarSeeker": 46, "HiddenDragon": 47,
               "Fenrir": 63, "Ultima": 64}


# v119 (user: Drive Form icons; web images declined – SoraSouls only builds from the user's own files; user choice
# "form-coloured crown emblem"): KH2's crown (item picture 344, HD) recoloured per form, icons EquIcon_0212-0215 in the
# next cells of the same strip. Each form keeps the crown's shading: luminance x form colour, highlights kept bright.
CROWN_ITEMPIC = 344
DRIVE_ICONS = [("valor", "Valor Form", (215, 45, 40)), ("wisdom", "Wisdom Form", (45, 105, 230)),
               ("master", "Master Form", (245, 195, 40)), ("final", "Final Form", (235, 238, 250))]
DRIVE_ICON_ID = {k: FIRST_ID + len(ICONS) + i for i, (k, *_r) in enumerate(DRIVE_ICONS)}


# v122 (user: "add drive recovery items"): KH2's own item pictures 007 Drive Recovery / 008 High Drive Recovery.
# The Icon40 strip is full (11 of 12 cells + margin), so these go on the sheet Icon21 (TEXI 28, menu_3.tpf, 2048x1024;
# vanilla sprites only use rows up to v=550) in a strip at v=556.
SHEET2, SHEET2_TEXI, SHEET2_TPF, CELL2_V0 = "Icon21", 28, "menu_3.tpf.dcx", 556
ITEM_ICONS = [("drive_recovery", "Drive Recovery", 7), ("high_drive_recovery", "High Drive Recovery", 8)]
ITEM_ICON_ID = {k: FIRST_ID + len(ICONS) + len(DRIVE_ICONS) + i for i, (k, *_r) in enumerate(ITEM_ICONS)}


def itempic_icon(itempic_dir, num):
    p = os.path.join(itempic_dir, f"item-{num:03d}.imd", "-0.dds")
    im = Image.open(p).convert("RGBA").resize((ICON_W, ICON_W), Image.LANCZOS)
    out = Image.new("RGBA", (ICON_W, ICON_H), (0, 0, 0, 0))
    out.alpha_composite(im, (0, (ICON_H - ICON_W) // 2))
    return out


def crown_icon(itempic_dir, colour):
    p = os.path.join(itempic_dir, f"item-{CROWN_ITEMPIC:03d}.imd", "-0.dds")
    a = np.asarray(Image.open(p).convert("RGBA")).astype(np.float32) / 255
    lum = a[..., :3] @ np.array([0.3, 0.59, 0.11])
    lum = np.clip((lum - lum[a[..., 3] > 0.5].min()) / (np.ptp(lum[a[..., 3] > 0.5]) + 1e-6), 0, 1)
    c = np.array(colour, np.float32) / 255
    rgb = np.clip(c[None, None] * (0.25 + 0.95 * lum[..., None]) + np.clip(lum - 0.85, 0, 1)[..., None] * 2.5, 0, 1)
    im = Image.fromarray((np.dstack([rgb, a[..., 3:]]) * 255).astype(np.uint8), "RGBA").resize((ICON_W, ICON_W),
                                                                                                Image.LANCZOS)
    out = Image.new("RGBA", (ICON_W, ICON_H), (0, 0, 0, 0))
    out.alpha_composite(im, (0, (ICON_H - ICON_W) // 2))
    return out


def kh2_icon(itempic_dir, key):
    """KH2 HD item picture -> 160x180 icon (square art fitted to the width, centred vertically)"""
    p = os.path.join(itempic_dir, f"item-{KH2_ITEMPIC[key]:03d}.imd", "-0.dds")
    im = Image.open(p).convert("RGBA").resize((ICON_W, ICON_W), Image.LANCZOS)
    out = Image.new("RGBA", (ICON_W, ICON_H), (0, 0, 0, 0))
    out.alpha_composite(im, (0, (ICON_H - ICON_W) // 2))
    return out


# ---------------------------------------------------------------------------------------------------- 1. render
def render(fbx, png):
    from make_keyblades import geometry
    P, N, T, U = geometry(fbx)
    tex = np.asarray(Image.open(png).convert("RGBA")).astype(np.float32) / 255.0
    th, tw = tex.shape[:2]
    # game space: blade along -Y (tip), flat in X-Y. Screen: tip up-right, handle bottom-left (vanilla icon pose).
    a = np.radians(-45.0)
    R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    xy = np.stack([P[:, 0], -P[:, 1]], 1) @ R.T
    z = P[:, 2]
    S = 4                                                        # supersampling
    W, H = ICON_W * S, ICON_H * S
    pad = 0.08
    lo, hi = xy.min(0), xy.max(0)
    sc = min(W * (1 - 2 * pad) / (hi[0] - lo[0]), H * (1 - 2 * pad) / (hi[1] - lo[1]))
    c = (lo + hi) / 2
    sx = (xy[:, 0] - c[0]) * sc + W / 2
    sy = H / 2 - (xy[:, 1] - c[1]) * sc
    img = np.zeros((H, W, 4), np.float32)
    zb = np.full((H, W), -np.inf, np.float32)
    light = np.array([-0.4, 0.6, 0.7]); light /= np.linalg.norm(light)
    for t in range(len(P) // 3):
        i = slice(3 * t, 3 * t + 3)
        x0, y0 = sx[i], sy[i]
        xmin, xmax = int(max(np.floor(x0.min()), 0)), int(min(np.ceil(x0.max()), W - 1))
        ymin, ymax = int(max(np.floor(y0.min()), 0)), int(min(np.ceil(y0.max()), H - 1))
        if xmax < xmin or ymax < ymin:
            continue
        gx, gy = np.meshgrid(np.arange(xmin, xmax + 1) + 0.5, np.arange(ymin, ymax + 1) + 0.5)
        d = (y0[1] - y0[2]) * (x0[0] - x0[2]) + (x0[2] - x0[1]) * (y0[0] - y0[2])
        if abs(d) < 1e-9:
            continue
        l0 = ((y0[1] - y0[2]) * (gx - x0[2]) + (x0[2] - x0[1]) * (gy - y0[2])) / d
        l1 = ((y0[2] - y0[0]) * (gx - x0[2]) + (x0[0] - x0[2]) * (gy - y0[2])) / d
        l2 = 1 - l0 - l1
        m = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        if not m.any():
            continue
        zz = l0 * z[i][0] + l1 * z[i][1] + l2 * z[i][2]
        uv = l0[..., None] * U[i][0] + l1[..., None] * U[i][1] + l2[..., None] * U[i][2]
        n = l0[..., None] * N[i][0] + l1[..., None] * N[i][1] + l2[..., None] * N[i][2]
        tu = np.clip((uv[..., 0] % 1.0) * tw, 0, tw - 1).astype(int)
        tv = np.clip((uv[..., 1] % 1.0) * th, 0, th - 1).astype(int)   # U already has v flipped (1 - v)
        col = tex[tv, tu]
        ys, xs = np.nonzero(m)
        Y, X = ys + ymin, xs + xmin
        keep = (zz[m] > zb[Y, X]) & (col[m][:, 3] > 0.5)
        Y, X = Y[keep], X[keep]
        nn = n[m][keep]
        lam = 0.55 + 0.45 * np.abs(nn @ light) / (np.linalg.norm(nn, axis=1) + 1e-9)
        cc = col[m][keep]
        img[Y, X, :3] = np.clip(cc[:, :3] * lam[:, None] * 1.1, 0, 1)
        img[Y, X, 3] = 1.0
        zb[Y, X] = zz[m][keep]
    im = Image.fromarray((img * 255).astype(np.uint8), "RGBA").resize((ICON_W, ICON_H), Image.LANCZOS)
    # soft dark outline so the icon reads on the menu background
    a = np.asarray(im)[..., 3].astype(np.float32) / 255
    from scipy.ndimage import maximum_filter, gaussian_filter
    halo = gaussian_filter(maximum_filter(a, 5), 1.2) * 0.75
    out = np.zeros((ICON_H, ICON_W, 4), np.float32)
    out[..., 3] = np.maximum(halo, a)
    rgb = np.asarray(im)[..., :3].astype(np.float32) / 255
    out[..., :3] = rgb * (a / np.maximum(out[..., 3], 1e-6))[..., None]
    return Image.fromarray((out * 255).astype(np.uint8), "RGBA")


# ---------------------------------------------------------------------------------------------------- 2. DXT5
def _565(c):
    c = np.clip(np.round(c), 0, 255).astype(int)
    return ((c[0] >> 3) << 11) | ((c[1] >> 2) << 5) | (c[2] >> 3)


def _un565(v):
    return np.array([((v >> 11) & 31) * 255 / 31, ((v >> 5) & 63) * 255 / 63, (v & 31) * 255 / 31])


def encode_block(px):
    """px (4,4,4) uint8 RGBA -> 16-byte DXT5 block"""
    p = px.reshape(16, 4).astype(np.float32)
    a = p[:, 3]
    a0, a1 = int(a.max()), int(a.min())
    if a0 == a1:
        ab = struct.pack("<BB", a0, a1) + b"\0" * 6
    else:
        pal = [a0, a1] + [((7 - k) * a0 + k * a1) / 7 for k in range(1, 7)]
        idx = np.argmin(np.abs(a[:, None] - np.array(pal)[None]), 1)
        bits = 0
        for k, v in enumerate(idx):
            bits |= int(v) << (3 * k)
        ab = struct.pack("<BB", a0, a1) + bits.to_bytes(6, "little")
    rgb = p[:, :3]
    w = a > 8
    src = rgb[w] if w.any() else rgb
    mean = src.mean(0)
    if len(src) > 1 and np.ptp(src, 0).max() > 0:
        ax = np.linalg.svd(src - mean, full_matrices=False)[2][0]
        proj = (src - mean) @ ax
        c0, c1 = mean + proj.max() * ax, mean + proj.min() * ax
    else:
        c0 = c1 = mean
    e0, e1 = _565(c0), _565(c1)
    if e0 < e1:
        e0, e1 = e1, e0
    if e0 == e1:
        cb = struct.pack("<HHI", e0, e1, 0)
    else:
        q0, q1 = _un565(e0), _un565(e1)
        pal = np.array([q0, q1, (2 * q0 + q1) / 3, (q0 + 2 * q1) / 3])
        idx = np.argmin(((rgb[:, None] - pal[None]) ** 2).sum(2), 1)
        bits = 0
        for k, v in enumerate(idx):
            bits |= int(v) << (2 * k)
        cb = struct.pack("<HHI", e0, e1, bits)
    return ab + cb


def dds_levels(d):
    h, w = struct.unpack_from("<II", d, 12)
    mips = struct.unpack_from("<I", d, 28)[0]
    off, out = 128, []
    for L in range(mips):
        lw, lh = max(1, w >> L), max(1, h >> L)
        size = max(1, (lw + 3) // 4) * max(1, (lh + 3) // 4) * 16
        out.append((off, lw, lh, size)); off += size
    return out


def level_image(d, off, lw, lh, size):
    hdr = bytearray(d[:128])
    struct.pack_into("<II", hdr, 12, lh, lw)
    struct.pack_into("<I", hdr, 20, size)
    struct.pack_into("<I", hdr, 28, 1)
    return np.asarray(Image.open(io.BytesIO(bytes(hdr) + d[off:off + size])).convert("RGBA")).copy()


def paint_sheet(dds, tiles):
    """tiles: [(u0, v0, RGBA image 160x180)] -> new DDS bytes (only overlapped blocks re-encoded, all mips)"""
    d = bytearray(dds)
    for L, (off, lw, lh, size) in enumerate(dds_levels(dds)):
        if lw < 4 or lh < 4:
            break
        img = level_image(dds, off, lw, lh, size)
        touched = set()
        for u0, v0, tile in tiles:
            x0, y0 = u0 >> L, v0 >> L
            tw, th = max(1, ICON_W >> L), max(1, ICON_H >> L)
            t = np.asarray(tile.resize((tw, th), Image.LANCZOS))
            img[y0:y0 + th, x0:x0 + tw] = t[:lh - y0, :lw - x0]
            for by in range(y0 // 4, (y0 + th + 3) // 4):
                for bx in range(x0 // 4, (x0 + tw + 3) // 4):
                    touched.add((by, bx))
        bpr = (lw + 3) // 4
        for by, bx in touched:
            blk = img[4 * by:4 * by + 4, 4 * bx:4 * bx + 4]
            if blk.shape[:2] != (4, 4):
                continue
            o = off + (by * bpr + bx) * 16
            d[o:o + 16] = encode_block(blk)
    return bytes(d)


# ---------------------------------------------------------------------------------------------------- 3. DRB
SECTIONS = ["STR\0", "TEXI", "SHPR", "CTPR", "ANIP", "INTP", "SCDP", "SHAP", "CTRL", "ANIK", "ANIO", "ANIM", "SCDK",
            "SCDO", "SCDL", "DLGO", "DLG\0"]


def drb_read(raw):
    secs, o = {}, 16
    for name in SECTIONS + ["END\0"]:
        assert raw[o:o + 4] == name.encode(), (name, raw[o:o + 4])
        size, count, z = struct.unpack_from("<iii", raw, o + 4)
        secs[name] = [bytearray(raw[o + 16:o + 16 + size]), count, z]
        o += 16 + size
    return secs


def drb_write(secs):
    out = bytearray(b"DRB\0" + b"\0" * 12)
    for name in SECTIONS + ["END\0"]:
        data, count, z = secs[name]
        if len(data) % 16:
            data = data + b"\0" * (16 - len(data) % 16)
        out += name.encode() + struct.pack("<iii", len(data), count, z) + data
    return bytes(out)


def _str(strs, off):
    e = off
    while strs[e:e + 2] != b"\0\0":
        e += 2
    return strs[off:e].decode("utf-16-le")


def drb_add_icons(raw, entries):
    """entries: [(icon_id, u0, v0)] on sheet SHEET_TEXI. Returns new drb bytes."""
    secs = drb_read(raw)
    STR, SHPR, SHAP, CTRL, DLGO, DLG = (secs[k] for k in ("STR\0", "SHPR", "SHAP", "CTRL", "DLGO", "DLG\0"))
    strs = STR[0]
    # strip STR padding to append strings after the last real one (count strings)
    real_end, k, o = 0, 0, 0
    while k < STR[1]:
        while strs[o:o + 2] != b"\0\0":
            o += 2
        o += 2; k += 1
    real_end = o
    strs = strs[:real_end]
    dlgs = [list(struct.unpack_from("<16i", DLG[0], 64 * i)) for i in range(DLG[1])]
    icon = next(i for i, g in enumerate(dlgs) if _str(strs, g[0]) == "Icon")
    g = dlgs[icon]
    base, n = g[9] // 32, g[8]
    dlgo = [list(struct.unpack_from("<8i", DLGO[0], 32 * i)) for i in range(DLGO[1])]
    tmpl = next(dlgo[j] for j in range(base, base + n) if _str(strs, dlgo[j][0]) == TEMPLATE_ICON)
    names = {_str(strs, dlgo[j][0]) for j in range(base, base + n)}
    t_type, t_shpr = struct.unpack_from("<ii", SHAP[0], tmpl[1])
    sprite = bytearray(SHPR[0][t_shpr:t_shpr + 36])
    ctrl_rec = bytes(CTRL[0][tmpl[2]:tmpl[2] + 8])
    shpr = SHPR[0]
    shap_data, ctrl_data = SHAP[0][:8 * SHAP[1]], CTRL[0][:8 * CTRL[1]]
    shpr = shpr[:]                                     # appended after existing data (keep 4-byte alignment)
    new_dlgo = []
    for ent in entries:
        icon_id, u0, v0 = ent[:3]
        texi = ent[3] if len(ent) > 3 else SHEET_TEXI
        nm = f"EquIcon_{icon_id:04d}"
        assert nm not in names, nm
        name_off = len(strs); strs += nm.encode("utf-16-le") + b"\0\0"; STR[1] += 1
        sp = bytearray(sprite)
        struct.pack_into("<4h", sp, 16, u0, v0, u0 + ICON_W, v0 + ICON_H)   # shorts 8-11: uv rect
        struct.pack_into("<h", sp, 24, texi)                                # short 12: TEXI index
        while len(shpr) % 4:
            shpr += b"\0"
        sp_off = len(shpr); shpr += sp
        shap_off = len(shap_data); shap_data += struct.pack("<ii", t_type, sp_off); SHAP[1] += 1
        ctrl_off = len(ctrl_data); ctrl_data += ctrl_rec; CTRL[1] += 1
        new_dlgo.append([name_off, shap_off, ctrl_off, *tmpl[3:]])
    ins = base + n
    dlgo = dlgo[:ins] + new_dlgo + dlgo[ins:]
    shift = 32 * len(new_dlgo)
    for i, gg in enumerate(dlgs):
        if i == icon:
            gg[8] += len(new_dlgo)
        elif gg[9] >= 32 * ins:
            gg[9] += shift
    STR[0] = strs
    SHPR[0] = shpr
    SHAP[0] = shap_data
    CTRL[0] = ctrl_data
    DLGO[0] = bytearray(b"".join(struct.pack("<8i", *x) for x in dlgo)); DLGO[1] = len(dlgo)
    DLG[0] = bytearray(b"".join(struct.pack("<16i", *x) for x in dlgs))
    return drb_write(secs)


def drb_icon(raw, icon_id):
    """(texi, u0, v0, u1, v1) of EquIcon_<id>, or None (verification)"""
    secs = drb_read(raw)
    strs = secs["STR\0"][0]
    dlgs = [struct.unpack_from("<16i", secs["DLG\0"][0], 64 * i) for i in range(secs["DLG\0"][1])]
    g = next(x for x in dlgs if _str(strs, x[0]) == "Icon")
    for j in range(g[9] // 32, g[9] // 32 + g[8]):
        d = struct.unpack_from("<8i", secs["DLGO"][0], 32 * j)
        if _str(strs, d[0]) == f"EquIcon_{icon_id:04d}":
            t, off = struct.unpack_from("<ii", secs["SHAP"][0], d[1])
            v = struct.unpack_from("<16h", secs["SHPR"][0], off)
            return (v[12], *v[8:12])
    return None


# ---------------------------------------------------------------------------------------------------- main
def main(kb_dir, tex_dir, menu_dir, out_mod, preview=None, kh2_itempic=None):
    from soulstruct.containers.tpf import TPF
    from soulstruct.dcx import decompress, compress
    tiles = []
    for k, (key, label, fbx, png) in enumerate(ICONS):
        if kh2_itempic:
            im = kh2_icon(kh2_itempic, key)
        else:
            im = render(os.path.join(kb_dir, fbx + ".fbx"), os.path.join(tex_dir, png + ".png"))
        tiles.append((CELL_U0 + CELL_STEP * k, CELL_V0, im))
        print(f"{label}: EquIcon_{ICON_ID[key]:04d} at {SHEET} ({CELL_U0 + CELL_STEP * k}, {CELL_V0})")
    if kh2_itempic:                                   # v119: Drive Form crowns after the Keyblades
        for j, (key, label, colour) in enumerate(DRIVE_ICONS):
            k = len(ICONS) + j
            tiles.append((CELL_U0 + CELL_STEP * k, CELL_V0, crown_icon(kh2_itempic, colour)))
            print(f"{label}: EquIcon_{DRIVE_ICON_ID[key]:04d} at {SHEET} ({CELL_U0 + CELL_STEP * k}, {CELL_V0})")
    if preview:
        sheet = Image.new("RGBA", (ICON_W * len(tiles), ICON_H), (60, 50, 40, 255))
        for k, (_, _, im) in enumerate(tiles):
            sheet.alpha_composite(im, (ICON_W * k, 0))
        sheet.save(preview)
    # atlas
    tpf = TPF.from_path(os.path.join(menu_dir, SHEET_TPF))
    t = next(x for x in tpf.textures if x.stem == SHEET)
    old = bytes(t.data)
    t.data = paint_sheet(old, tiles)
    changed = sum(1 for i in range(0, len(old), 16) if old[i:i + 16] != t.data[i:i + 16])
    os.makedirs(os.path.join(out_mod, "menu"), exist_ok=True)
    tpf.write(os.path.join(out_mod, "menu", SHEET_TPF))
    print(f"{SHEET}: {changed} of {len(old) // 16} DXT blocks re-encoded")
    tiles2 = []
    if kh2_itempic:                                   # v122: item icons on the second sheet
        for j, (key, label, num) in enumerate(ITEM_ICONS):
            tiles2.append((CELL_U0 + CELL_STEP * j, CELL2_V0, itempic_icon(kh2_itempic, num)))
            print(f"{label}: EquIcon_{ITEM_ICON_ID[key]:04d} at {SHEET2} ({CELL_U0 + CELL_STEP * j}, {CELL2_V0})")
        tpf2 = TPF.from_path(os.path.join(menu_dir, SHEET2_TPF))
        t2 = next(x for x in tpf2.textures if x.stem == SHEET2)
        t2.data = paint_sheet(bytes(t2.data), tiles2)
        tpf2.write(os.path.join(out_mod, "menu", SHEET2_TPF))
    # drb
    raw, dcx_type = decompress(open(os.path.join(menu_dir, "menu.drb.dcx"), "rb").read())
    ids = [ICON_ID[k] for k, *_r in ICONS] + ([DRIVE_ICON_ID[k] for k, *_r in DRIVE_ICONS] if kh2_itempic else [])
    ents = [(iid, CELL_U0 + CELL_STEP * i, CELL_V0) for i, iid in enumerate(ids)]
    ents += [(ITEM_ICON_ID[k], CELL_U0 + CELL_STEP * j, CELL2_V0, SHEET2_TEXI) for j, (k, *_r) in enumerate(ITEM_ICONS)] \
        if kh2_itempic else []
    new = drb_add_icons(bytes(raw), ents)
    for iid, u, v, *tx in ents[len(ids):]:
        assert drb_icon(new, iid) == (tx[0], u, v, u + ICON_W, v + ICON_H)
    for i, iid in enumerate(ids):
        assert drb_icon(new, iid) == (SHEET_TEXI, CELL_U0 + CELL_STEP * i, CELL_V0,
                                      CELL_U0 + CELL_STEP * i + ICON_W, CELL_V0 + ICON_H)
    for vid in (0, 204, 3072, 4000, 9999):            # vanilla icons unchanged
        assert drb_icon(new, vid) == drb_icon(bytes(raw), vid), vid
    # the game folder ships both menu.drb.dcx and a loose menu.drb: both are replaced so whichever is read has the icons
    open(os.path.join(out_mod, "menu", "menu.drb"), "wb").write(new)
    open(os.path.join(out_mod, "menu", "menu.drb.dcx"), "wb").write(compress(new, dcx_type))
    chk, _ = decompress(open(os.path.join(out_mod, "menu", "menu.drb.dcx"), "rb").read())
    assert chk == new
    print(f"menu.drb: {len(ents)} icons added ({len(raw)} -> {len(new)} bytes), DCX {dcx_type.name}")
    return new


if __name__ == "__main__":
    main(*sys.argv[1:7])
