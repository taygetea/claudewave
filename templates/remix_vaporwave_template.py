"""
VAPORWAVE REMIX TEMPLATE.

A ready-to-adapt pipeline that:
  1. Slows the track 20-25% (classic screw).
  2. Replaces bass/drums/other with programmatic synths, keeping vocals.
  3. Adds chopped hook loops (eccojams style) at chorus moments.
  4. Optional ACE-Step AI pad for atmosphere.
  5. Heavy chorus+phaser+tape delay+shimmer hall on everything.

Adapt the constants at the top for your song. You'll need to have already:
  - run demucs to get work/htdemucs/<song>/{vocals,bass,drums,other}.wav
  - run basic-pitch (see transcribe templates) to get bass_notes.json and chords
  - optionally queued an ACE-Step pad to comfyui output
"""
import os, math, json, random, glob
import numpy as np
from scipy import signal
from pedalboard import (
    Pedalboard, Chorus, Phaser, Reverb, Delay, LowpassFilter, HighpassFilter,
    Compressor, Gain, HighShelfFilter, LowShelfFilter, Distortion,
)
from claudewave.lib import synths, drums, dsp, analysis, choppers, ace_step

# ================= CONFIGURE PER SONG =================
SONG_NAME       = "your_song"
STEMS_DIR       = f"work/htdemucs/{SONG_NAME}"
BASS_NOTES_JSON = f"work/{SONG_NAME}_bass_notes.json"
CHORDS_JSON     = f"work/{SONG_NAME}_chords.json"
ACE_PAD_GLOB    = f"C:/Users/you/ComfyUI/output/{SONG_NAME}_pad*.flac"
OUT_WAV         = f"work/{SONG_NAME}_vaporwave.wav"
SR              = 44100
SLOW_RATIO      = 0.80          # 20% slow -> ~-3.86 semitones
PITCH_MULT      = SLOW_RATIO
# Original BPM of the song (from librosa beat_track on the full mix)
ORIGINAL_BPM    = 96.0
BPM             = ORIGINAL_BPM * SLOW_RATIO

# Chopped hook: (start_s, end_s) in the ORIGINAL (pre-slow) timeline
HOOK_ORIG = (17.25, 25.60)
# Where to drop echoing copies in the SLOWED timeline:
# (start_s, n_copies, stagger_s)
HOOK_DROPS = [(70.0, 2, 3.5), (135.0, 3, 4.5), (200.0, 3, 5.0)]

random.seed(42); np.random.seed(42)

