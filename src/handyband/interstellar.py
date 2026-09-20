"""Interstellar theme: guided single-hand melody with independent accompaniment."""

import math
from pathlib import Path

import cv2
import numpy as np

from handyband.finger_gesture import GESTURE_PATTERNS, classify_numbered_gesture
from handyband.guided_audio import GuidedAudio
from handyband.guided_score import load_score, training_score
from handyband.guided_session import GuidedSession

DEFAULT_SCORE_PATH = Path("HandyBand_Audio/Interstellar/score.json")
COLORS = {1: (225, 193, 98), 2: (147, 219, 130), 4: (131, 170, 242), 5: (229, 149, 199)}
INSTRUCTIONS = {
    1: "Index up; fold the other fingers",
    2: "Index + middle up; fold the others",
    4: "Four fingers up; fold your thumb",
    5: "Open palm; all five fingers up",
}


def label(image, text, x, y, size=0.6, color=(224, 229, 242)):
    cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, size, color, 1, cv2.LINE_AA)


def draw_hand(image, gesture, center, scale=1.0, hand="Right"):
    """Use the actual classifier patterns as the diagram's single source of truth."""
    pattern = next(pattern for pattern, value in GESTURE_PATTERNS.items() if value == gesture)
    cx, cy = center
    color = COLORS[gesture]
    mirror = 1 if hand == "Right" else -1

    def point(x, y):
        return (round(cx + mirror * x * scale), round(cy + y * scale))

    cv2.rectangle(image, point(-27, 0), point(27, 52), color, max(1, round(2 * scale)))
    for i, extended in enumerate(pattern):
        x = (-42, -22, -6, 10, 26)[i]
        start = point(-27 if i == 0 else x, 25 if i == 0 else 0)
        tip = point(x, (-12 if i == 0 else (-52, -67, -58, -38)[i - 1])
                    if extended else 17)
        cv2.line(image, start, tip, color, max(2, round(8 * scale)), cv2.LINE_AA)
        cv2.circle(image, tip, max(2, round(4 * scale)), (245, 245, 245), -1, cv2.LINE_AA)


