"""
Analysis helpers: stem separation, beat-tracking, chord detection,
monophonic melody extraction. Call these to drive the synth rebuild.
"""
import json, os, subprocess, math
import numpy as np
import librosa
from collections import defaultdict


# ====================== 1) Stem separation (demucs) ======================

def run_demucs(input_path, work_dir, two_stems=False):
    """Run demucs via subprocess. Returns path to the stems folder
    (work_dir/htdemucs/<song>/)."""
    cmd = ["python", "-m", "demucs", "-o", work_dir]
    if two_stems:
        cmd += ["--two-stems=vocals"]
    cmd.append(input_path)
    subprocess.run(cmd, check=True)
    song_name = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(work_dir, "htdemucs", song_name)


# ====================== 2) Beat tracking ======================

def beat_track(audio_path, sr_load=22050, tightness=110):
    """Return (tempo_bpm, beat_times_s). Use an instrumental/no_vocals stem
    for the best beat detection — vocals can confuse the tracker."""
    y, sr = librosa.load(audio_path, sr=sr_load, mono=True)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, trim=False, tightness=tightness)
    return float(np.atleast_1d(tempo).item()), librosa.frames_to_time(beats, sr=sr)


# ====================== 3) Chord detection ======================

CHORD_TEMPLATES = []
for name, root in [("C",0),("C#",1),("Db",1),("D",2),("D#",3),("Eb",3),("E",4),("F",5),
                   ("F#",6),("Gb",6),("G",7),("G#",8),("Ab",8),("A",9),("A#",10),("Bb",10),("B",11)]:
    CHORD_TEMPLATES.append((f"{name}maj7", [root, (root+4)%12, (root+7)%12, (root+11)%12]))
    CHORD_TEMPLATES.append((f"{name}m7",   [root, (root+3)%12, (root+7)%12, (root+10)%12]))
    CHORD_TEMPLATES.append((f"{name}7",    [root, (root+4)%12, (root+7)%12, (root+10)%12]))
    CHORD_TEMPLATES.append((f"{name}",     [root, (root+4)%12, (root+7)%12]))
    CHORD_TEMPLATES.append((f"{name}m",    [root, (root+3)%12, (root+7)%12]))


def detect_chords_from_notes(notes, tempo_bpm, beats_per_window=2,
                              prefer_sevenths=True):
    """Score chord labels against the transcribed note events.

    notes: list of {start, end, pitch, vel} dicts (from basic-pitch)
    Returns list of {start, end, chord, bass_midi} windows.
    """
    window = beats_per_window * 60.0/tempo_bpm
    duration = max((n["end"] for n in notes), default=0.0)
    out = []
    t0 = 0.0
    while t0 < duration:
        t1 = t0 + window
        pc = np.zeros(12)
        low = None
        for e in notes:
            if e["end"] <= t0 or e["start"] >= t1: continue
            ol = max(0, min(e["end"], t1) - max(e["start"], t0))
            pc[e["pitch"] % 12] += ol * e["vel"]
            if low is None or e["pitch"] < low: low = e["pitch"]
        if pc.sum() > 0:
            best = None; best_s = -1e9
            for name, tones in CHORD_TEMPLATES:
                bonus = 1.3 if (prefer_sevenths and len(tones) == 4) else 1.0
                score = bonus * sum(pc[t] for t in tones) \
                      - 0.12 * sum(pc[t] for t in range(12) if t not in tones)
                if score > best_s:
                    best_s = score; best = name
        else:
            best = None
        out.append({"start": t0, "end": t1, "chord": best, "bass_midi": low})
        t0 = t1
    return out


def bar_chords_from_beats(beat_times_slowed, chord_windows, midi_stretch):
    """Collapse chord_windows into one chord per bar (4 beats), scaled to
    the slowed timeline.

    Returns list of (bar_start_s, bar_end_s, chord_name) tuples.
    """
    bar_chords = []
    for i in range(0, len(beat_times_slowed)-1, 4):
        t0 = beat_times_slowed[i]
        t1 = beat_times_slowed[i+4] if i+4 < len(beat_times_slowed) else beat_times_slowed[-1] + 0.6
        tot = defaultdict(float)
        for c in chord_windows:
            cs = c["start"] * midi_stretch
            ce = c["end"]   * midi_stretch
            if ce <= t0 or cs >= t1: continue
            o = min(ce, t1) - max(cs, t0)
            if c["chord"]: tot[c["chord"]] += o
        name = max(tot.items(), key=lambda kv: kv[1])[0] if tot else None
        bar_chords.append((t0, t1, name))
    return bar_chords


# ====================== 4) Monophonic melody / whistle (pyin) ======================