# ================= PIPELINE =================
def main():
    # Load stems
    vocals = dsp.load_stereo(f"{STEMS_DIR}/vocals.wav", SR)
    inst   = dsp.load_stereo(f"{STEMS_DIR}/no_vocals.wav", SR)

    # Screw everything
    vocals_s = dsp.resample_rate(vocals, SLOW_RATIO)
    inst_s   = dsp.resample_rate(inst, SLOW_RATIO)

    # Tape wobble
    vocals_s = dsp.tape_wobble(vocals_s, SR, rate_hz=0.23, depth=32)
    inst_s   = dsp.tape_wobble(inst_s, SR, rate_hz=0.18, depth=48)
    vocals_s = dsp.rms_normalize(vocals_s, -14.0)
    inst_s   = dsp.rms_normalize(inst_s, -16.0)

    # Chopped hook
    hook_start_slowed = HOOK_ORIG[0] * (1/SLOW_RATIO)
    hook_end_slowed   = HOOK_ORIG[1] * (1/SLOW_RATIO)
    hook_chunk = choppers.extract_hook(vocals_s, hook_start_slowed, hook_end_slowed, SR)
    hook_chunk = Pedalboard([
        HighpassFilter(cutoff_frequency_hz=120),
        Chorus(rate_hz=0.5, depth=0.5, centre_delay_ms=12, feedback=0.2, mix=0.5),
        Delay(delay_seconds=0.7, feedback=0.6, mix=0.5),
        Reverb(room_size=0.97, damping=0.2, wet_level=0.85, dry_level=0.2),
        LowpassFilter(cutoff_frequency_hz=4800),
    ])(hook_chunk, SR)

    # Vocals — dreamy but still intelligible
    vocals_s = Pedalboard([
        HighpassFilter(cutoff_frequency_hz=90),
        Chorus(rate_hz=0.55, depth=0.3, centre_delay_ms=8, feedback=0.1, mix=0.25),
        Delay(delay_seconds=0.40, feedback=0.35, mix=0.22),
        Reverb(room_size=0.88, damping=0.32, wet_level=0.35, dry_level=0.85),
    ])(vocals_s, SR)

    # Instrumental — heavy -wave treatment
    inst_wet = Pedalboard([
        Chorus(rate_hz=0.32, depth=0.7, centre_delay_ms=15, feedback=0.28, mix=0.6),
        Phaser(rate_hz=0.12, depth=0.85, centre_frequency_hz=500, feedback=0.45, mix=0.5),
        Delay(delay_seconds=0.65, feedback=0.52, mix=0.38),
        Reverb(room_size=0.97, damping=0.3, wet_level=0.7, dry_level=0.0),
        LowpassFilter(cutoff_frequency_hz=5800),
    ])(inst_s, SR)
    inst_dry = Pedalboard([
        HighpassFilter(cutoff_frequency_hz=60),
        LowpassFilter(cutoff_frequency_hz=8200),
        Distortion(drive_db=3.0),
        Compressor(threshold_db=-18, ratio=2.0),
    ])(inst_s, SR)
    inst_s = (0.5*inst_dry + 1.0*inst_wet).astype(np.float32)
    inst_s = dsp.sidechain_pump(inst_s, SR, bpm=BPM, depth=0.12)

    # ACE atmosphere layer
    ace_layer = None
    cands = sorted(glob.glob(ACE_PAD_GLOB), key=os.path.getmtime)
    if cands:
        ace = dsp.load_stereo(cands[-1], SR)
        ace = dsp.resample_rate(ace, SLOW_RATIO)
        ace = dsp.tape_wobble(ace, SR, rate_hz=0.12, depth=28)
        ace_layer = Pedalboard([
            HighpassFilter(cutoff_frequency_hz=90),
            Phaser(rate_hz=0.06, depth=0.7, centre_frequency_hz=400, feedback=0.4, mix=0.35),
            Reverb(room_size=0.95, damping=0.4, wet_level=0.45, dry_level=0.55),
            LowpassFilter(cutoff_frequency_hz=5000),
        ])(ace, SR)

    # Align + mix
    target_n = max(vocals_s.shape[0], inst_s.shape[0],
                   0 if ace_layer is None else ace_layer.shape[0])

    vocals_s = dsp.pad_to(vocals_s, target_n)
    inst_s   = dsp.pad_to(inst_s, target_n)
    if ace_layer is not None: ace_layer = dsp.pad_to(ace_layer, target_n)

    hook_layer = choppers.place_hook_loops(target_n, SR, hook_chunk, HOOK_DROPS)

    mix = 1.25*vocals_s + 0.80*inst_s + 0.55*hook_layer
    if ace_layer is not None: mix += 0.25*ace_layer

    # Vinyl + hiss
    mix += 0.30 * dsp.pad_to(dsp.vinyl_crackle(target_n/SR, SR, density=90, level=0.03), target_n)

    # Master
    mix = Pedalboard([
        LowShelfFilter(cutoff_frequency_hz=130, gain_db=1.5),
        HighShelfFilter(cutoff_frequency_hz=9000, gain_db=0.8),
        Compressor(threshold_db=-18, ratio=2.0, attack_ms=25, release_ms=220),
        Distortion(drive_db=1.5),
        Gain(gain_db=-1.5),
    ])(mix.astype(np.float32), SR)

    mix = dsp.mix_fades(mix, SR, fade_in_s=3.0, fade_out_s=8.0)
    mix = dsp.limit_peak(mix, 0.97)

    import soundfile as sf
    sf.write(OUT_WAV, mix, SR, subtype='PCM_16')
    print(f"Wrote {OUT_WAV}")

if __name__ == "__main__":
    main()