class Interstellar:
    name = "Interstellar"

    def __init__(self, score_path: Path = DEFAULT_SCORE_PATH) -> None:
        score = load_score(score_path) if score_path.is_file() else training_score()
        self.session = GuidedSession(score)
        self.audio = GuidedAudio(score)
        self.detected: int | None = None
        self.tracked = False
        self.score_path = score_path

    def update(self, hands, timestamp_ms: int) -> None:
        hand = next((h for h in hands if h.handedness == self.session.hand), None)
        self.tracked = hand is not None
        self.detected = classify_numbered_gesture(hand) if hand is not None else None
        self.session.update(timestamp_ms, self.detected, self.tracked)
        self.audio.sync(self.session)

    def on_key(self, key: int) -> None:
        session = self.session
        if key == 32:
            session.toggle_pause()
        elif key in (ord("t"), ord("p"), ord("e")):
            session.set_mode({ord("t"): "Tutorial", ord("p"): "Practice",
                              ord("e"): "Perform"}[key])
        elif key in (ord("l"), ord("r")):
            session.hand = "Left" if key == ord("l") else "Right"
            session.reset()
        elif key in (ord("n"), ord("b")):
            session.step_phrase(1 if key == ord("n") else -1)
        elif key == ord("a"):
            missed = sorted(session.misses | session.cut_short)
            if missed:
                session.phrase = session.score.cues[missed[0]].phrase
                session.set_mode("Practice")
        else:
            return
        # Mode/hand changes and pauses stop sound immediately, without a stale frame.
        self.audio.stop()

    def draw(self, camera: np.ndarray) -> np.ndarray:
        session = self.session
        canvas = np.zeros((640, 960, 3), dtype=np.uint8)
        canvas[:] = (25, 16, 13)
        for i in range(65):
            x, y = (i * 137 + 23) % 960, (i * 83 + 41) % 550
            cv2.circle(canvas, (x, y), 1, (75, 62, 54), -1)
        label(canvas, "INTERSTELLAR", 28, 38, 0.9)
        label(canvas, session.score.title, 28, 74, 0.52)
        label(canvas, f"{session.mode}  |  {session.hand} hand  |  "
              f"Phrase {session.cue.phrase + 1}/{len(session.score.phrases)}", 28, 103, 0.53)
        if session.score.is_demo:
            label(canvas, "TRAINING ONLY - import a MIDI to play Cornfield Chase", 28, 130,
                  0.5, (110, 190, 255))
        else:
            label(canvas, "Assisted MIDI arrangement / gesture = musical unit", 28, 130, 0.48)
        cv2.line(canvas, (80, 253), (710, 253), (85, 78, 68), 2)
        cv2.line(canvas, (140, 153), (140, 258), (234, 233, 206), 2)
        label(canvas, "PLAY", 120, 270, 0.45)
        upcoming = session.indices[session.cursor:session.cursor + 3]
        for ordinal, index in enumerate(upcoming):
            cue = session.score.cues[index]
            lead = cue.start_ms - session.position_ms
            if session.mode == "Tutorial":
                x = 140 + ordinal * 215
            else:
                x = min(670, max(140, round(140 + lead / 18)))
            cv2.rectangle(canvas, (x - 43, 156), (x + 43, 250), COLORS[cue.gesture], 1)
            draw_hand(canvas, cue.gesture, (x, 192), 0.42, session.hand)
            label(canvas, str(cue.gesture), x - 6, 242, 0.55, COLORS[cue.gesture])
            if ordinal > 0:
                label(canvas, f"next {ordinal}", x - 24, 151, 0.35)
        cue = session.cue
        draw_hand(canvas, cue.gesture, (175, 388), 1.25, session.hand)
        label(canvas, f"SHAPE {cue.gesture}", 300, 325, 0.85, COLORS[cue.gesture])
        label(canvas, INSTRUCTIONS[cue.gesture], 300, 359, 0.56)
        label(canvas, "Palm toward camera", 300, 387, 0.5)
        label(canvas, session.feedback, 300, 424, 0.49, (160, 222, 183))
        remaining = max(0.0, min(1.0,
                        (cue.start_ms + cue.duration_ms - session.position_ms) / cue.duration_ms))
        cv2.ellipse(canvas, (175, 385), (96, 107), -90, 0, round(360 * remaining),
                    COLORS[cue.gesture], 2, cv2.LINE_AA)
        cv2.rectangle(canvas, (300, 451), (690, 463), (65, 57, 48), -1)
        cv2.rectangle(canvas, (300, 451), (300 + round(390 * remaining), 463),
                      COLORS[cue.gesture], -1)
        label(canvas, "HOLD until the bar runs out; then change / relax", 300, 487, 0.42)
        preview = cv2.resize(camera, (200, 150))
        canvas[320:470, 735:935] = preview
        label(canvas, f"Detected: {self.detected or '--'}", 740, 494, 0.48)
        label(canvas, "Tracked" if self.tracked else "Hand not found", 740, 518, 0.45)
        if session.state == "Countdown":
            beats = session.countdown_ms * session.score.bpm / 60_000
            radius = 28 + round(18 * (beats % 1))
            cv2.circle(canvas, (820, 222), radius, (178, 205, 235), 2, cv2.LINE_AA)
            label(canvas, str(max(1, math.ceil(beats))), 809, 232, 0.9)
        else:
            label(canvas, session.state.upper(), 737, 226, 0.55)
        label(canvas, f"Matched {len(session.hits)}/{len(session.indices)}  |  "
              f"Missed {len(session.misses)}  |  Released early {len(session.cut_short)}",
              28, 538, 0.53)
        cv2.rectangle(canvas, (0, 556), (960, 640), (37, 27, 22), -1)
        label(canvas, "SPACE Start/Pause   T Tutorial   P Practice   E Perform", 28, 582, 0.55)
        label(canvas, "L/R Hand   B/N Phrase   A Retry missed phrase   Q/Esc Exit", 28, 612, 0.53)
        return canvas

    def close(self) -> None:
        self.audio.close()
