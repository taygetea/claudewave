"""
Base helpers for sound-reactive ASCII visualizers.

The pattern:
  1. Analyze audio once → {rms, mel, mel32, duration, n_frames}.
  2. Build a character grid per frame; draw scene + overlays into it.
  3. Render grid to PIL using run-length-encoded draw.text (100× faster).
  4. Pipe raw RGB24 to ffmpeg; multiprocessing workers in parallel.
  5. Mux with MP3-in-MP4 for max player compatibility.
"""
import os, math, random, subprocess, time
import numpy as np
import librosa
from PIL import Image, ImageDraw


# ====================== Audio analysis ======================

def analyze_audio(path, fps, n_mel_bands=8, n_spec_bars=32):
    """Return dict with duration, n_frames, rms, mel (n_mel_bands × n_frames),
    mel32 (n_spec_bars × n_frames). All arrays already padded to exactly n_frames."""
    y, sr = librosa.load(path, sr=22050, mono=True)
    duration = len(y) / sr
    hop = int(sr/fps)
    n_frames = int(math.ceil(duration * fps))
    rms = librosa.feature.rms(y=y, frame_length=hop*2, hop_length=hop, center=True)[0]
    mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=n_mel_bands,
                                         hop_length=hop, n_fft=hop*4, fmin=40, fmax=8000)
    mel_n = np.clip((librosa.power_to_db(mel, ref=np.max)+60)/60, 0, 1)
    mel32 = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=n_spec_bars,
                                           hop_length=hop, n_fft=hop*4, fmin=40, fmax=10000)
    mel32_n = np.clip((librosa.power_to_db(mel32, ref=np.max)+60)/60, 0, 1)

    def pad(a, n):
        if a.shape[-1] < n:
            pw = n - a.shape[-1]
            return np.pad(a, ((0,0),(0,pw)) if a.ndim==2 else (0,pw), mode='edge')
        return a[..., :n]

    rms = pad(rms, n_frames); mel_n = pad(mel_n, n_frames); mel32_n = pad(mel32_n, n_frames)
    rms_n = rms / (rms.max()+1e-9)
    return dict(duration=duration, n_frames=n_frames, fps=fps,
                rms=rms_n.astype(np.float32),
                mel=mel_n.astype(np.float32),
                mel32=mel32_n.astype(np.float32))


# ====================== Grid → image rendering ======================

def render_grid_rle(draw, grid, font, cell_w, cell_h, y_offset=4):
    """Run-length-encoded grid render: for each row, group consecutive same-color
    chars into a single draw.text call. 100× faster than per-cell draw."""
    for r in range(len(grid)):
        y = r * cell_h + y_offset
        c = 0; row = grid[r]; ncols = len(row)
        while c < ncols:
            start = c
            _, col0 = row[c]
            while c < ncols and row[c][1] == col0:
                c += 1
            s = "".join(row[k][0] for k in range(start, c))
            x = start * cell_w
            draw.text((x, y), s, font=font, fill=col0 + (255,))


# ====================== FX passes ======================

def chrom_shift(img, shift=1):
    """Chromatic aberration: shift R left, B right by `shift` pixels.
    CAVEAT: at 1080p use shift=1; at 4K use shift=2. More than that blurs badly."""
    arr = np.asarray(img)
    r = np.roll(arr[:, :, 0], shift, axis=1)
    b = np.roll(arr[:, :, 2], -shift, axis=1)
    return Image.fromarray(np.stack([r, arr[:, :, 1], b], axis=2))


def grain_pass(img, seed, amount=5):
    """Film grain. amount is ±max-noise-value."""
    arr = np.asarray(img).astype(np.int16)
    rng = np.random.default_rng(seed)
    noise = rng.integers(-amount, amount+1, arr.shape, dtype=np.int16)
    return Image.fromarray(np.clip(arr+noise, 0, 255).astype(np.uint8))


def scanlines(img, every_n=4, brightness=0.95):
    """Darken every Nth row for CRT scanline look. brightness < 1."""
    arr = np.asarray(img).astype(np.int16)
    arr[1::every_n] = (arr[1::every_n] * brightness).astype(np.int16)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


# ====================== Multiprocessing render wrapper ======================

_WORKER_STATE = {}

