r"""SoraSouls – Sora's KH2 voice in Dark Souls (v127). User 2026-10-10: replace the death scream with Sora's own KH2
voice, and play his KH2 lines when he casts Fire, Blizzard, Thunder and Cure.

Clips come from the player's own KH2 voice file voice\us\battle\tt0_sora.win32.scd (tools/kh2_voice.py); the user
picked them by ear: death 03, Fire 11, Blizzard 12, Thunder 13, Cure 14.
  * Death: sound\frpg_main.fsb (the player's own copy) with the male death voices voice-m-dead.wav and
    voice-mx-dead.wav replaced (tools/fsb4.py). Same index/name, so the game's event file still finds them.
    Note: the same voice is used by every male character.
  * Casting: mod\sora_voice\fire|blizzard|thunder|cure.wav, played by the add-on DLL (v82+) when a Sora spell is cast;
    death.wav, played by the add-on (v83+) when Sora's HP reaches 0 (in-game v82 the bank swap seemed not to apply).

  python sora_sounds.py <KH2 voice\us\battle dir> <DSR game dir> <out mod dir>
"""
import io, os, sys, tempfile
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fsb4, kh2_voice  # noqa: E402

SCD = "tt0_sora.win32.scd"
CLIPS = {"death": 3, "fire": 11, "blizzard": 12, "thunder": 13, "cure": 14}
DEATH_SAMPLES = ("voice-m-dead.wav", "voice-mx-dead.wav", "voice-m-fallindead.wav", "voice-mx-fallindead.wav")


def build(voice_dir, game, mod):
    clips = kh2_voice.clips(os.path.join(voice_dir, SCD))
    if len(clips) != 31:
        raise RuntimeError(f"{SCD}: {len(clips)} clips (expected 31) – a different KH2 version?")
    out = os.path.join(mod, "sora_voice")
    os.makedirs(out, exist_ok=True)
    wavs = {}
    for name, k in CLIPS.items():
        data, rate = sf.read(io.BytesIO(clips[k]["ogg"]))
        p = os.path.join(out, f"{name}.wav")             # death.wav too: the add-on plays it as well (v83)
        sf.write(p, data, rate, subtype="PCM_16")
        wavs[name] = p
    os.makedirs(os.path.join(mod, "sound"), exist_ok=True)
    fsb4.replace(os.path.join(game, "sound", "frpg_main.fsb"), os.path.join(mod, "sound", "frpg_main.fsb"),
                 [(s, wavs["death"]) for s in DEATH_SAMPLES])
    print("wrote", out, "and sound\\frpg_main.fsb")


if __name__ == "__main__":
    build(*sys.argv[1:4])
