"""Overlapping playback for numbered finger-gesture events."""

from pathlib import Path
from typing import Any

from handyband.models import FingerGestureEvent


class FingerAudioPlayer:
    """Play every mapped gesture on its own mixer channel at original volume."""

    def __init__(
        self,
        sound_paths: dict[int, Path],
        *,
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

    def process(self, events: tuple[FingerGestureEvent, ...]) -> None:
        """Play mapped events independently and ignore gestures without audio."""

        for event in events:
            sound = self._sounds.get(event.gesture)
            if sound is None:
                continue
            channel = self._pygame.mixer.find_channel(force=True)
            channel.play(sound)
            channel.set_volume(1.0)

    def close(self) -> None:
        """Release the audio mixer."""

        self._pygame.mixer.quit()
