"""SoraSouls – the title intro video (movww/frpg_title.bik) with SORA SOULS lettering (v122).
In-game v121: "the starting animation in the title screen still says dark souls – it slowly zooms in and fades in,
then after the animation finishes it says sora souls". The intro is a 9.8 s Bink 1 video (1920x1080, 29.97 fps, no
audio): the DARK SOULS word fades in blurred while zooming, then REMASTERED fades in.

This rebuilds it from the user's own video:
  1. last frame F: warped into the title texture's layout, re-lettered with sora_title.make (SORA cut from the
     game's own DARK/SOULS glyphs), warped back -> difference image D (only the word band changes);
  2. every frame i: the word band is modelled as gain * blur(zoom(F)) about the frame centre; zoom, blur and gain are
     fitted per frame (least squares on a 1/4-size copy) and the same transform applied to D: new_i = frame_i + T_i(D);
  3. frames are written as PNGs + a lossless AVI. Bink encoding needs RAD Game Tools' free "RAD Video Tools" (no open
     encoder exists); the user converts the AVI to frpg_title.bik (Bink 1, 1920x1080, 29.97 fps) on their PC.
Usage: python sora_title_movie.py <frpg_title.bik> <ENGLISH/menu_local.tpf.dcx (vanilla)> <out dir>
"""
import io, os, subprocess, sys
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, affine_transform

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sora_title

W_ROWS = (330, 622)          # frame rows holding the DARK SOULS word incl. zoom margin (REMASTERED starts at ~632)
CX, CY = 960.0, 540.0        # zoom centre (frame centre)


def word_features(L, band):
    """first/last letter column, word top and streak row of luminance image L inside rows band"""
    b = L[band[0]:band[1]]
    prof = (b > 100).sum(1)
    streak = band[0] + int(np.mean([y for y in range(len(prof)) if prof[y] > 0.55 * L.shape[1]]))
    bb = b.copy(); bb[streak - 4 - band[0]:streak + 5 - band[0]] = 0
    col = (bb > 80).sum(0); runs, inr = [], False
    for x, v in enumerate(col):
        if v > 3 and not inr: s0, inr = x, True
        elif v <= 3 and inr: runs.append((s0, x)); inr = False
    runs = [r for r in runs if r[1] - r[0] > 30]
    top = band[0] + int(np.where((bb > 60).sum(1) > 20)[0][0])
    return runs[0][0], runs[-1][1], top, streak


def relettered_last_frame(F, tex_png):
    """F (H,W,3) uint8 -> F' with SORA SOULS, via the title texture's coordinate system"""
    tex = np.asarray(Image.open(io.BytesIO(tex_png)).convert("RGBA")).astype(float)
    tl = tex[..., :3].mean(2) * tex[..., 3] / 255
    t0, t1, ttop, tst = word_features(tl, (60, 320))
    fl = F.astype(float).mean(2)
    f0, f1, ftop, fst = word_features(fl, (380, 620))
    sx = (f1 - f0) / (t1 - t0); sy = (fst - ftop) / (tst - ttop)
    # texture (u, v) -> frame (x, y): x = f0 + (u - t0) * sx, y = ftop + (v - ttop) * sy
    th, tw = tex.shape[:2]
    Fw = np.zeros((th, tw, 4))
    for c in range(3):
        Fw[..., c] = affine_transform(F[..., c].astype(float), [sy, sx], offset=[ftop - ttop * sy, f0 - t0 * sx],
                                      output_shape=(th, tw), order=1)
    Fw[..., 3] = 255
    buf = io.BytesIO(); Image.fromarray(np.clip(Fw, 0, 255).astype(np.uint8), "RGBA").save(buf, "PNG")
    Nw = np.asarray(sora_title.make(buf.getvalue())).astype(float)
    Dw = Nw[..., :3] - Fw[..., :3]
    H, Wd = F.shape[:2]
    D = np.zeros((H, Wd, 3))
    for c in range(3):                                   # frame -> texture is the inverse map
        D[..., c] = affine_transform(Dw[..., c], [1 / sy, 1 / sx], offset=[ttop - ftop / sy, t0 - f0 / sx],
                                     output_shape=(H, Wd), order=1, cval=0)
    D[:W_ROWS[0]] = 0; D[W_ROWS[1]:] = 0
    return D, (sx, sy, f0, ftop)


def zoom_blur(img, s, sigma):
    """zoom by s about (CX, CY) then gaussian blur (sigma in pixels of img)"""
    out = np.empty_like(img)
    for c in range(img.shape[2]):
        z = affine_transform(img[..., c], [1 / s, 1 / s], offset=[CY - CY / s, CX - CX / s], order=1)
        out[..., c] = gaussian_filter(z, sigma) if sigma > 0 else z
    return out


def fit_frame(Fs, Gs, prev=None):
    """Fs, Gs: 1/4-size luminance word bands (final frame, frame i) -> (s, sigma, gain, err)"""
    best = None
    ss = np.arange(0.96, 1.20, 0.005)
    sig = [0, 0.5, 1, 1.5, 2, 3, 4, 5, 6, 8, 10]
    for s in ss:
        z = affine_transform(Fs, [1 / s, 1 / s], offset=[CYs - CYs / s, CXs - CXs / s], order=1)
        for sg in sig:
            m = gaussian_filter(z, sg) if sg else z
            den = (m * m).sum()
            g = (m * Gs).sum() / den if den > 0 else 0.0
            e = ((g * m - Gs) ** 2).sum()
            if best is None or e < best[3]:
                best = (s, sg * 4, g, e)
    return best


