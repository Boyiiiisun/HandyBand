"""Portable, millisecond-based scores for guided gesture performances."""

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Note:
    start_ms: float
    duration_ms: float
    pitch: int
    velocity: int = 80


@dataclass(frozen=True)
class Cue:
    start_ms: float
    duration_ms: float
    gesture: int
    phrase: int
    notes: tuple[Note, ...]


@dataclass(frozen=True)
class Score:
    title: str
    bpm: float
    cues: tuple[Cue, ...]
    accompaniment: tuple[Note, ...] = ()
    source: str = ""
    is_demo: bool = False

    def __post_init__(self) -> None:
        if not math.isfinite(self.bpm) or not 20 <= self.bpm <= 300 or not self.cues:
            raise ValueError("Score needs cues and a tempo between 20 and 300 BPM")
        end = 0.0
        phrase = 0
        for cue in self.cues:
            if (not math.isfinite(cue.start_ms) or not math.isfinite(cue.duration_ms)
                    or cue.start_ms < end or cue.duration_ms < 500
                    or cue.gesture not in (1, 2, 4, 5) or cue.phrase < phrase):
                raise ValueError("Cues must be ordered, non-overlapping and use gestures 1,2,4,5")
            if not cue.notes:
                raise ValueError("Every cue must contain melody notes")
            for note in cue.notes:
                self._validate_note(note, cue.duration_ms)
            end = cue.start_ms + cue.duration_ms
            phrase = cue.phrase
        for note in self.accompaniment:
            self._validate_note(note, end)

    @staticmethod
    def _validate_note(note: Note, end: float) -> None:
        if (not math.isfinite(note.start_ms) or not math.isfinite(note.duration_ms)
                or note.start_ms < 0 or note.duration_ms <= 0
                or note.start_ms + note.duration_ms > end + 1
                or not 0 <= note.pitch <= 127 or not 1 <= note.velocity <= 127):
            raise ValueError("Invalid note timing, pitch or velocity")

    @property
    def duration_ms(self) -> float:
        return self.cues[-1].start_ms + self.cues[-1].duration_ms

    @property
    def phrases(self) -> tuple[int, ...]:
        return tuple(dict.fromkeys(cue.phrase for cue in self.cues))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")


def load_score(path: Path) -> Score:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Score(
        title=data["title"], bpm=data["bpm"],
        cues=tuple(Cue(**{**cue, "notes": tuple(Note(**n) for n in cue["notes"])})
                   for cue in data["cues"]),
        accompaniment=tuple(Note(**n) for n in data.get("accompaniment", [])),
        source=data.get("source", ""), is_demo=data.get("is_demo", False),
    )


def training_score() -> Score:
    """An original interaction exercise; deliberately NOT Cornfield Chase."""
    pitches = (60, 64, 67, 72, 67, 64, 60, 64)
    gestures = (1, 2, 4, 5, 4, 2, 1, 2)
    return Score(
        title="Gesture training (not Cornfield Chase)", bpm=80, is_demo=True,
        cues=tuple(Cue(i * 2250, 2250, g, i // 4,
                       (Note(0, 1850, p),))
                   for i, (p, g) in enumerate(zip(pitches, gestures, strict=True))),
        accompaniment=tuple(Note(i * 2250, 2100, 48 if i < 4 else 43, 40)
                            for i in range(8)),
        source="Original HandyBand control exercise, not a transcription of the film score.",
    )
