# Setup

This skill uses a stack with audio/video binaries, two Python environments (3.13 main + 3.12 side for basic-pitch), and an optional local ComfyUI server for AI music layers.

## 1. ffmpeg (required)

The skill shells out to `ffmpeg` for encoding and muxing. You need a build that includes `libx264`, `libmp3lame`, and ideally `h264_nvenc` (NVIDIA GPU encoder — 20× faster than libx264).

**Windows:** grab a `-full` build from [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/), extract `ffmpeg.exe` + `ffprobe.exe`, put them on PATH.

**macOS:** `brew install ffmpeg` (no nvenc; use libx264, ~20× slower but works).

**Linux:** `apt install ffmpeg` or Nix `nix-shell -p ffmpeg-full`. For NVENC you may need the NVIDIA-enabled build from the [official docs](https://trac.ffmpeg.org/wiki/HWAccelIntro#NVENC).

Verify:

```bash
ffmpeg -version             # check version string
ffmpeg -h encoder=libmp3lame   # should print encoder options
ffmpeg -h encoder=h264_nvenc   # GPU encoder; optional
```

## 2. Python 3.13 main environment (required)

Most of the skill runs here. Pin torch/torchaudio to matching CUDA versions.

```bash
pip install librosa soundfile scipy numpy pedalboard demucs Pillow music21 pyfiglet
# torch/torchaudio — pick the right CUDA for your system
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
# or CPU-only if no GPU:
# pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

**Gotcha: demucs + torchaudio on Windows.** If `python -m demucs ...` errors with `torch.ops.load_library` or `WinError 127`, your `torchaudio` version doesn't match your `torch`. Fix:

```bash
pip install --force-reinstall --no-deps torchaudio==<your-torch-version> \
    --index-url https://download.pytorch.org/whl/cu124
```

## 3. Python 3.12 side environment (required — for basic-pitch)

basic-pitch's transitive dependencies (old setuptools for some subdep's numpy build) don't build on Python 3.13 right now. You need a 3.12 interpreter side-by-side.

**Windows:** `winget install Python.Python.3.12` — installs alongside 3.13; invoke as `py -3.12`.

**macOS:** `brew install python@3.12`.

**Linux:** `apt install python3.12` or via `pyenv`.

Install basic-pitch + its usable deps there (use `--no-deps` to avoid resolution headaches):

```bash
py -3.12 -m pip install numpy==1.26.4
py -3.12 -m pip install --no-deps basic-pitch
py -3.12 -m pip install onnxruntime pretty_midi librosa soundfile scipy mir_eval "resampy<0.4.3"

# Verify
py -3.12 -c "from basic_pitch.inference import predict, Model; print('basic-pitch ready')"
```

**Why the ONNX model?** basic-pitch ships both a TF saved_model and an ONNX variant. The TF saved_model fails to load on newer TF versions (`_UserObject has no attribute add_slot`). This skill uses `nmp.onnx` via `onnxruntime` instead, which loads cleanly.

The model path is `<site-packages>/basic_pitch/saved_models/icassp_2022/nmp.onnx`.

## 4. ComfyUI + ACE-Step (optional — for AI music layers)

This unlocks two capabilities:

- **AI atmosphere pads** (text-to-music). Describe a genre + BPM + key, get a ~4 minute atmospheric track you can layer under the mix.
- **Vocal style transfer** (m2m audio-to-audio). Feed in a vocal stem and new tags like "vaporwave, dreamy, ethereal", get back an AI-reinterpreted version to blend in.

### Install ComfyUI

Follow [ComfyUI's install guide](https://github.com/comfyanonymous/ComfyUI#installing). Run on `127.0.0.1:8188`:

```bash
python main.py --listen 0.0.0.0 --port 8188
# or on Windows via the ComfyUI Desktop app, which defaults to this port
```

### Install ACE-Step checkpoints

Place these files in `<ComfyUI>/models/checkpoints/`:

| File | Size | Purpose |
|---|---|---|
| `ace_step_1.5_turbo_aio.safetensors` | ~3 GB | Fast text-to-music (v1.5 turbo, all-in-one). For atmospheric pads. |
| `ace_step_v1_3.5b.safetensors` | ~7 GB | v1 model with `lyrics_strength` parameter. For m2m vocal style transfer (KSampler with `denoise < 1.0`). |

Download from the official ACE-Step Hugging Face repo ([huggingface.co/ace-step](https://huggingface.co/ace-step) — check for the latest). You can use Hugging Face's `huggingface-cli download` or just drop the files manually.

### Required node classes

All of these ship with recent ComfyUI builds — no custom nodes needed:

- `CheckpointLoaderSimple`
- `KSampler`
- `EmptyAceStep1.5LatentAudio` / `EmptyAceStepLatentAudio`
- `TextEncodeAceStepAudio` (v1, exposes `lyrics_strength`)
- `TextEncodeAceStepAudio1.5`
- `LoadAudio`, `SaveAudio`
- `VAEEncodeAudio`, `VAEDecodeAudio`
- `ReferenceTimbreAudio` (optional, for preserving timbre)

Verify all are available:

```bash
curl -s http://127.0.0.1:8188/object_info | \
  python -c "import sys, json; d = json.load(sys.stdin); \
    needed = ['CheckpointLoaderSimple','KSampler','EmptyAceStep1.5LatentAudio',\
    'TextEncodeAceStepAudio','TextEncodeAceStepAudio1.5','LoadAudio','SaveAudio',\
    'VAEEncodeAudio','VAEDecodeAudio']; \
    [print(n, 'OK' if n in d else 'MISSING') for n in needed]"
```

### VRAM requirements

- `ace_step_1.5_turbo_aio.safetensors` text-to-music at ~4 minute duration: **~8 GB VRAM**.
- `ace_step_v1_3.5b.safetensors` m2m at ~4 minute duration: **~12 GB VRAM recommended**. Less works but may be slow or OOM.

### Uploading audio for m2m

ComfyUI's `LoadAudio` node reads from `<ComfyUI>/input/`. Copy your vocal stem there before queueing an m2m workflow:

```python
import shutil
shutil.copy("work/htdemucs/song/vocals.wav", "C:/Users/you/ComfyUI/input/song_vocals.wav")
```

## 5. Optional: music21

Full-featured music-theory toolkit — key estimation, chord analysis, MIDI manipulation, voice-leading. The skill's default `lib/analysis.py::detect_chords_from_notes` does simple pitch-class template matching; music21 lets you do smarter things:

```bash
pip install music21
```

Use cases: programmatically compose a bass line, harmonize a melody, transpose chord progressions to a new key, export MIDI with correct musical notation, do key-signature detection on a pitch sequence.

## 6. Optional: fluidsynth + soundfont

If you want realistic piano/orchestral sounds (instead of the FM/subtractive synthesis this skill does by default), install fluidsynth and a General MIDI soundfont.

**Windows:** 
```bash
winget install FluidSynth.FluidSynth     # or download from fluidsynth.org
pip install pyfluidsynth
```

**Gotcha on Windows:** `pyfluidsynth` hard-codes its DLL search to `C:\tools\fluidsynth\bin`. If you get `FileNotFoundError: ... C:\tools\fluidsynth\bin`, create that directory and put `libfluidsynth.dll` there, or set the `FLUIDSYNTH_LIB_PATH` environment variable to your actual install path. (This is a known issue with the Windows build of pyfluidsynth.)

**macOS/Linux:** 
```bash
brew install fluidsynth           # or: apt install fluidsynth libfluidsynth-dev
pip install pyfluidsynth
```

Then download a soundfont — free options:
- **GeneralUser GS** (~30 MB, excellent GM quality): [schristiancollins.com/generaluser.php](https://schristiancollins.com/generaluser.php)
- **FluidR3_GM.sf2** (~140 MB, what comes with most Linux distros)
- **Salamander Grand Piano** if you want just piano: [sfzinstruments.github.io](https://sfzinstruments.github.io/pianos/salamander/)

This skill doesn't require fluidsynth — all instruments in `lib/synths.py` are synthesized in numpy — but it's a nice option for acoustic timbres, especially for dreampop/chillwave aesthetics where you might want a real piano instead of an FM Rhodes.

## 7. Optional: pyfiglet for title art

For auto-generating big ASCII titles:

```bash
pip install pyfiglet
pyfiglet "YOUR TITLE" -f "big"
```

Paste the output into your visualizer's `TITLE_ART` list. The templates include hand-tuned block-letter art, but pyfiglet is faster for prototyping.

## 8. Sanity check

All at once:

```bash
# Python 3.13 stack
python -c "import librosa, soundfile, scipy, numpy, pedalboard, demucs, PIL, music21; print('py313 ok')"
# Python 3.12 stack
py -3.12 -c "from basic_pitch.inference import predict, Model; print('py312 ok')"
# ffmpeg
ffmpeg -version | head -1
# ComfyUI (optional)
curl -s http://127.0.0.1:8188/system_stats | head -c 200
```

If all four succeed, you're ready.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ModuleNotFoundError: demucs` or `WinError 127` on demucs import | torchaudio/torch version mismatch. `pip install --force-reinstall --no-deps torchaudio==<torch-version> --index-url https://download.pytorch.org/whl/cu124` |
| `AttributeError: module 'pkgutil' has no attribute 'ImpImporter'` when installing basic-pitch | You're on Python 3.13. Use `py -3.12 -m pip install --no-deps basic-pitch` |
| basic-pitch: `File cannot be loaded into TensorFlow, CoreML, TFLite or ONNX` | Missing `onnxruntime`. `py -3.12 -m pip install onnxruntime` and pass `Model(nmp.onnx)` explicitly (see `lib/analysis.py`) |
| demucs first-run download fails | Rerun when network is stable; cached under `~/.cache/torch/hub/checkpoints/` |
| ComfyUI `LoadAudio` doesn't see your file | Copy the file to `<ComfyUI>/input/` first |
| ComfyUI queue returns `required_input_missing` | Pass all advanced params explicitly in the workflow JSON: `generate_audio_codes`, `cfg_scale`, `temperature`, `top_p`, `top_k`, `min_p`. See `lib/ace_step.py` for a complete template. |
| ffmpeg `Unknown encoder h264_nvenc` | Your build doesn't include NVENC. Use a `-full` build, or fall back to `libx264` (slower) |
| "Final video has no sound" (Windows Media Player) | WMP is picky about AAC in MP4. Re-mux with `audio_codec="mp3"` (MP3-in-MP4) using `lib/viz.py::mux_audio_video` |
| Render is slow (single-process) | You're not using `multiprocessing.Pool`. See `lib/viz.py::render_video` — it parallelizes across CPU cores and encodes on GPU |
| Video looks blurry at 1080p | Chromatic-shift is probably too aggressive. Use `shift=1` at 1080p, `shift=2` at 1440p, `shift=3` at 4K |
