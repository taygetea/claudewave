# claudewave

A [Claude Code](https://claude.com/claude-code) skill for building vaporwave/slushwave/citypop/chillwave remixes and sound-reactive ASCII music videos of existing songs.

Claude handles the whole pipeline: stem separation, per-instrument MIDI transcription, beat-tracked arrangement, programmatic synth rebuild, genre-specific DSP, and 1080p60 ASCII visualizers with per-song reflections.

## What it does

Given an mp3/wav, Claude will:

1. Separate it into 4 stems (demucs).
2. Transcribe bass + harmonic instruments to MIDI (basic-pitch) for pitch/chord info.
3. Beat-track the original for the rhythm grid.
4. Detect chord progression (including jazz extensions).
5. (Optional) Generate AI atmosphere pads + m2m vocal style transfer via a local ComfyUI server with ACE-Step.
6. (Optional) Extract monophonic melodies (whistle/lead) with pYIN.
7. Rebuild the track with programmatic synth voices (FM Rhodes, slap bass, sub, bell, Juno pad, whistle, vocoder).
8. Apply genre-specific DSP (chorus/phaser/reverb/tape wobble/sidechain pump/chopped hook loops).
9. Render a 1080p60 ASCII music video with scene visuals + a reflection panel with AI/lyric-related commentary.
10. Mux the final video with MP3-in-MP4 for broad compatibility.

## Install

See [`setup.md`](setup.md) for full install commands. Summary:

- **ffmpeg** (with `libx264`, `libmp3lame`, optionally `h264_nvenc` for GPU encode)
- **Python 3.13** main env: `librosa soundfile scipy numpy pedalboard demucs Pillow music21`
- **Python 3.12** side env (for `basic-pitch` which has deps that don't build on 3.13): `basic-pitch onnxruntime pretty_midi librosa soundfile scipy`
- Optional: a local **ComfyUI** server at `127.0.0.1:8188` with `ace_step_1.5_turbo_aio.safetensors` and `ace_step_v1_3.5b.safetensors` for AI music generation

## Use

Add the skill directory to Claude Code's skills path, then just ask:

> make a slushwave remix of this track with a music video

> turn this into a citypop cover

> vaporwave this, use the chorus line as an eccojam loop

> build a sound-reactive ASCII visualizer for this song

Claude will work through the pipeline with you, previewing intermediate results and iterating based on feedback.

## Subgenre guide

See [`SKILL.md`](SKILL.md) for the full subgenre quick-reference table. Rough guidance on matching sources to treatments:

- **slushwave** — extreme slowdown, drifting, for ambient/new-age sources
- **classic vaporwave** — chopped & screwed, for smooth jazz / 80s R&B / synth-pop
- **eccojams** — hypnotic single-phrase loops
- **mallsoft** — cavernous spacious ambient, for lounge / easy listening
- **future funk** — upbeat, for disco / soul / city pop
- **citypop (claudewave)** — clean, polished, FM Rhodes + slap bass, for any melodic song
- **chillwave / dreampop** — warm nostalgic, for folk / indie

## Credits

Created through iterative collaboration with Claude (Opus 4.7) on a couple of songs. The patterns and pitfalls in this skill are hard-won from that session.

Research sources and credits in [`SKILL.md`](SKILL.md).

License: MIT.