def refine(Fs, Gs, s0, sg0):
    """finer zoom (0.0005) and blur (0.25 px at 1/4 size) around a coarse fit"""
    best = None
    for s in np.arange(s0 - 0.005, s0 + 0.0051, 0.0005):
        z = affine_transform(Fs, [1 / s, 1 / s], offset=[CYs - CYs / s, CXs - CXs / s], order=1)
        for sg in np.arange(max(0, sg0 / 4 - 0.75), sg0 / 4 + 0.76, 0.25):
            m = gaussian_filter(z, sg) if sg > 0 else z
            den = (m * m).sum(); g = (m * Gs).sum() / den if den > 0 else 0.0
            e = ((g * m - Gs) ** 2).sum()
            if best is None or e < best[3]:
                best = (s, sg * 4, g, e)
    return best


def smooth(x, idx, deg):
    """least-squares polynomial through the fitted frames (removes per-frame fitting jitter)"""
    p = np.polyfit(idx, x, deg)
    return np.polyval(p, idx)


def main(bik, local_tpf, out_dir):
    from soulstruct.containers.tpf import TPF
    global CXs, CYs
    fr = os.path.join(out_dir, "frames_orig"); nf = os.path.join(out_dir, "frames")
    os.makedirs(fr, exist_ok=True); os.makedirs(nf, exist_ok=True)
    if not os.listdir(fr):
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", bik, os.path.join(fr, "f%04d.png")], check=True)
    names = sorted(os.listdir(fr))
    F = np.asarray(Image.open(os.path.join(fr, names[-1])).convert("RGB"))
    tex = next(x for x in TPF.from_path(local_tpf).textures if x.stem == "Title")
    D, fitinfo = relettered_last_frame(F, bytes(tex.data))
    print("texture->frame scale/offset", [round(v, 3) for v in fitinfo])
    band = slice(W_ROWS[0], W_ROWS[1])
    Fnew_band = np.clip(F.astype(float) + D, 0, 255)[band]
    Fs = F.astype(float).mean(2)[band][::4, ::4]
    CXs, CYs = CX / 4, (CY - W_ROWS[0]) / 4
    # 1) fit zoom / blur / gain per frame (cached: the fit takes minutes)
    cache = os.path.join(out_dir, "fits.npy")
    if os.path.exists(cache):
        fits = [None if r[0] < 0 else tuple(r) for r in np.load(cache)]
    else:
        fits = []
        for k, n in enumerate(names):
            G = np.asarray(Image.open(os.path.join(fr, n)).convert("RGB")).astype(float)
            Gs = G.mean(2)[band][::4, ::4]
            if Gs.max() < 4:
                fits.append(None); continue
            s, sg, g, e = fit_frame(Fs, Gs)
            s, sg, g, e = refine(Fs, Gs, s, sg)
            fits.append((s, sg, g, float(e / max((Gs * Gs).sum(), 1e-9))))
        np.save(cache, np.array([f if f else (-1, -1, -1, -1) for f in fits], float))
    idx = np.array([k for k, f in enumerate(fits) if f is not None])
    S = np.array([fits[k][0] for k in idx]); SG = np.array([fits[k][1] for k in idx]); GN = np.array([fits[k][2] for k in idx])
    # 2) smooth over time (Savitzky-Golay, window 31): removes per-frame fitting jitter without any jump where the
    #    animation comes to rest (the v122 first try forced rest values from one frame on -> visible pop)
    from scipy.signal import savgol_filter
    Ss = savgol_filter(S, 31, 2, mode="interp")
    SGs = np.clip(savgol_filter(SG, 31, 2, mode="interp"), 0, None)
    GNs = np.clip(savgol_filter(GN, 31, 2, mode="interp"), 0, None)
    rest = idx[-1]
    # 3) render: the word band is replaced by the same transform of the re-lettered last frame
    log = []
    for j, k in enumerate(idx):
        pass
    sm = {int(k): (Ss[j], SGs[j], GNs[j]) for j, k in enumerate(idx)}
    for k, n in enumerate(names):
        G = np.asarray(Image.open(os.path.join(fr, n)).convert("RGB")).astype(float)
        if k in sm:
            s, sg, g = sm[k]
            G[band] = np.clip(g * zoom_blur_band(Fnew_band, s, sg), 0, 255)
            log.append(f"{n} zoom {s:.4f} blur {sg:.2f} gain {g:.3f} fit-error {fits[k][3]:.4f}")
        else:
            log.append(f"{n} black")
        Image.fromarray(G.astype(np.uint8)).save(os.path.join(nf, n))
    with open(os.path.join(out_dir, "fit_log.txt"), "w") as f:
        f.write("\n".join(log))
    print("rest from frame", rest, "; sample:", log[30], "|", log[120], "|", log[-1])
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", "30000/1001", "-i",
                    os.path.join(nf, "f%04d.png"), "-c:v", "utvideo", "-pix_fmt", "rgb24",
                    os.path.join(out_dir, "frpg_title_sorasouls.avi")], check=True)
    print("wrote", os.path.join(out_dir, "frpg_title_sorasouls.avi"))


def zoom_blur_band(Dband, s, sigma):
    """zoom/blur the word band of D about the frame centre (band starts at W_ROWS[0])"""
    out = np.empty_like(Dband)
    cy = CY - W_ROWS[0]
    for c in range(3):
        z = affine_transform(Dband[..., c], [1 / s, 1 / s], offset=[cy - cy / s, CX - CX / s], order=1)
        out[..., c] = gaussian_filter(z, sigma) if sigma > 0 else z
    return out


if __name__ == "__main__":
    main(*sys.argv[1:4])
