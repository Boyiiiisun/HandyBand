"""Data structures shared by tracking, finger analysis, and rendering."""

from dataclasses import dataclass
from enum import IntEnum


class HandLandmark(IntEnum):
    """Indices in MediaPipe's 21-point hand landmark model."""

    WRIST = 0
    THUMB_CMC = 1
    THUMB_MCP = 2
    THUMB_IP = 3
    THUMB_TIP = 4
    INDEX_MCP = 5
    INDEX_PIP = 6
    INDEX_DIP = 7
    INDEX_TIP = 8
    MIDDLE_MCP = 9
    MIDDLE_PIP = 10
    MIDDLE_DIP = 11
    MIDDLE_TIP = 12
    RING_MCP = 13
    RING_PIP = 14
    RING_DIP = 15
    RING_TIP = 16
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_DIP = 19
    PINKY_TIP = 20


@dataclass(frozen=True, slots=True)
class Landmark:
    """A normalized three-dimensional landmark."""

    x: float
    y: float
    z: float
    visibility: float = 1.0


@dataclass(frozen=True, slots=True)
class FingerState:
    """The inferred state and tip position of one finger."""

    name: str
    extended: bool
    tip: Landmark


@dataclass(frozen=True, slots=True)
class HandObservation:
    """All information produced for one detected hand."""

    handedness: str
    confidence: float
    landmarks: tuple[Landmark, ...]
    fingers: tuple[FingerState, ...]


@dataclass(frozen=True, slots=True)
class ForearmObservation:
    """Elbow and midpoint anchors for one forearm."""

    handedness: str
    elbow: Landmark
    midpoint: Landmark
    wrist: Landmark
    confidence: float


@dataclass(frozen=True, slots=True)
class DrumEvent:
    """A classified drum strike ready for a future audio consumer."""

    handedness: str
    name: str
    speed: float
    volume: float
    timestamp_ms: int


@dataclass(frozen=True, slots=True)
class DrumGestureStatus:
    """Per-hand gesture state shown by the development overlay."""

    handedness: str
    phase: str
    open_hand: bool
    speed: float
    recent_event: DrumEvent | None


def correct_handedness(label: str, *, mirrored: bool) -> str:
    """Return anatomical handedness when inference used a mirrored frame."""

    if not mirrored:
        return label
    return {"Left": "Right", "Right": "Left"}.get(label, label)
