"""
CITYPOP REMIX TEMPLATE — full rebuild from 4-stem + per-instrument MIDI.

The key move: REPLACE drums, bass, and 'other' (piano/strings) with programmatic
synth voices playing the song's actual chords at the song's actual beat times.
Only the vocals remain from the source. Result is a proper cover, not a
layer-over.

Critical rule: drums + bass + rhodes comp ALL ride the librosa.beat_track grid,
NOT basic-pitch note onsets (which have ~50ms error and cause cacophony).

Requires:
  - 4-stem demucs output at work/htdemucs/<song>/{vocals,bass,drums,other}.wav
  - A chord-windows JSON (from analysis.detect_chords_from_notes)
  - Optional: ACE-Step citypop pad
"""
import os, math, json, random, glob
import numpy as np
import librosa
from scipy import signal
from pedalboard import (
    Pedalboard, Chorus, Phaser, Reverb, Delay, LowpassFilter, HighpassFilter,
    Compressor, Gain, HighShelfFilter, LowShelfFilter,
)
from claudewave.lib import synths, drums, dsp, analysis

# ================= CONFIGURE =================
SONG_NAME       = "your_song"
STEMS_DIR       = f"work/htdemucs/{SONG_NAME}"
CHORDS_JSON     = f"work/{SONG_NAME}_chords.json"
ACE_PAD_GLOB    = f"C:/Users/you/ComfyUI/output/{SONG_NAME}_citypop_pad*.flac"
OUT_WAV         = f"work/{SONG_NAME}_citypop.wav"
SR              = 44100
SLOW_RATIO      = 0.96          # subtle tape slow (~-0.7 st)
PITCH_MULT      = SLOW_RATIO
MIDI_STRETCH    = 1.0 / SLOW_RATIO

random.seed(42); np.random.seed(42)


