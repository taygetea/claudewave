---
name: claudewave
description: Toolkit for AI-assisted song remixing, covering, and sound-reactive ASCII-art music-video generation. Invoke when the user wants to transform an existing audio track (mp3/wav/flac) — stem-separating it, transcribing instruments to MIDI, rebuilding it with programmatic synthesis, applying DSP, and/or generating an ASCII music visualizer that reacts to the audio. Supports AI layers via ACE-Step (ComfyUI). Genre-agnostic; the user tells you the aesthetic.
---

# claudewave

A toolkit for building sonic reinterpretations of existing songs and rendering sound-reactive ASCII music videos for them.

The pipeline is general: stems → per-instrument MIDI → beat grid → arrangement (with programmatic synths, DSP, optional AI layers) → ASCII visualizer → mux. The user picks the aesthetic, the palette, the visual concept, the timing, the reflections. The skill provides the building blocks.

## When to use

Trigger on prompts that involve any of:

- remix / rebuild / cover / reimagine a song
- stem separation, vocal isolation
- replace an instrument with a synth
- AI music generation or style transfer (ACE-Step)
- ASCII music video / music visualizer / lyric video
- animate to audio / sound-reactive visuals
- generic "-wave" / slowed & reverb / screw / chop requests
- text-on-video / typewritten commentary timed to vocals

Whenever the user hands over a song and wants *something done to it*, this skill is likely in scope.

## Capabilities

### Audio