def extract_monophonic(wav_path, fmin_note='C5', fmax_note='C7',
                       band=(550, 3500), voiced_thr=0.30, min_dur=0.08,
                       pitch_tol=1.5, bridge_gap_s=0.12, bridge_pitch_tol=3):
    """Extract a monophonic pitch line (whistle/flute/lead) as MIDI note events.

    - Band-passes the audio to the expected range so non-melodic energy
      doesn't confuse pyin.
    - Returns list of {start, end, pitch, vel} (vel fixed at 0.8).
    - Bridges adjacent notes of similar pitch with short gaps (legato).
    """
    from scipy import signal as scsig
    y, sr = librosa.load(wav_path, sr=22050, mono=True)
    sos = scsig.butter(4, [band[0]/(sr/2), band[1]/(sr/2)], btype='band', output='sos')
    y_bp = scsig.sosfilt(sos, y).astype(np.float32)

    f0, voiced_flag, voiced_prob = librosa.pyin(
        y_bp, fmin=librosa.note_to_hz(fmin_note), fmax=librosa.note_to_hz(fmax_note),
        sr=sr, frame_length=2048, hop_length=256, resolution=0.1,
    )
    times = librosa.times_like(f0, sr=sr, hop_length=256)
    valid = (voiced_flag) & (voiced_prob > voiced_thr) & ~np.isnan(f0)

    # extract notes
    notes = []
    in_note = False; note_start = 0.0; pitch_buffer = []
    for (t, p, v) in zip(times, f0, valid):
        if v:
            midi = librosa.hz_to_midi(p)
            if not in_note:
                in_note = True; note_start = t; pitch_buffer = [midi]
            else:
                if abs(midi - np.mean(pitch_buffer)) > pitch_tol:
                    dur = t - note_start
                    if dur >= min_dur:
                        notes.append({"start": float(note_start), "end": float(t),
                                      "pitch": int(round(np.median(pitch_buffer))), "vel": 0.8})
                    note_start = t; pitch_buffer = [midi]
                else:
                    pitch_buffer.append(midi)
        else:
            if in_note:
                dur = t - note_start
                if dur >= min_dur:
                    notes.append({"start": float(note_start), "end": float(t),
                                  "pitch": int(round(np.median(pitch_buffer))), "vel": 0.8})
                in_note = False; pitch_buffer = []
    if in_note and len(pitch_buffer) > 3:
        notes.append({"start": float(note_start), "end": float(times[-1]),
                      "pitch": int(round(np.median(pitch_buffer))), "vel": 0.8})

    # merge/bridge adjacent notes of close pitch
    bridged = []
    for n in notes:
        if (bridged
            and (n["start"] - bridged[-1]["end"] < bridge_gap_s)
            and abs(n["pitch"] - bridged[-1]["pitch"]) <= bridge_pitch_tol):
            bridged[-1]["end"] = n["end"]
        else:
            bridged.append(n)
    # drop very short
    return [n for n in bridged if (n["end"]-n["start"]) >= min_dur]


# ====================== 5) Vocal onset segments ======================

def vocal_activity_segments(vocal_wav, sr_load=22050, threshold=0.025,
                            min_segment_s=0.5, hop=512):
    """Simple RMS-threshold vocal activity detection. Returns list of (start, end)
    in the ORIGINAL audio timeline. Useful for section-aware arrangement."""
    y, sr = librosa.load(vocal_wav, sr=sr_load, mono=True)
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    times = librosa.times_like(rms, sr=sr, hop_length=hop)
    active = rms > threshold
    segs = []
    in_seg = False; seg_start = 0.0
    for i, a in enumerate(active):
        if a and not in_seg:
            seg_start = times[i]; in_seg = True
        elif not a and in_seg:
            if times[i] - seg_start > min_segment_s:
                segs.append((float(seg_start), float(times[i])))
            in_seg = False
    if in_seg and (times[-1] - seg_start > min_segment_s):
        segs.append((float(seg_start), float(times[-1])))
    return segs


# ====================== 6) MIDI transcription helper (Python 3.12) ======================

def transcribe_stem_basic_pitch(wav_path, out_json, fmin=30.0, fmax=3000.0,
                                 onset_threshold=0.5, frame_threshold=0.3,
                                 minimum_note_length=58.0):
    """Calls basic-pitch to transcribe a single stem to a simple JSON file.

    MUST be run under Python 3.12 (see setup.md). Uses the ONNX model.
    """
    from basic_pitch.inference import predict, Model
    from basic_pitch import ICASSP_2022_MODEL_PATH
    onnx_path = os.path.join(os.path.dirname(ICASSP_2022_MODEL_PATH), "nmp.onnx")
    model = Model(onnx_path)
    _, midi_data, note_events = predict(
        wav_path, model,
        onset_threshold=onset_threshold, frame_threshold=frame_threshold,
        minimum_note_length=minimum_note_length,
        minimum_frequency=fmin, maximum_frequency=fmax,
        multiple_pitch_bends=False, melodia_trick=True,
    )
    events = []
    for (s, e, p, v, pb) in note_events:
        events.append({"start": float(s), "end": float(e),
                       "pitch": int(p), "vel": float(v)})
    events.sort(key=lambda x: (x["start"], x["pitch"]))
    dur = max((x["end"] for x in events), default=0.0)
    with open(out_json, "w") as f:
        json.dump({"duration": dur, "notes": events}, f, indent=1)
    return out_json