def main():
    # 1) Vocals + beat grid
    vocals = dsp.load_stereo(f"{STEMS_DIR}/vocals.wav", SR)
    tempo, beat_times_orig = analysis.beat_track(f"{STEMS_DIR}/no_vocals.wav")
    beat_times = beat_times_orig * (1.0 / SLOW_RATIO)
    print(f"tempo ~{tempo:.1f} BPM, {len(beat_times)} beats")

    vocals_s = dsp.resample_rate(vocals, SLOW_RATIO)
    vocals_s = dsp.tape_wobble(vocals_s, SR, rate_hz=0.19, depth=13)
    vocals_s = dsp.rms_normalize(vocals_s, -14.0)
    vocals_s = Pedalboard([
        HighpassFilter(cutoff_frequency_hz=100),
        Chorus(rate_hz=0.65, depth=0.22, centre_delay_ms=7.5, feedback=0.08, mix=0.22),
        Delay(delay_seconds=0.30, feedback=0.20, mix=0.14),
        Reverb(room_size=0.72, damping=0.45, wet_level=0.22, dry_level=0.9),
        HighShelfFilter(cutoff_frequency_hz=9000, gain_db=1.0),
    ])(vocals_s, SR)

    total_s = vocals_s.shape[0]/SR + 3.0

    # 2) Per-bar chords from the chord-window JSON (one chord per 4 beats)
    chord_data = json.load(open(CHORDS_JSON))
    bar_chords = analysis.bar_chords_from_beats(beat_times, chord_data["chords"], MIDI_STRETCH)

    # 3) Drums on actual beats — arrangement: intro silence → light → groove → ...
    def sc(t): return t*(1.0/SLOW_RATIO)
    drum_sections = [
        (0.0,      sc(18.0), 0.0, "off"),
        (sc(18.0), sc(60.0), 0.85, "light"),
        (sc(60.0), sc(100.0), 1.0, "groove"),
        (sc(100.0), sc(140.0), 0.85, "light"),
        (sc(140.0), sc(180.0), 1.0, "groove"),
        (sc(180.0), sc(220.0), 0.7, "light"),
    ]
    drum_raw = drums.render_drums_on_beats(beat_times, total_s, SR, drum_sections)
    drums_s = Pedalboard([
        HighpassFilter(cutoff_frequency_hz=35),
        LowpassFilter(cutoff_frequency_hz=12000),
        Compressor(threshold_db=-14, ratio=3.5, attack_ms=5, release_ms=100),
        Reverb(room_size=0.35, damping=0.6, wet_level=0.1, dry_level=0.92),
    ])(drum_raw, SR)

    # 4) Bass on beats 1 & 3 (root → fifth) — NOT from basic-pitch timing
    bass_raw = _render_bass(beat_times, bar_chords, total_s, SR, gain=1.0)
    bass_s = Pedalboard([
        LowpassFilter(cutoff_frequency_hz=1800),
        Compressor(threshold_db=-18, ratio=3.0, attack_ms=8, release_ms=110),
    ])(bass_raw, SR)

    # 5) Rhodes comp on beats 2 & 4 (syncopated)
    rhodes_raw = _render_rhodes(beat_times, bar_chords, total_s, SR, gain=1.0)
    rhodes_s = Pedalboard([
        Chorus(rate_hz=0.45, depth=0.4, centre_delay_ms=9, feedback=0.15, mix=0.35),
        Delay(delay_seconds=0.32, feedback=0.28, mix=0.2),
        Reverb(room_size=0.78, damping=0.4, wet_level=0.28, dry_level=0.8),
        HighShelfFilter(cutoff_frequency_hz=8000, gain_db=1.0),
    ])(rhodes_raw, SR)

    # 6) Lush pad (one voicing per bar)
    pad_raw = _render_pad(bar_chords, total_s, SR)
    pad_s = Pedalboard([
        Chorus(rate_hz=0.25, depth=0.55, centre_delay_ms=14, feedback=0.2, mix=0.5),
        Reverb(room_size=0.9, damping=0.35, wet_level=0.42, dry_level=0.6),
        LowpassFilter(cutoff_frequency_hz=6500),
    ])(pad_raw, SR)

    # 7) ACE atmosphere layer
    ace_layer = None
    cands = sorted(glob.glob(ACE_PAD_GLOB), key=os.path.getmtime)
    if cands:
        ace = dsp.load_stereo(cands[-1], SR)
        ace = dsp.resample_rate(ace, SLOW_RATIO)
        ace_layer = Pedalboard([
            HighpassFilter(cutoff_frequency_hz=140),
            Chorus(rate_hz=0.3, depth=0.4, centre_delay_ms=12, feedback=0.15, mix=0.35),
            Reverb(room_size=0.85, damping=0.45, wet_level=0.3, dry_level=0.65),
            LowpassFilter(cutoff_frequency_hz=7500),
        ])(ace, SR)

    # Align
    target_n = max(vocals_s.shape[0], drums_s.shape[0], bass_s.shape[0],
                   rhodes_s.shape[0], pad_s.shape[0],
                   0 if ace_layer is None else ace_layer.shape[0])
    def P(y): return dsp.pad_to(y, target_n)
    vocals_s, drums_s, bass_s, rhodes_s, pad_s = (P(x) for x in
        (vocals_s, drums_s, bass_s, rhodes_s, pad_s))
    if ace_layer is not None: ace_layer = P(ace_layer)

    mix = (1.20*vocals_s + 0.55*drums_s + 0.70*bass_s + 0.55*rhodes_s + 0.40*pad_s)
    if ace_layer is not None: mix += 0.20*ace_layer

    # Tape hiss + master
    mix += 0.25 * P(dsp.cassette_hiss(target_n/SR, SR, level=0.010))
    mix = Pedalboard([
        LowShelfFilter(cutoff_frequency_hz=120, gain_db=1.0),
        HighShelfFilter(cutoff_frequency_hz=8500, gain_db=1.5),
        Compressor(threshold_db=-16, ratio=2.0, attack_ms=20, release_ms=180),
        Gain(gain_db=-1.0),
    ])(mix.astype(np.float32), SR)
    mix = dsp.mix_fades(mix, SR, fade_in_s=2.0, fade_out_s=6.0)
    mix = dsp.limit_peak(mix, 0.97)

    import soundfile as sf
    sf.write(OUT_WAV, mix, SR, subtype='PCM_16')
    print(f"Wrote {OUT_WAV}")


