"""SoraSouls – title logo "SORA SOULS / REMASTERED" made from the game's own title lettering (v117).
User: "change the title text from Dark Souls Remastered to SoraSouls Remastered in their style".

The title screen logo is the texture Title (menu_0.tpf) / Title_r (menu_4.tpf), 2048x640 DXT5: "DARK SOULS", a light
streak through it, "REMASTERED" below (plus an unused "NETWORK TEST VER." banner). Every letter of "SORA" already
exists in that artwork: S and O from SOULS, R and A from DARK. This cuts those glyphs out of the user's own texture
along minimum-ink seams (letters touch at their serifs), lays out "SORA SOULS" centred where "DARK SOULS" was, redraws
the streak across the word band, and drops the trademark sign (it belongs to the original name). "REMASTERED" and the
rest of the texture are untouched.
Usage: python sora_title.py <game menu dir> <out mod dir> [preview.png]
"""
import io, os, sys
import numpy as np
from PIL import Image

# Reference layout (measured on menu_0 Title, 2048x640). v121 (in-game v120: "the title screen still says dark souls"):
# the title screen actually shows the per-language copy menu/<LANG>/menu_local.tpf "Title" (2048x512), whose lettering
# sits a few pixels off (x' ~ 0.994 x + 18, y' ~ y - 3). Every coordinate below is mapped through the layout measured
# on the texture being edited (first/last letter columns, word top, streak row).
REF = dict(x0=249, x1=1780, top=86, streak=185)
BAND = (80, 296)                 # rows of the "DARK SOULS" word (REMASTERED starts below 330)
STREAK = (182, 189)              # rows of the light streak through the word
SPAN = (225, 1840)               # columns of the word (+ trademark sign)
GAP = 60                         # space between SORA and SOULS (px)


def measure(img):
    lum = img[..., :3].mean(2) * img[..., 3] / 255.0
    prof = (lum[60:320] > 100).sum(1)
    streak = 60 + int(np.mean([y for y in range(len(prof)) if prof[y] > 1200]))
    band = lum[90:300].copy(); band[streak - 3 - 90:streak + 4 - 90] = 0
    col = (band > 80).sum(0); runs, inr = [], False
    for x, v in enumerate(col):
        if v > 3 and not inr: s0, inr = x, True
        elif v <= 3 and inr: runs.append((s0, x)); inr = False
    runs = [r for r in runs if r[1] - r[0] > 30]
    top = int(np.where((lum[:330] > 60).sum(1) > 20)[0][0])
    return dict(x0=runs[0][0], x1=runs[-1][1], top=top, streak=streak)


def seam(lum, x0, x1, streak):
    """minimum-ink top-to-bottom path in columns [x0, x1) of lum (band rows) -> x per row"""
    c = lum[:, x0:x1].copy()
    c[streak[0]:streak[1]] = 0                                   # the streak is redrawn anyway
    h, w = c.shape
    acc = c.copy(); back = np.zeros((h, w), int)
    for y in range(1, h):
        prev = acc[y - 1]
        cand = np.stack([np.r_[np.inf, prev[:-1]], prev, np.r_[prev[1:], np.inf]])
        k = cand.argmin(0)
        acc[y] += cand[k, np.arange(w)]
        back[y] = np.arange(w) + k - 1
    xs = np.zeros(h, int); xs[-1] = int(acc[-1].argmin())
    for y in range(h - 1, 0, -1):
        xs[y - 1] = back[y, xs[y]]
    return xs + x0


