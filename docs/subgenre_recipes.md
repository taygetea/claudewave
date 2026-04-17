# Subgenre Recipes

Parameter cheatsheet for each -wave subgenre. Start from these numbers and dial in.

## Slushwave

Dreamy, drifting, almost rhythmless. Vocals drowned in reverb.

```python
SLOW_RATIO = 0.65     # 35% slow — extreme screw
tape_wobble(rate_hz=0.32, depth=70, flutter_rate=5.6)
# vocals
Chorus(rate=0.55, depth=0.7, mix=0.55)
Phaser(rate=0.25, depth=0.8, centre=800, mix=0.4)
Delay(delay=0.85, feedback=0.55, mix=0.38)
Reverb(room=0.95, damping=0.5, wet=0.55, dry=0.55)
# instrumental: even wetter/slower
# NO drums. NO synth bass. Chord pad only, held very long.
# Heavy vinyl crackle (density=150, level=0.04)
```

## Classic vaporwave (Floral Shoppe style)

Chopped + screwed 80s R&B / smooth jazz.

```python
SLOW_RATIO = 0.80     # 20% slow — classic screw
# Chop a hook phrase and loop it hypnotically at chorus moments
# vocals
Chorus(rate=0.55, mix=0.30)
Delay(delay=0.40, feedback=0.35, mix=0.25)
Reverb(room=0.88, wet=0.35, dry=0.85)
# instrumental
Chorus(rate=0.32, depth=0.7, mix=0.6)
Phaser(rate=0.12, depth=0.85, centre=500, mix=0.5)
Delay(delay=0.65, feedback=0.52, mix=0.38)
Reverb(room=0.97, wet=0.7, dry=0)
LowpassFilter(5800)
# + sidechain pump at BPM*SLOW
# + vinyl crackle density=90
```

## Eccojams

Take a single hook phrase from the vocal stem, loop it hypnotically with staggered copies + decaying gain. The "rest of the song" is optional — traditional eccojams is just the loop, nothing else. Use long reverb.

```python
from claudewave.lib.choppers import extract_hook, place_hook_loops
hook = extract_hook(vocals_slowed, start=15.0, end=23.0, sr=SR)  # 8s phrase
drops = [(0.0, 6, 4.5), (60.0, 6, 4.5), (120.0, 6, 4.5)]  # loop 6 times every minute
# heavy reverb + LP on the hook
# minimal or no other layers
```

## Mallsoft

Cavernous, ambient, "empty mall" feel. Keep vocals but bury them in reverb.

```python
SLOW_RATIO = 0.88     # subtle slow
Reverb(room=0.99, damping=0.45, wet=0.7, dry=0.4)  # massive decay
# No drums. Very slow pad only. Low-passed so highs don't cut through.
# Add occasional bell chimes + subtle footsteps-reverberating-off-tile ambience
# Use render_water() from lib.ambience for the "fountain" sound
```

## Citypop (claudewave variant)

The opposite of slushwave — clean, polished, minimal slow, clear vocals, full band.

```python
SLOW_RATIO = 0.96     # just a hint of warmth (~-0.7 st)
# vocals — DRY for clarity
Chorus(rate=0.65, depth=0.2, mix=0.22)
Delay(delay=0.30, feedback=0.22, mix=0.14)
Reverb(room=0.72, wet=0.22, dry=0.90)  # drier than vaporwave
# REBUILD from 4-stem MIDI:
#   drums: shaker 8ths + kick 1&3 + brush snare 2&4 + hat offbeats
#   bass: slap_bass on root beat-1, fifth beat-3
#   keys: rhodes comp on beats 2&4 (syncopated)
#   pad: juno per bar
# All on librosa.beat_track grid — no basic-pitch timing for rhythm!
```

## Chillwave / Dreampop

Warm, nostalgic, summer-memory. Not quite vaporwave, not quite synthpop.

```python
SLOW_RATIO = 0.90     # subtle
Chorus(rate=0.45, depth=0.35, mix=0.3)
Phaser(rate=0.15, depth=0.7, centre=650, mix=0.3)
Delay(delay=0.55, feedback=0.4, mix=0.28)
Reverb(room=0.88, wet=0.4, dry=0.65)
# Warm pad + FM Rhodes + sub bass, soft lo-fi drum groove
# Optional: cricket/water ambience (from ambience.py)
```

## Future Funk

Upbeat, disco-chopped, vocal stutters. NOT slowed — maybe even sped up.

```python
SLOW_RATIO = 1.00 or 1.05   # original speed or slight speedup
# Chopped vocal stabs — grab short vocal slices, resequence on the beat grid
# Punchy kick on every beat (4-on-the-floor)
# Funk bass arpeggio between chord roots
# Filter sweep on the chord pad (LP cutoff automation)
# BPM 100-120
```

## Hardvapour

Vaporwave meets speedcore. Rare and niche.

```python
# Slow the source heavily BUT run harsh distortion + loud kick over it
# Slow vocals 70%, then overlay hardstyle kick pattern at 170+ BPM
# Clash is the point. Keep the vocals identifiable through the noise.
```

---

## Universal master bus

All subgenres share some master-bus moves. Tune by taste:

```python
Pedalboard([
    LowShelfFilter(cutoff=120, gain_db=+1 to +1.5),    # warmth
    HighShelfFilter(cutoff=9000, gain_db=-2 to +1.5),  # bright for citypop, dark for slushwave
    Compressor(threshold=-18, ratio=2.0, attack=20, release=200),  # glue
    Distortion(drive_db=1.5 to 3.0),                   # optional tape saturation
    Gain(gain_db=-1 to -1.5),                          # headroom
])
# fade in 2-3s, fade out 6-8s
```

## Pitch-match rule

Critical: if you slow the vocal stem by a ratio, you also drop its pitch. All synth notes must be pitch-shifted by the same ratio to stay in tune:

```python
f = midi_to_hz(pitch) * SLOW_RATIO   # this is what lib/synths.py::midi_to_hz(slow=...) does
```

Don't forget this. Synths sharp by half a semitone against slowed vocals sounds terrible.
