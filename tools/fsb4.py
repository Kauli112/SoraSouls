r"""SoraSouls – replace a sample in a Dark Souls Remastered FMOD Ex sound bank (.fsb, FSB4), v127.

Layout (worked out on frpg_main.fsb, 279 samples): 48-byte header ("FSB4", sample count, sample-header size, data
size, version 0x40000, mode 0x40), then one 80-byte header per sample (size, 30-byte name, length in samples,
compressed bytes, loop start/end, mode, frequency, ...), then the sample data back to back, each sample's data a
multiple of 32 bytes. Samples are MPEG audio (mode 0x10100220; voice samples MPEG-2 Layer III, 22050 Hz, mono);
bank mode 0x40 = every MPEG frame padded to a multiple of 4 bytes.
A replacement keeps the sample's index, name, frequency and channel count, so the event file (.fev) that plays it
needs no change.

  python fsb4.py list <bank.fsb>
  python fsb4.py replace <bank.fsb> <out.fsb> <sample name> <audio file> [<sample name> <audio file> ...]
"""
import struct, sys
import numpy as np

HDR, SHDR = 48, 80


def read(path):
    d = bytearray(open(path, "rb").read())
    if d[:4] != b"FSB4":
        raise ValueError(f"{path}: not an FSB4 bank")
    n, shdr_size, data_size = struct.unpack_from("<III", d, 4)
    samples, o, off = [], HDR, HDR + shdr_size
    for i in range(n):
        sz = struct.unpack_from("<H", d, o)[0]
        if sz != SHDR:
            raise ValueError(f"sample {i}: header size {sz} (only {SHDR}-byte headers supported)")
        name = bytes(d[o + 2:o + 32]).split(b"\0")[0].decode("latin1")
        length, csize = struct.unpack_from("<II", d, o + 32)
        freq = struct.unpack_from("<i", d, o + 52)[0]
        ch = struct.unpack_from("<H", d, o + 62)[0]
        samples.append(dict(name=name, header=bytes(d[o:o + sz]), length=length, freq=freq, channels=ch,
                            data=bytes(d[off:off + csize])))
        o += sz; off += csize
    return bytes(d[:HDR]), samples


def mpeg_frames(mp3):
    """split an MPEG audio stream into frames (MPEG-1/2 Layer III)"""
    BR = {1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
          2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]}
    SR = {1: [44100, 48000, 32000], 2: [22050, 24000, 16000]}
    frames, i = [], 0
    while i + 4 <= len(mp3):
        if mp3[i] != 0xFF or (mp3[i + 1] & 0xE0) != 0xE0:
            i += 1
            continue
        ver = 1 if mp3[i + 1] & 0x08 else 2
        bri, sri, pad = mp3[i + 2] >> 4, (mp3[i + 2] >> 2) & 3, (mp3[i + 2] >> 1) & 1
        if bri in (0, 15) or sri == 3:
            i += 1
            continue
        size = (144 if ver == 1 else 72) * BR[ver][bri] * 1000 // SR[ver][sri] + pad
        frames.append(mp3[i:i + size])
        i += size
    return frames


def encode(audio_path, freq, channels):
    """audio file -> (MPEG data padded per frame to 4 bytes and in total to 32, length in samples)"""
    import soundfile as sf, lameenc
    a, rate = sf.read(audio_path, dtype="float32", always_2d=True)
    a = a.mean(1, keepdims=True) if channels == 1 else np.repeat(a[:, :1], 2, 1) if a.shape[1] == 1 else a[:, :2]
    if rate != freq:                                   # linear resample (short voice clips)
        t = np.arange(int(len(a) * freq / rate)) * rate / freq
        a = np.stack([np.interp(t, np.arange(len(a)), a[:, c]) for c in range(a.shape[1])], 1).astype(np.float32)
    pcm = (np.clip(a, -1, 1) * 32767).astype("<i2")
    enc = lameenc.Encoder()
    enc.set_bit_rate(64 if freq < 32000 else 128); enc.set_in_sample_rate(freq); enc.set_channels(channels)
    enc.set_quality(2)
    mp3 = enc.encode(pcm.tobytes()) + enc.flush()
    frames = mpeg_frames(mp3)
    out = b"".join(f + bytes(-len(f) % 4) for f in frames)
    # length = decoded frames x samples per frame, as in the game's own samples (voice-m-dead: 56 x 576 = 32256)
    per = 1152 if frames and frames[0][1] & 0x08 else 576
    return out + bytes(-len(out) % 32), len(frames) * per


def replace(src, dst, pairs):
    head, samples = read(src)
    for name, audio in pairs:
        s = next((x for x in samples if x["name"] == name), None)
        if s is None:
            raise KeyError(f"{src}: no sample {name}")
        s["data"], s["length"] = encode(audio, s["freq"], s["channels"])
        h = bytearray(s["header"])
        struct.pack_into("<IIII", h, 32, s["length"], len(s["data"]), 0, max(s["length"] - 1, 0))
        s["header"] = bytes(h)
        print(f"{name}: {s['length']} samples, {len(s['data'])} bytes ({s['freq']} Hz, {s['channels']} ch)")
    head = bytearray(head)
    struct.pack_into("<III", head, 4, len(samples), sum(len(x["header"]) for x in samples),
                     sum(len(x["data"]) for x in samples))
    with open(dst, "wb") as f:
        f.write(head)
        for x in samples:
            f.write(x["header"])
        for x in samples:
            f.write(x["data"])


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "list":
        for i, s in enumerate(read(sys.argv[2])[1]):
            print(i, s["name"], s["length"], len(s["data"]), s["freq"], s["channels"])
    else:
        a = sys.argv[4:]
        replace(sys.argv[2], sys.argv[3], list(zip(a[0::2], a[1::2])))
