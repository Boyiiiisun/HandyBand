"""Music styles and their gesture/audio pairing."""

from pathlib import Path

from handyband.drum_audio import DrumAudioPlayer
from handyband.drum_gesture import DrumGestureRecognizer
from handyband.finger_audio import FingerAudioPlayer
from handyband.finger_gesture import FingerGestureRecognizer


class Odysseus:
    """Arm-downstroke drums plus numbered finger gestures."""

    name = "Odysseus"
    left_safety_interval_ms = 75000
    right_safety_interval_ms = 75000
    sound_path = Path("HandyBand_Audio/Odysseus/drum.wav")
    finger_sound_paths = {
        gesture: Path(f"HandyBand_Audio/Odysseus/od_oboe_{gesture:02d}.wav")
        for gesture in range(1, 8)
    }

    def __init__(self, sound_path: Path = sound_path) -> None:
        self.recognizer = DrumGestureRecognizer()
        self.audio = DrumAudioPlayer(sound_path)
        self.finger_recognizer = FingerGestureRecognizer(
            left_safety_interval_ms=self.left_safety_interval_ms,
            right_safety_interval_ms=self.right_safety_interval_ms,
        )
        self.finger_audio = FingerAudioPlayer(self.finger_sound_paths)

    def close(self) -> None:
        self.audio.close()


class Piano:
    """Numbered finger gestures mapped directly to six piano sounds."""

    name = "Piano"
    left_safety_interval_ms = 1640
    right_safety_interval_ms = 820
    finger_sound_paths = {
        gesture: Path(f"HandyBand_Audio/Piano/pi_{gesture}.wav")
        for gesture in range(1, 7)
    }
    left_finger_sound_paths = {
        gesture: Path(f"HandyBand_Audio/Piano/lef_{gesture}.wav")
        for gesture in range(1, 7)
    }

    def __init__(self) -> None:
        self.recognizer = None
        self.audio = None
        self.finger_recognizer = FingerGestureRecognizer(
            left_safety_interval_ms=self.left_safety_interval_ms,
            right_safety_interval_ms=self.right_safety_interval_ms,
        )
        self.finger_audio = FingerAudioPlayer(
            self.finger_sound_paths,
            left_sound_paths=self.left_finger_sound_paths,
        )

    def close(self) -> None:
        self.finger_audio.close()
