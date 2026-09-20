"""Inspect a local MIDI, then create a trimmed guided score with separate backing."""

import argparse
import bisect
import math
from collections import defaultdict, deque
from pathlib import Path

import mido

from handyband.guided_score import Cue, Note, Score


def read_midi(path: Path) -> tuple[list[list[Note]], float, int]:
    midi = mido.MidiFile(path)
    if midi.type == 2 or midi.ticks_per_beat <= 0:
        raise ValueError("Use a synchronous type 0/1 MIDI with beat-based timing")
    absolute = []
    tempos = {0: 500_000}
    for track in midi.tracks:
        tick = 0
        events = []
        for message in track:
            tick += message.time
            events.append((tick, message))
            if message.type == "set_tempo":
                tempos[tick] = message.tempo
        absolute.append(events)
    ticks = sorted(tempos)
    elapsed = [0.0]
    for i in range(1, len(ticks)):
        elapsed.append(elapsed[-1] + mido.tick2second(
            ticks[i] - ticks[i - 1], midi.ticks_per_beat, tempos[ticks[i - 1]]) * 1000)

    def to_ms(tick: int) -> float:
        i = bisect.bisect_right(ticks, tick) - 1
        return elapsed[i] + mido.tick2second(
            tick - ticks[i], midi.ticks_per_beat, tempos[ticks[i]]) * 1000

    tracks = []
    for events in absolute:
        held = defaultdict(deque)
        sustained = defaultdict(list)
        pedal = defaultdict(bool)
        notes = []

        def finish(start: int, end: int, pitch: int, velocity: int, notes=notes) -> None:
            if end > start:
                notes.append(Note(to_ms(start), to_ms(end) - to_ms(start), pitch, velocity))

        for tick, msg in events:
            if msg.type == "note_on" and msg.velocity:
                held[(msg.channel, msg.note)].append((tick, msg.velocity))
            elif msg.type in ("note_off", "note_on"):
                key = (msg.channel, msg.note)
                if held[key]:
                    start, velocity = held[key].popleft()
                    if pedal[msg.channel]:
                        sustained[msg.channel].append((start, msg.note, velocity))
                    else:
                        finish(start, tick, msg.note, velocity)
            elif msg.type == "control_change" and msg.control == 64:
                pedal[msg.channel] = msg.value >= 64
                if not pedal[msg.channel]:
                    for start, pitch, velocity in sustained.pop(msg.channel, []):
                        finish(start, tick, pitch, velocity)
        end = events[-1][0] if events else 0
        for (_, pitch), queue in held.items():
            for start, velocity in queue:
                finish(start, end, pitch, velocity)
        for queue in sustained.values():
            for start, pitch, velocity in queue:
                finish(start, end, pitch, velocity)
        tracks.append(sorted(notes, key=lambda note: (note.start_ms, note.pitch)))
    return tracks, mido.tempo2bpm(tempos[0]), midi.ticks_per_beat


def make_score(tracks: list[list[Note]], bpm: float, melody_track: int,
               start_ms: float, end_ms: float, cue_beats: float, source: str) -> Score:
    if not 0 <= melody_track < len(tracks) or not tracks[melody_track]:
        raise ValueError("Select a track containing melody notes")
    duration = end_ms - start_ms
    if (not all(math.isfinite(x) for x in (start_ms, end_ms, cue_beats))
            or start_ms < 0 or duration < 1000 or cue_beats * 60_000 / bpm < 500):
        raise ValueError("Supply a positive cue length and a clip of at least one second")
    if end_ms > max(n.start_ms + n.duration_ms for track in tracks for n in track) + 1000:
        raise ValueError("Clip end exceeds the MIDI duration")
    step = cue_beats * 60_000 / bpm

    def clip(notes, start, end):
        return tuple(Note(max(n.start_ms, start) - start,
                          min(n.start_ms + n.duration_ms, end) - max(n.start_ms, start),
                          n.pitch, n.velocity)
                     for n in notes if n.start_ms < end and n.start_ms + n.duration_ms > start)

    chunks = []
    at = start_ms
    while at < end_ms - 1:
        stop = min(at + step, end_ms)
        if end_ms - stop < 500:
            stop = end_ms
        notes = clip(tracks[melody_track], at, stop)
        if notes:
            # One gesture selects a contextual musical unit, not a universal pitch.
            onset = min(n.start_ms for n in notes)
            anchor = max(n.pitch for n in notes if n.start_ms < onset + 30) % 12
            chunks.append((at - start_ms, stop - at, anchor, notes))
        at = stop
    anchors = sorted({chunk[2] for chunk in chunks})
    gestures = (1, 2, 4, 5)
    mapping = {pitch: gestures[min(3, i * 4 // len(anchors))]
               for i, pitch in enumerate(anchors)}
    cues = tuple(Cue(at, length, mapping[anchor], i // 4, notes)
                 for i, (at, length, anchor, notes) in enumerate(chunks))
    backing = clip([n for i, track in enumerate(tracks) if i != melody_track for n in track],
                   start_ms, end_ms)
    # Trim backing to the final non-empty cue, so validation and finish agree.
    final = cues[-1].start_ms + cues[-1].duration_ms if cues else duration
    backing = clip(backing, 0, final)
    return Score("Cornfield Chase - MIDI arrangement", bpm, cues, backing, source)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("midi", type=Path)
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--melody-track", type=int)
    parser.add_argument("--start", type=float, default=0, help="Clip start in seconds")
    parser.add_argument("--end", type=float, help="Required explicit clip end in seconds")
    parser.add_argument("--cue-beats", type=float, default=6)
    parser.add_argument("--source", default="Local MIDI supplied by the user")
    parser.add_argument("--output", type=Path,
                        default=Path("HandyBand_Audio/Interstellar/score.json"))
    args = parser.parse_args()
    try:
        tracks, bpm, _ = read_midi(args.midi)
        if args.inspect:
            print(f"Initial tempo: {bpm:.2f} BPM (tempo changes respected in note times)")
            for i, notes in enumerate(tracks):
                if notes:
                    bounds = f"{min(n.pitch for n in notes)}..{max(n.pitch for n in notes)}"
                    print(f"Track {i}: {len(notes)} notes; pitch {bounds}")
                else:
                    print(f"Track {i}: no notes")
            return
        if args.melody_track is None or args.end is None:
            parser.error("Use --inspect, then specify --melody-track and --end")
        score = make_score(tracks, bpm, args.melody_track, args.start * 1000,
                           args.end * 1000, args.cue_beats, args.source)
        score.save(args.output)
        print(f"Saved {len(score.cues)} cues, {score.duration_ms / 1000:.2f}s to {args.output}")
    except (ValueError, OSError, EOFError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
