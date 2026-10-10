r"""SoraSouls – read Sora's battle voice clips from the player's own KH2 voice files (.win32.scd), v127.

SCD (Square Enix sound container, KH 1.5+2.5 PC): stream headers (0x20 bytes: stream size, channels, sample rate,
codec, loop start/end, extra-data size, aux chunk count); codec 6 = Ogg Vorbis. After the header: a codec block
(byte 0 version, byte 2 XOR key, +0x10 seek table size, +0x14 Vorbis header size, then seek table, then the Vorbis
header pages – XOR-ed with the key when version is 2), then the audio pages. Header + audio = a normal .ogg file.

  python kh2_voice.py list <scd> <out dir>        writes every clip as NN.ogg (to pick one by ear)
"""
import os, struct, sys

RATES = (22050, 24000, 32000, 44100, 48000)


def clips(path):
    d = open(path, "rb").read()
    out = []
    for o in range(0, len(d) - 0x20, 4):
        size, ch, rate, codec, ls, le, extra, aux = struct.unpack_from("<iiiiiiii", d, o)
        if not (rate in RATES and codec == 6 and 0 < ch <= 2 and 0 < size < len(d) and aux == 0 and 0 < extra < 0x10000):
            continue
        c = o + 0x20
        ver, key = d[c], d[c + 2]
        seek_sz, vh_sz = struct.unpack_from("<II", d, c + 0x10)
        vh = d[c + 0x20 + seek_sz: c + 0x20 + seek_sz + vh_sz]
        if ver == 2 and key:
            vh = bytes(b ^ key for b in vh)
        if not vh.startswith(b"OggS"):
            continue
        audio = d[c + extra: c + extra + size]
        out.append(dict(offset=o, rate=rate, channels=ch, ogg=vh + audio))
    return out


if __name__ == "__main__":
    cmd, src, dst = sys.argv[1:4]
    os.makedirs(dst, exist_ok=True)
    for k, c in enumerate(clips(src)):
        open(os.path.join(dst, f"{k:02d}.ogg"), "wb").write(c["ogg"])
    print(len(clips(src)), "clips written to", dst)