1. **Stem separation** — demucs 4-stem (vocals / drums / bass / other) or 2-stem (vocals / no_vocals).
2. **Per-instrument MIDI transcription** — Spotify basic-pitch on individual stems. Pitch/chord info only; NOT timing (see pitfall #1).
3. **Beat tracking** — librosa.beat.beat_track on the instrumental. The authoritative rhythm grid.
4. **Chord detection** — chord-template scoring across pitch-class windows; supports jazz extensions (maj7, m7, 7, m, maj).
5. **Monophonic pitch extraction** — librosa.pyin for whistle/flute/lead lines.
6. **Vocal onset detection** — RMS thresholding, band-passed to voice range to isolate sung vs whistled sections.
7. **Programmatic synth library** — FM Rhodes, slap bass, sub, bell, Juno pad, whistle, FM lead, 5 drum voices.
8. **DSP** — pedalboard (chorus/phaser/reverb/delay/compressor/distortion/bitcrush/pitchshift), custom tape wobble, sidechain pump, vinyl crackle, cassette hiss.
9. **Channel vocoder** — 18-band classic vocoder with chord-following saw carrier.
10. **Chop & loop** — extract a vocal hook and place decaying staggered copies for eccojams-style hypnotics.
11. **Ambient layers** — synthesized crickets, water lapping, wind (no soundfont needed).
12. **AI layers (optional)** — ACE-Step 1.5 text-to-music for atmospheric pads; ACE-Step v1 m2m for vocal style transfer. Requires a local ComfyUI server.

### Video

1. **Audio-reactive analysis** — per-frame RMS + mel bands + 32-band spectrogram.
2. **ASCII character grid renderer** — efficient run-length-encoded PIL rendering. Block chars for dense zones, thin chars for overlays.
3. **Scene primitives** — gradient backgrounds, block-filled zones, palm trees, buildings, windows, horizons, stars, particle fields.
4. **Reflection / subtitle panel** — typewriter effect, time-aligned to vocal onsets, multi-line with cursor.
5. **HUD** — timestamp, session info, spectrogram bars.
6. **FX passes** — chromatic aberration, scanlines, film grain, bloom (scaled by resolution).
7. **Parallel rendering** — `multiprocessing.Pool` across all CPU cores for PIL text rendering.
8. **GPU-accelerated encoding** — `h264_nvenc` for NVIDIA GPUs (20× faster than libx264).
9. **Audio-video muxing** — MP3-in-MP4 for max compatibility, or AAC for modern targets.

## Pipeline at a glance

```
song.mp3
   │
   ▼
demucs ──▶ vocals / drums / bass / other
   │                │          │        │
   │                │          │        ▼
   │                │          │      basic-pitch (→ JSON note events)
   │                │          ▼
   │                │      basic-pitch
   │                │          │
   │                │          ▼
   │                │      chord detection
   │                ▼
   │            (optional: transcribe for percussion cues)
   ▼
librosa.beat_track ────────▶ beat_times[]
   │
   ▼
─── arrangement design ─────────────────────────────────────────
   │                                                              │
   ├─ programmatic synths (lib/synths.py, lib/drums.py)            │
   ├─ DSP chains (lib/dsp.py + pedalboard)                         │
   ├─ chopped hook loops (lib/choppers.py)                         │
   ├─ vocoder (lib/vocoder.py)                                     │
   ├─ ambient layers (lib/ambience.py)                             │
   ├─ (optional) ACE-Step text-to-music pad (lib/ace_step.py)      │
   └─ (optional) ACE-Step v1 m2m vocal re-style (lib/ace_step.py)  │
─── mix + master ──────────────────────────────────────────────────
   │
   ▼
remix.wav
   │
   ▼
──── ASCII visualizer (lib/viz.py + scene code) ──────────────────
   │  - design scene primitives (block-char zones for density)     │
   │  - per-frame grid build → run-length draw                     │
   │  - reflection panel with typewriter reveal                    │
   │  - HUD with audio-reactive spectrogram                        │
   │  - FX passes (chromatic, grain, scanlines)                    │
   │  - parallel render via multiprocessing.Pool + h264_nvenc      │
─────────────────────────────────────────────────────────────────
   │
   ▼
silent.mp4 ──mux with audio──▶ final.mp4 (MP3-in-MP4)
```

## Project layout

```
your_project/
├── input.mp3
├── work/                              # all intermediate artifacts
│   ├── htdemucs/<song>/               # demucs stems
│   │   ├── vocals.wav
│   │   ├── drums.wav
│   │   ├── bass.wav
│   │   └── other.wav
│   ├── <song>_bass_notes.json         # basic-pitch transcriptions
│   ├── <song>_other_notes.json
│   ├── <song>_whistle_notes.json      # (if applicable)
│   ├── <song>_chords.json             # chord windows + bar_chords
│   ├── remix.py                       # your pipeline
│   ├── visualize.py                   # your visualizer
│   └── <song>_remix.wav
└── <song>_claudewave.mp4              # final deliverable
```

## Critical rules (pitfalls Claude has walked through)

1. **Rhythm lives on the beat grid, not on basic-pitch.** basic-pitch note onsets have ~50 ms error. If you drive synth drums / bass / rhodes comping from basic-pitch's note start times, they'll clash rhythmically with each other and with the vocals. **All rhythmic placements** must come from `librosa.beat.beat_track` on the original audio. Use basic-pitch only for *pitch* and *chord* info.

2. **Synth pitch must match slowdown.** If you slow the vocals by ratio `r`, the vocals' pitch drops by `r` too. Your synth notes — which come from MIDI pitches at their original frequencies — will be sharp against the slowed vocals. Multiply every synth `midi_to_hz()` output by the slowdown ratio. (The provided `synths.midi_to_hz(m, slow=ratio)` handles this.)

3. **ASCII zones need block chars, not thin chars.** If a scene zone sits over a colorful gradient sky, thin chars like `. , ; : | / ~ - _` are "holes" — you see the gradient through them, and the zone looks washed out. Use `█ ▓ ▒ ░ ▀ ▄` to fill cells. Keep thin chars for sparse overlays (stars, particles).

4. **Section-aware arrangement.** Drums that never drop out sound exhausting. Define an arrangement of `(start_s, end_s, gain, style)` sections — typical flow is `off → light → groove → light → groove → tail`. Use `lib/drums.py::render_drums_on_beats` with sections.

5. **Reflections must align to sung vocals, not whistle.** demucs classifies whistles into the `vocals` stem. If your song has a whistle, RMS-based vocal onset detection will fire on the whistle too. Band-pass the vocals stem to the voice range (80-800 Hz) before detecting onsets if you only want sung sections. Reflections timed to whistle rather than singing will feel off.

6. **Panel should be contiguous.** The reflection/subtitle panel should never have gaps where it disappears entirely — that reads as broken. Make reflection entries end exactly where the next begins, covering the whole track (with an intro entry before first vocals and outro after last).

7. **Chromatic aberration scales with resolution.** `shift=3` at 4K is fine, but at 1080p it blurs everything. Rule: `shift=1` at 1080p, `shift=2` at 1440p, `shift=3` at 4K.

8. **Scene reactivity: less is more.** Don't drive every visual element from RMS — it makes the scene twitchy. Reserve audio-reactivity for deliberate elements (typically the bottom spectrogram bars, maybe a sun halo). Let waves, palm tree sway, etc. move on smooth time sine waves only.

9. **Rendering speed.** Single-process PIL rendering is slow. On modern hardware you should always use `multiprocessing.Pool` + `h264_nvenc`. See `lib/viz.py::render_video`. Expected: ~3 seconds per second of video at 1080p60 on a 32-core/4090-laptop. Single-process libx264 is ~20-30× slower.

10. **Audio codec for compatibility.** Windows Media Player doesn't always play AAC in MP4. If the user reports "no sound", re-mux with `libmp3lame` — MP3-in-MP4 plays reliably in WMP, VLC, browsers, mobile.

## Skill workflow

When invoked:

1. **Clarify the vision.** Ask what aesthetic the user wants (specific subgenre? general vibe words? a visual concept for the video?). Different aesthetics want different parameters — see `docs/subgenre_recipes.md` for starting points, but don't assume. If the user asked for a specific genre, check fit: certain subgenres only work on certain source material (docs/subgenre_recipes.md explains).

2. **Environment check.** Verify ffmpeg, Python 3.13 main env, Python 3.12 for basic-pitch, and optionally ComfyUI reachability. See `setup.md`.

3. **Stem separation** (4-stem unless user wants minimal-change). Report what's in each stem.

4. **MIDI transcription** for whichever stems are needed. Report note counts. Remind Claude not to use onsets for timing.

5. **Beat track + chord detection.** Report tempo and chord progression — this informs the arrangement.

6. **(Optional) Monophonic extraction** for whistles/leads.

7. **(Optional) ACE-Step** generation and/or m2m layers if the user wants AI atmosphere or AI-styled vocals.

8. **Design the remix**, based on the aesthetic. Preview the audio before committing to video.

9. **Design the visualizer.** Palette, scene elements, reflections (ideally timed to vocal onsets). Render 3-5 preview frames at different timestamps BEFORE the full render — cheap to iterate on palette/layout that way.

10. **Full render.** Use multiprocessing + nvenc. Expected: a few minutes.

11. **Mux** (MP3-in-MP4 default).

12. **Iterate.** Feedback loops happen — mix balance, reflection timing, scene reactivity are all common iteration points.

## Dependencies

Full install commands in `setup.md`. Summary of the stack this skill uses:

### Required

- **ffmpeg** — audio/video IO, muxing, encoding. Must include `libx264`, `libmp3lame`. For GPU encoding (strongly recommended on NVIDIA systems) include `h264_nvenc`. On Windows, grab a `-full` build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/).
- **Python 3.13** (main env) with: `librosa`, `soundfile`, `scipy`, `numpy`, `pedalboard`, `demucs`, `torch`, `torchaudio`, `Pillow`.
- **Python 3.12** (side env, basic-pitch's build chain doesn't work on 3.13) with: `basic-pitch`, `onnxruntime`, `pretty_midi`, `librosa`, `soundfile`, `scipy`, `mir_eval`, `resampy<0.4.3`. Invoke it as `py -3.12 <script>`. The skill uses it ONLY for the MIDI-transcription step.

