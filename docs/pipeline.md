# Pipeline

Step-by-step reference, with the commands you'll actually run.

## 1. Stem separation

```bash
# 4-stem (vocals / drums / bass / other) — use this for proper cover rebuilds
python -m demucs -o work "song.mp3"

# OR 2-stem (vocals / no_vocals) — use this for just layering treatment
python -m demucs --two-stems=vocals -o work "song.mp3"
```

Outputs `work/htdemucs/<song>/*.wav`.

## 2. Transcribe stems to MIDI (Python 3.12)

Transcribe each harmonic stem separately. Skip `drums.wav` (no harmonic content). Use the helpers in `lib/analysis.py`:

```python
from claudewave.lib.analysis import transcribe_stem_basic_pitch

# bass stem — narrow freq range
transcribe_stem_basic_pitch("work/htdemucs/song/bass.wav",
                             "work/song_bass_notes.json",
                             fmin=30.0, fmax=500.0)

# other stem (piano/strings/leads) — broad freq range
transcribe_stem_basic_pitch("work/htdemucs/song/other.wav",
                             "work/song_other_notes.json",
                             fmin=55.0, fmax=3000.0)
```

**RUN WITH `py -3.12`** — basic-pitch's deps don't build on 3.13 yet.

## 3. Beat-track the instrumental

```python
from claudewave.lib.analysis import beat_track
tempo, beat_times = beat_track("work/htdemucs/song/no_vocals.wav")
# scale to slowed timeline:
beat_times_slowed = beat_times * (1.0 / SLOW_RATIO)
```

## 4. Detect chord progression

```python
from claudewave.lib.analysis import detect_chords_from_notes, bar_chords_from_beats
import json
notes = json.load(open("work/song_other_notes.json"))["notes"]
chord_windows = detect_chords_from_notes(notes, tempo_bpm=tempo)
bar_chords = bar_chords_from_beats(beat_times_slowed, chord_windows,
                                    midi_stretch=1.0/SLOW_RATIO)
```

## 5. (Optional) Extract monophonic melody

For whistles, flutes, or lead lines:

```python
from claudewave.lib.analysis import extract_monophonic
whistle = extract_monophonic("work/htdemucs/song/vocals.wav",
                              fmin_note='C5', fmax_note='C7',
                              band=(550, 3500), voiced_thr=0.30)
```

Note: demucs classifies whistles as `vocals`, not `other`. Band-pass carefully.

## 6. (Optional) ACE-Step atmospheric pad

Requires local ComfyUI at 127.0.0.1:8188.

```python
from claudewave.lib.ace_step import (queue_workflow, wait_for_output,
                                      build_ace15_generation, TAG_PRESETS)
wf = build_ace15_generation(
    tags=TAG_PRESETS["citypop"],
    duration_s=215.0, bpm=96, keyscale="F major",
    filename_prefix="song_citypop_pad",
)
prompt_id = queue_workflow(wf)
pad_path = wait_for_output(prompt_id,
                            output_dir="C:/Users/you/ComfyUI/output",
                            prefix="song_citypop_pad")
```

## 7. (Optional) ACE-Step v1 m2m vocal style transfer

```python
import shutil
from claudewave.lib.ace_step import queue_workflow, wait_for_output, build_ace_v1_m2m

# copy vocals stem into ComfyUI/input/ first
shutil.copy("work/htdemucs/song/vocals.wav", "C:/Users/you/ComfyUI/input/song_vocals.wav")

wf = build_ace_v1_m2m(
    audio_filename_in_comfy_input="song_vocals.wav",
    tags="vaporwave, slushwave, dreamy, hypnotic, ethereal, soft female vocal, heavy reverb",
    lyrics="[verse]\n... your lyrics here ...",
    denoise=0.55,
)
prompt_id = queue_workflow(wf)
m2m_path = wait_for_output(prompt_id,
                            output_dir="C:/Users/you/ComfyUI/output",
                            prefix="ace_m2m")
# m2m_path is the AI-shimmered vocal layer, blend it at ~0.4-0.6 gain
```

## 8. Build the remix

Pick a template from `templates/` and adapt the constants. Or compose from `lib/synths.py`, `lib/drums.py`, `lib/dsp.py`, `lib/choppers.py`, `lib/vocoder.py`, `lib/ambience.py`.

**Arrangement**: define sections as `(start_s, end_s, gain, style)`. Styles: `"off" | "light" (half-time) | "groove" (full) | "lift" (with fills)`.

Use `lib.drums.render_drums_on_beats(beat_times, total_s, sr, sections)` to generate the drum track on the real beat grid.

## 9. Build the visualizer

Pick a scene template (`visualize_beach_template.py`, `visualize_nightdrive_template.py`, or design your own). Time the reflection panel to actual sung-vocal onsets:

```python
from claudewave.lib.analysis import vocal_activity_segments
segs = vocal_activity_segments("work/htdemucs/song/vocals.wav",
                                 threshold=0.018)
# But for songs with whistle + singing, BAND-PASS to the voice range first
# (80-800Hz) to detect only sung vocals, not whistle. See visualizer template.
```

**Performance**: use `multiprocessing.Pool` with 30+ workers on a modern CPU, and `h264_nvenc` for the encoder. 1080p60 renders a 4-minute song in ~3-5 minutes on a good laptop.

## 10. Mux

```python
from claudewave.lib.viz import mux_audio_video
mux_audio_video(audio_path="work/song_remix.wav",
                silent_video="work/song_silent.mp4",
                output_path="song_claudewave.mp4",
                audio_codec="mp3")  # MP3 in MP4 plays in WMP; aac is fine for modern
```

## Total time budget

For a ~4 minute song on a 4090-laptop / 32-core CPU:

| Stage | Time |
|---|---|
| demucs 4-stem | ~30s |
| basic-pitch (per stem) | ~15s |
| beat_track + chord detection | 5s |
| ACE-Step generate pad (20 steps) | ~60s |
| ACE-Step v1 m2m (40 steps) | ~3-5min |
| Build remix script | instant once written |
| Render remix audio | ~15s |
| Render 1080p60 video | ~7-10min |
| Mux | ~5s |
| **Total** | **~15-25 min** |

The MP3 input → final video iteration loop on a known template is ~10 min once everything is installed.