# ---- Beat-grid synth renderers (reusable) ----
def _render_bass(beat_times, bar_chords, total_s, sr, gain=1.0):
    n_total = int(total_s*sr)
    L = np.zeros(n_total, dtype=np.float32); R = np.zeros(n_total, dtype=np.float32)
    for i, t in enumerate(beat_times):
        if t >= total_s: break
        bpos = i % 4
        if bpos not in (0, 2): continue
        name = next((n for (s,e,n) in bar_chords if s <= t < e), None)
        rm = synths.chord_root_midi(name) if name else None
        if rm is None: continue
        note_off = 0 if bpos == 0 else 7
        dur = min((beat_times[i+1] - t + 0.05) if i+1 < len(beat_times) else 0.5, 1.4)
        y = synths.voice_slap_bass(synths.midi_to_hz(rm + note_off, slow=PITCH_MULT),
                                     dur*1.02, sr, velocity=0.78*gain)
        si = int(t*sr); ei = min(n_total, si+y.shape[0])
        L[si:ei] += y[:ei-si]; R[si:ei] += y[:ei-si]
    return np.stack([L,R], axis=1)


def _render_rhodes(beat_times, bar_chords, total_s, sr, gain=1.0):
    n_total = int(total_s*sr)
    L = np.zeros(n_total, dtype=np.float32); R = np.zeros(n_total, dtype=np.float32)
    for i, t in enumerate(beat_times):
        if t >= total_s: break
        bpos = i % 4
        if bpos not in (1, 3): continue
        name = next((n for (s,e,n) in bar_chords if s <= t < e), None)
        if name is None: continue
        pitches = synths.chord_voicing_midi(name, base_midi=60)
        dur = min((beat_times[i+1] - t + 0.1) if i+1 < len(beat_times) else 0.6, 1.0)
        for p in pitches:
            y = synths.voice_rhodes(synths.midi_to_hz(p, slow=PITCH_MULT), dur*1.1, sr,
                                     velocity=0.45 + 0.05*random.random())
            pan = ((p%12)-6)/24.0
            gl = math.cos((pan+1)*math.pi/4); gr = math.sin((pan+1)*math.pi/4)
            si = int(t*sr); ei = min(n_total, si+y.shape[0])
            L[si:ei] += y[:ei-si]*gl*0.5*gain
            R[si:ei] += y[:ei-si]*gr*0.5*gain
    return np.stack([L,R], axis=1)


def _render_pad(bar_chords, total_s, sr):
    n_total = int(total_s*sr)
    buf = np.zeros((n_total, 2), dtype=np.float32)
    for (s, e, name) in bar_chords:
        dur = e - s + 0.3
        if dur <= 0.1 or s >= total_s: continue
        pitches = synths.chord_pad_voicing_midi(name)
        if not pitches: continue
        seg = np.zeros((int(dur*sr), 2), dtype=np.float32)
        for p in pitches:
            v = synths.voice_juno_pad(synths.midi_to_hz(p, slow=PITCH_MULT), dur, sr,
                                       velocity=0.5, n_voices=5, spread_cents=10.0)
            seg[:v.shape[0]] += v
        peak = float(np.max(np.abs(seg))) + 1e-9
        seg = seg / peak * 0.32
        si = int(s*sr); ei = min(n_total, si+seg.shape[0])
        buf[si:ei] += seg[:ei-si]
    return buf


if __name__ == "__main__":
    main()