### Underlying ML models (automatic downloads)

- **demucs** — Meta's `htdemucs` hybrid-transformer source-separation model (`~/.cache/torch/hub/checkpoints/955717e8-8726e21a.th`, ~80 MB, downloads on first run).
- **basic-pitch** — Spotify's polyphonic pitch detection (CC BY 4.0). Ships inside the package at `basic_pitch/saved_models/icassp_2022/nmp.onnx`. The skill uses the ONNX variant (not the TF saved_model, which fails to load on current TF versions).

### Optional but recommended: ComfyUI + ACE-Step (for AI music layers)

ACE-Step is a diffusion-based music generation model that lets you:
- Generate atmospheric pads / beds from text prompts (genre + BPM + key)
- Do **m2m** (audio-to-audio) style transfer on vocals — take an existing vocal stem and re-interpret it in a different aesthetic (vaporwave, dreamy, ethereal, etc.)

Setup:

1. Install [ComfyUI](https://github.com/comfyanonymous/ComfyUI) and run on `127.0.0.1:8188`. The skill queues jobs via its HTTP API (`POST /prompt`).
2. Download and place these checkpoints in `ComfyUI/models/checkpoints/`:
   - **`ace_step_1.5_turbo_aio.safetensors`** — for text-to-music generation (fast, all-in-one 1.5 variant). Grab from the ACE-Step Hugging Face repo.
   - **`ace_step_v1_3.5b.safetensors`** — for m2m style transfer. The v1 variant supports a `lyrics_strength` parameter that v1.5 doesn't. Larger (~7 GB).
3. ComfyUI must expose these built-in node classes (all ship with recent ComfyUI):
   - `CheckpointLoaderSimple`, `KSampler`
   - `EmptyAceStep1.5LatentAudio`, `TextEncodeAceStepAudio1.5` (for v1.5 gen)
   - `TextEncodeAceStepAudio` (for v1 m2m, takes `lyrics_strength`)
   - `LoadAudio`, `SaveAudio`, `VAEEncodeAudio`, `VAEDecodeAudio`, `ReferenceTimbreAudio`

The skill's `lib/ace_step.py` has `build_ace15_generation()` and `build_ace_v1_m2m()` which produce ready-to-queue workflow JSON dicts. It'll skip AI layers if the server isn't reachable at `127.0.0.1:8188`.

Approximate VRAM requirements: 8 GB for ACE-Step 1.5 turbo, 12+ GB recommended for ACE-Step v1 3.5B.

### Fonts used

Default font paths in the templates (Windows):
- `C:\Windows\Fonts\consolab.ttf` — Consolas Bold (main cell + UI)
- `C:\Windows\Fonts\georgiai.ttf` — Georgia Italic (reflection panels, journal feel)
- `C:\Windows\Fonts\segoesc.ttf` — Segoe Script (handwritten feel; optional)

Substitute equivalents on macOS/Linux if needed. Any monospace + any italic serif work.

### Optional extras

These weren't required for the patterns in this skill (the default synth voices in `lib/synths.py` are pure numpy, no soundfonts or external synthesis engines needed) — but they're genuine alternatives worth knowing about:

- **music21** (`pip install music21`) — full-featured music-theory toolkit. Can do key estimation, chord progression analysis, MIDI manipulation, harmonic analysis, voice-leading. Useful if you want smarter chord detection than the built-in pitch-class scoring in `lib/analysis.py`, or if you want to compose MIDI programmatically (generate bass lines, harmonize melodies, etc.) before handing the result to the synth voices.
- **fluidsynth** + a `.sf2` soundfont — renders MIDI to audio via a real sampler, giving you realistic piano, strings, brass, etc. (General Midi or custom soundfonts work.) The skill's default synths are FM/subtractive — great for vaporwave/citypop aesthetic but not acoustic-realistic. Install with `winget install FluidSynth.FluidSynth` (Windows) / `brew install fluidsynth` / `apt install fluidsynth libfluidsynth-dev`, then `pip install pyfluidsynth`. Grab a free soundfont like **GeneralUser GS** ([schristiancollins.com](https://schristiancollins.com/generaluser.php)). **Gotcha:** on Windows, `pyfluidsynth` hard-codes `C:\tools\fluidsynth\bin` as a DLL path — you may need to create that folder and drop `libfluidsynth.dll` into it, or set the `FLUIDSYNTH_LIB_PATH` env var.
- **pyfiglet** (`pip install pyfiglet`) — big ASCII-art title generator. `pyfiglet "YOUR TITLE" -f big` gives you a ready-to-paste `TITLE_ART` array for the visualizer.
- **basic-pitch-torch** / **crepe** / **omnizart** / **MT3** — alternative polyphonic/monophonic transcription models. basic-pitch is the easiest to use and what the skill defaults to. Swap in others if you need different tradeoffs (accuracy vs speed vs polyphony limit).
- **Spleeter** — Deezer's alternative to demucs for stem separation. Faster but generally lower quality; demucs is preferred.
- **Spectral feature extraction** — beyond the `librosa.feature.melspectrogram` / `rms` used here, librosa has tempo-gram, beat-gram, chroma-cqt, constant-Q, spectral-flux, onset-strength-envelope, etc. for more sophisticated audio-reactivity.

## Getting started

See:
- `setup.md` — copy-paste install commands for everything above
- `requirements.txt` — pip dependencies (with notes on the Python 3.13 vs 3.12 split)
- `lib/` — reusable audio + video building blocks (importable as `claudewave.lib.*`)
- `templates/` — adaptable pipelines for remixes and visualizers
- `docs/pipeline.md` — step-by-step reference
- `docs/subgenre_recipes.md` — parameter presets for common -wave genres if the user asks for one
- `docs/viz_patterns.md` — visualizer scene patterns

---

License: MIT. The tools used (demucs/basic-pitch/ACE-Step/librosa/pedalboard) have their own licenses — check before redistributing outputs commercially.
