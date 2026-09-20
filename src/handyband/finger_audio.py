"""Overlapping playback for numbered finger-gesture events."""

from pathlib import Path
from typing import Any

from handyband.models import FingerGestureEvent


class FingerAudioPlayer:
    """Play mapped gestures with per-hand crossfades between different shapes."""

    def __init__(
        self,
        sound_paths: dict[int, Path],
        *,
        left_sound_paths: dict[int, Path] | None = None,
        fadeout_ms: int = 150,
        pygame_module: Any | None = None,
    ) -> None:
        if pygame_module is None:
            import pygame as pygame_module

        self._pygame = pygame_module
        if hasattr(self._pygame.mixer, "get_init") and self._pygame.mixer.get_init() is None:
            self._pygame.mixer.init(frequency=48_000, size=-16, channels=2, buffer=256)
            self._pygame.mixer.set_num_channels(16)
        self._sounds = {
            gesture: self._pygame.mixer.Sound(str(path))
            for gesture, path in sound_paths.items()
        }
        self._left_sounds = (
            {
                gesture: self._pygame.mixer.Sound(str(path))
                for gesture, path in left_sound_paths.items()
            }
            if left_sound_paths is not None
            else self._sounds
        )
        self._known_sounds = tuple(self._sounds.values()) + tuple(self._left_sounds.values())
        self._fadeout_ms = fadeout_ms
        self._last_gesture_by_hand: dict[str, int] = {}
        self._channels_by_hand: dict[str, list[Any]] = {}

    def process(self, events: tuple[FingerGestureEvent, ...]) -> None:
        """Play mapped events independently and ignore gestures without audio."""

        for event in events:
            previous_gesture = self._last_gesture_by_hand.get(event.handedness)
            if previous_gesture is not None and previous_gesture != event.gesture:
                for channel in self._channels_by_hand.get(event.handedness, []):
                    if channel.get_sound() in self._known_sounds:
                        channel.fadeout(self._fadeout_ms)
                self._channels_by_hand[event.handedness] = []
            self._last_gesture_by_hand[event.handedness] = event.gesture

            sounds = self._left_sounds if event.handedness == "Left" else self._sounds
            sound = sounds.get(event.gesture)
            if sound is None:
                continue
            channel = self._pygame.mixer.find_channel(force=True)
            self._forget_channel(channel)
            channel.play(sound)
            channel.set_volume(1.0)
            self._channels_by_hand.setdefault(event.handedness, []).append(channel)

    def _forget_channel(self, channel: Any) -> None:
        for channels in self._channels_by_hand.values():
            channels[:] = [existing for existing in channels if existing is not channel]

    def close(self) -> None:
        """Release the audio mixer."""

        self._pygame.mixer.quit()
