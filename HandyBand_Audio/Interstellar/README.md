# Interstellar / Cornfield Chase

This folder contains the locally imported MIDI arrangement for the third theme.
The program renders it with a soft organ/piano-like synthesizer; it is **not the
film soundtrack recording**. No external soundfont or online playback is needed.

## Sources inspected on 2026-09-19

- [Official WaterTower soundtrack listing](https://www.watertower-music.com/release/interstellar-original-motion-picture-soundtrack-expanded-edition/)
- [Official original recording for comparison](https://www.youtube.com/watch?v=JuSsvM8B4Jc)
- [Downloaded MIDI: Nonstop2k, arranged by msluetz](https://www.nonstop2k.com/midi-files/21091-hans-zimmer-cornfield-chase-interstellar-soundtrack-midi.html)

The Nonstop2k page offers a regular/free download and describes educational/remix
use. This is not evidence of permission to redistribute Hans Zimmer's composition
or this arrangement with an MIT-licensed application. The downloaded `source.mid`,
derived `score.json`, and rendered WAV files are local-only and ignored by Git.
The application code's MIT license does not grant rights to these music assets.

## Selected excerpt

The downloaded MIDI has 480 ticks per quarter note, 3/4 meter, initial tempo
94 BPM, duration approximately 122.55 seconds, and two note-bearing tracks:

| Track index | Role used here | Notes in full MIDI |
| --- | --- | --- |
| 0 | User-controlled musical units (including right-hand voicings) | 718 |
| 1 | Automatic lower accompaniment | 544 |

Default excerpt: **0 to 30.638256 seconds**, the first 16 bars, ending before bar
17. At bar 17 the lower track changes from sparse bass chords to twelve note
onsets per bar. This is a conservative, score-based interpretation of "before
the busy music" for this particular arrangement, not a verified timestamp in
the original soundtrack. Audition the local preview and adjust the end if needed.

There are eight six-beat musical units, grouped into two practice phrases.
Gestures 1, 2, 4, 5 select the prompted unit in context, rather than always mapping
to one pitch. The MIDI's actual note timing and velocity are preserved within
each unit. Notes crossing unit boundaries are clipped/split. Other MIDI expression
such as pitch bends, reverb and program changes is not synthesized; sustain pedal
and tempo changes are parsed. Unit spacing uses the initial tempo, so for a
variable-tempo excerpt manually review/edit the resulting cue boundaries.

## Reproduce / change the excerpt

Download the regular/free MIDI using the source page's **DOWNLOAD MIDI** button
and save it here as `source.mid`. Then run from the repository root:

```powershell
python scripts/import_interstellar.py HandyBand_Audio/Interstellar/source.mid --inspect
python scripts/import_interstellar.py HandyBand_Audio/Interstellar/source.mid --melody-track 0 --end 30.638256 --cue-beats 6 --source "https://www.nonstop2k.com/midi-files/21091-hans-zimmer-cornfield-chase-interstellar-soundtrack-midi.html"
python -m handyband --style Interstellar
```

`--start` / `--end` are seconds in the chosen MIDI, not in the official recording.
`--melody-track` uses the zero-based index printed by `--inspect`. All other
tracks become accompaniment, so inspect the source before selecting this value.
An arbitrary mixed single-track MIDI cannot automatically isolate its melody.

An absent `score.json` loads an explicitly labelled original gesture exercise,
**not Cornfield Chase**. A malformed score reports an error instead of silently
substituting music. Use `--score path/to/score.json` to load a different prepared
score. The JSON uses milliseconds; notes within each cue use relative times,
while accompaniment notes use times relative to the whole excerpt.
