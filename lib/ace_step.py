"""
Helpers for queuing ACE-Step workflows against a local ComfyUI server.

Two main use cases:
  1. Generate an atmospheric pad (text-to-music) with ACE-Step 1.5.
  2. Do m2m (audio-to-audio) style transfer with ACE-Step v1.
"""
import json, urllib.request, uuid, os, time


COMFY_API = "http://127.0.0.1:8188"


def queue_workflow(workflow_dict, api_url=COMFY_API, timeout=30):
    """Submit a workflow (the 'prompt' graph JSON) to ComfyUI. Returns prompt_id."""
    payload = json.dumps({"prompt": workflow_dict, "client_id": str(uuid.uuid4())}).encode()
    req = urllib.request.Request(f"{api_url}/prompt", data=payload,
                                  headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=timeout).read()
        return json.loads(r.decode())["prompt_id"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"ComfyUI queue failed ({e.code}): {e.read().decode()}")


def wait_for_output(prompt_id, output_dir, prefix, api_url=COMFY_API,
                    poll_every=3.0, timeout=1200.0):
    """Poll the ComfyUI history until this prompt_id finishes, then return the
    first produced audio filename under output_dir."""
    start = time.time()
    while time.time() - start < timeout:
        r = urllib.request.urlopen(f"{api_url}/history?max_items=50", timeout=10).read()
        h = json.loads(r.decode())
        if prompt_id in h:
            for node_id, o in h[prompt_id].get("outputs", {}).items():
                for a in o.get("audio", []):
                    if a["filename"].startswith(prefix):
                        sub = a.get("subfolder", "")
                        return os.path.join(output_dir, sub, a["filename"])
            return None
        time.sleep(poll_every)
    raise TimeoutError(f"ACE-Step job {prompt_id} did not finish in {timeout}s")


def build_ace15_generation(tags, duration_s, bpm, keyscale="C major",
                            seed=42, cfg=5.0, steps=26,
                            negative_tags="harsh, distorted, noisy, aggressive",
                            filename_prefix="ace_pad"):
    """Build an ACE-Step 1.5 text-to-music workflow dict ready to queue.

    Returns a workflow dict you can pass to queue_workflow().
    """
    return {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": "ace_step_1.5_turbo_aio.safetensors"}},
        "2": {"class_type": "EmptyAceStep1.5LatentAudio",
              "inputs": {"seconds": float(duration_s), "batch_size": 1}},
        "3": {"class_type": "TextEncodeAceStepAudio1.5",
              "inputs": {
                  "clip": ["1", 1],
                  "tags": tags,
                  "lyrics": "[instrumental]",
                  "seed": seed, "bpm": int(bpm), "duration": float(duration_s),
                  "timesignature": "4", "language": "en", "keyscale": keyscale,
                  "generate_audio_codes": True, "cfg_scale": 2.0,
                  "temperature": 0.95, "top_p": 0.9, "top_k": 0, "min_p": 0.0,
              }},
        "4": {"class_type": "TextEncodeAceStepAudio1.5",
              "inputs": {
                  "clip": ["1", 1], "tags": negative_tags, "lyrics": "",
                  "seed": 1, "bpm": int(bpm), "duration": float(duration_s),
                  "timesignature": "4", "language": "en", "keyscale": keyscale,
                  "generate_audio_codes": True, "cfg_scale": 2.0,
                  "temperature": 0.85, "top_p": 0.9, "top_k": 0, "min_p": 0.0,
              }},
        "5": {"class_type": "KSampler",
              "inputs": {
                  "model": ["1", 0], "positive": ["3", 0], "negative": ["4", 0],
                  "latent_image": ["2", 0], "seed": seed, "steps": steps,
                  "cfg": cfg, "sampler_name": "euler", "scheduler": "simple",
                  "denoise": 1.0,
              }},
        "6": {"class_type": "VAEDecodeAudio",
              "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveAudio",
              "inputs": {"audio": ["6", 0], "filename_prefix": filename_prefix}},
    }


def build_ace_v1_m2m(audio_filename_in_comfy_input, tags, lyrics,
                      seed=42, denoise=0.55, steps=40, cfg=4.5,
                      negative_tags="rock, aggressive, loud, harsh",
                      filename_prefix="ace_m2m"):
    """ACE-Step v1 m2m style transfer. audio_filename_in_comfy_input must be a file
    located inside ComfyUI/input/ directory (copy it there first).
    denoise ~0.5-0.6 preserves structure while changing style; 0.3 is subtle;
    0.7+ loses most of the original."""
    return {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": "ace_step_v1_3.5b.safetensors"}},
        "2": {"class_type": "LoadAudio",
              "inputs": {"audio": audio_filename_in_comfy_input}},
        "3": {"class_type": "VAEEncodeAudio",
              "inputs": {"audio": ["2", 0], "vae": ["1", 2]}},
        "4": {"class_type": "TextEncodeAceStepAudio",
              "inputs": {"clip": ["1", 1], "tags": tags, "lyrics": lyrics,
                          "lyrics_strength": 1.0}},
        "5": {"class_type": "TextEncodeAceStepAudio",
              "inputs": {"clip": ["1", 1], "tags": negative_tags,
                          "lyrics": "", "lyrics_strength": 1.0}},
        "6": {"class_type": "KSampler",
              "inputs": {"model": ["1", 0], "positive": ["4", 0],
                          "negative": ["5", 0], "latent_image": ["3", 0],
                          "seed": seed, "steps": steps, "cfg": cfg,
                          "sampler_name": "euler", "scheduler": "simple",
                          "denoise": denoise}},
        "7": {"class_type": "VAEDecodeAudio",
              "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveAudio",
              "inputs": {"audio": ["7", 0], "filename_prefix": filename_prefix}},
    }


# -- Tag presets ------------------------------------------------------------

TAG_PRESETS = {
    "slushwave":    "slushwave, vaporwave, hypnagogic, ambient, drone pad, dreamy, hazy, heavy reverb, shimmer reverb, warm analog tape, soft phaser, lush strings, cloud pad, underwater, melancholic, midnight, deep slow drift, warm cassette, pad ensemble, glassy bells, long decay, lofi, distant echo",
    "vaporwave":    "vaporwave, chopped and screwed, slowed and reverb, 80s smooth jazz, soft female vocal, ethereal, dreamy, hazy, heavy reverb, warm tape, mallsoft, aesthetic, pink afternoon, 80 bpm",
    "mallsoft":     "mallsoft, ambient vaporwave, empty mall, escalator, smooth jazz muzak, cavernous reverb, spacious, dreamy, 90s corporate, tile floor echo, fluorescent lights, suburban dream",
    "citypop":      "city pop, tatsuro yamashita style, mariya takeuchi, neon tokyo, 1984, lush FM electric piano, warm analog synth, smooth jazz bossa shuffle, slap bass, shaker, brushed snare, DX7 Rhodes, pastel chords, maj7 extensions, instrumental, lush strings, twilight city, nostalgic, polished, mid-tempo, urban nightlife",
    "chillwave":    "nostalgic dreampop, warm chillwave, analog synthesizer, mellow FM electric piano, soft juno pad, sunset, summer memory, gentle arpeggio, warm tape, soft sub bass, lush reverb, shimmering bells, instrumental, spacious, dewy, cinematic, yearning",
    "future_funk":  "future funk, nu-disco, chopped disco vocal, funk guitar, slap bass, punchy drums, french house, filter sweep, warm saturation, hedonistic, uplifting, summer, 110 bpm",
}