def make(title_png_bytes):
    img = np.asarray(Image.open(io.BytesIO(title_png_bytes)).convert("RGBA")).copy()
    m = measure(img)
    sx = (m["x1"] - m["x0"]) / (REF["x1"] - REF["x0"])
    sy = (m["streak"] - m["top"]) / (REF["streak"] - REF["top"])
    X = lambda c: int(round(m["x0"] + (c - REF["x0"]) * sx))
    Y = lambda r: int(round(m["top"] + (r - REF["top"]) * sy))
    b0, b1 = Y(BAND[0]), min(Y(BAND[1]), img.shape[0])
    st = (Y(STREAK[0]) - b0, Y(STREAK[1]) - b0)                   # streak rows inside the band
    lum = img[..., :3].mean(2) * img[..., 3] / 255.0
    band = lum[b0:b1]

    def glyph(left, right):
        h = b1 - b0
        L = np.full(h, left) if np.isscalar(left) else left
        R = np.full(h, right) if np.isscalar(right) else right
        x0, x1 = int(L.min()), int(R.max())
        g = img[b0:b1, x0:x1].copy()
        keep = (np.arange(x0, x1)[None, :] >= L[:, None]) & (np.arange(x0, x1)[None, :] < R[:, None])
        g[~keep] = 0
        return g, x0

    ar = seam(band, X(560), X(690), st)          # A | R (R's top serif reaches over A's right foot)
    rk = seam(band, X(745), X(780), st)          # R | K
    da = seam(band, X(425), X(455), st)          # D | A
    ou = seam(band, X(1318), X(1350), st)        # O | U
    S1, _ = glyph(X(1004), X(1136))
    O1, _ = glyph(X(1136), ou)
    R1, _ = glyph(ar, rk)
    A1, _ = glyph(da, ar)
    SOULS, xsouls = glyph(X(1004), X(1812))                       # S O U L S
    SOULS[:Y(110) - b0, X(1790) - xsouls:] = 0                    # trademark sign (top right) dropped
    parts = [S1, O1, R1, A1]
    widths = sum(p.shape[1] for p in parts) - 3 * 6 + GAP + SOULS.shape[1]
    centre = (X(233) + X(1806)) / 2
    x = int(round(centre - widths / 2))
    out = img.copy()
    # clear the word band: the texture has a dark, partly opaque backdrop behind the lettering and the streak runs
    # through it – each row is refilled with what lies just outside the word
    s0, s1 = X(SPAN[0]), min(X(SPAN[1]), img.shape[1] - 6)
    for y in range(b0, b1):
        lc, rc = img[y, s0 - 6:s0].mean(0), img[y, s1:s1 + 6].mean(0)
        t = np.linspace(0, 1, s1 - s0)[:, None]
        out[y, s0:s1] = np.round(lc * (1 - t) + rc * t).astype(np.uint8)

    def paste(g, x):
        h, w = g.shape[:2]
        dst = out[b0:b0 + h, x:x + w]
        lm = lambda p: p[..., :3].astype(float).mean(-1) * p[..., 3] / 255.0
        take = lm(g) > lm(dst)                                     # brighter wins (letters over the dark backdrop)
        dst[take] = g[take]

    for p in parts:
        paste(p, x); x += p.shape[1] - 6
    x += 6 + GAP
    paste(SOULS, x)
    return Image.fromarray(out, "RGBA")


def main(menu_dir, out_mod, preview=None):
    from soulstruct.containers.tpf import TPF
    os.makedirs(os.path.join(out_mod, "menu"), exist_ok=True)
    for tpf_name, stem in (("menu_0.tpf.dcx", "Title"), ("menu_4.tpf.dcx", "Title_r"),
                           (os.path.join("ENGLISH", "menu_local.tpf.dcx"), "Title")):   # v121: the one shown
        src = os.path.join(out_mod, "menu", tpf_name)
        if not os.path.exists(src):                          # menu_0 may already carry the Keyblade icons
            src = os.path.join(menu_dir, tpf_name)
        tpf = TPF.from_path(src)
        t = next(x for x in tpf.textures if x.stem == stem)
        mips = int.from_bytes(t.data[28:32], "little")
        im = make(bytes(t.data))
        buf = io.BytesIO(); im.save(buf, "DDS", pixel_format="DXT5")
        t.data = buf.getvalue()                              # one mip level (the logo is shown at full size)
        os.makedirs(os.path.dirname(os.path.join(out_mod, "menu", tpf_name)), exist_ok=True)
        tpf.write(os.path.join(out_mod, "menu", tpf_name))
        print(f"{stem} ({tpf_name}): SORA SOULS logo written (vanilla had {mips} mips)")
        if preview and "local" in tpf_name:
            bg = Image.new("RGBA", im.size, (20, 20, 20, 255)); bg.alpha_composite(im)
            bg.convert("RGB").resize((1024, 320)).save(preview)


if __name__ == "__main__":
    main(*sys.argv[1:4])