def _mp_init_worker(compose_fn_module_name, compose_fn_name, feats, extra):
    """Load the compose function + any per-worker state once per worker."""
    import importlib
    mod = importlib.import_module(compose_fn_module_name)
    _WORKER_STATE["compose"] = getattr(mod, compose_fn_name)
    _WORKER_STATE["feats"] = feats
    _WORKER_STATE["extra"] = extra
    random.seed(os.getpid())
    np.random.seed(os.getpid() & 0xffffffff)


def _mp_render_frame(fi):
    """Call the compose function for a single frame. compose_fn signature:
    compose_fn(fi, t, feats, extra) -> PIL.Image"""
    random.seed(fi)
    np.random.seed(fi & 0xffffffff)
    t = fi / _WORKER_STATE["feats"]["fps"]
    img = _WORKER_STATE["compose"](fi, t, _WORKER_STATE["feats"], _WORKER_STATE["extra"])
    return fi, np.asarray(img).tobytes()


def render_video(audio_path, video_out, compose_fn_module, compose_fn_name,
                 w, h, fps, extra_state=None, n_workers=None,
                 use_nvenc=True, cq=22, preset="p4", chunksize=3):
    """Render an ASCII music video.

    - compose_fn_module:  module name where compose_fn lives (e.g. 'my_visualizer')
    - compose_fn_name:    name of the compose function inside that module
    - extra_state:        arbitrary picklable state to hand to each worker
                          (e.g. font paths, scene parameters)

    The compose function is called as compose_fn(fi, t, feats, extra) and must
    return a PIL RGB Image of size (w, h).
    """
    import multiprocessing as mp

    feats = analyze_audio(audio_path, fps)
    n_frames = feats["n_frames"]

    if n_workers is None:
        n_workers = max(1, os.cpu_count() - 2)

    encoder_args = (["-c:v", "h264_nvenc", "-preset", preset, "-cq", str(cq)]
                    if use_nvenc else ["-c:v", "libx264", "-preset", "medium",
                                       "-crf", "20"])
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{w}x{h}", "-r", str(fps),
        "-i", "-", "-an",
        *encoder_args,
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        video_out,
    ]
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    t_start = time.time()

    with mp.Pool(n_workers, initializer=_mp_init_worker,
                  initargs=(compose_fn_module, compose_fn_name, feats, extra_state)) as pool:
        for (fi_res, fb) in pool.imap(_mp_render_frame, range(n_frames), chunksize=chunksize):
            proc.stdin.write(fb)
            if fi_res % 60 == 0:
                el = time.time() - t_start
                rate = (fi_res+1)/max(0.001, el)
                eta = (n_frames - fi_res - 1)/max(0.001, rate)
                print(f"  frame {fi_res}/{n_frames}  {rate:5.2f} fps  eta={eta:6.1f}s", flush=True)

    proc.stdin.close()
    proc.wait()


# ====================== Muxing ======================

def mux_audio_video(audio_path, silent_video, output_path, audio_codec="mp3",
                    audio_bitrate="256k"):
    """Mux silent video with audio. MP3-in-MP4 is most compatible with
    older players (WMP); use 'aac' for modern-only."""
    if audio_codec == "mp3":
        acodec = ["-c:a", "libmp3lame", "-b:a", audio_bitrate,
                  "-ar", "44100", "-ac", "2"]
    else:
        acodec = ["-c:a", "aac", "-b:a", audio_bitrate,
                  "-ar", "44100", "-ac", "2"]
    cmd = [
        "ffmpeg", "-y",
        "-i", audio_path,
        "-i", silent_video,
        "-map", "1:v:0", "-map", "0:a:0",
        "-c:v", "copy",
        *acodec,
        "-disposition:a:0", "default",
        "-movflags", "+faststart",
        output_path,
    ]
    subprocess.run(cmd, check=True)


# ====================== Typewriter overlay helper ======================

def typewritten_lines(start_t, t, lines, char_rate=22.0):
    """For a timed reflection/journal panel. Returns list of (line_index,
    visible_char_count, full_line) — last entry is the currently-revealing line.

    Typical use: call with the current time, the panel's start time, and the
    list of lyric/thought lines. Render each entry up to visible_char_count.
    """
    elapsed = max(0, t - start_t)
    budget = elapsed * char_rate
    out = []; used = 0
    for i, ln in enumerate(lines):
        n = len(ln)
        if budget >= used + n:
            out.append((i, n, ln)); used += n + 4
        else:
            visible = max(0, int(budget - used))
            out.append((i, visible, ln))
            break
    return out
