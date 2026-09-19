"""Low-latency playback for velocity-sensitive drum events."""

from pathlib import Path
from typing import Any

from handyband.models import DrumEvent


class DrumAudioPlayer:
    """Play one centered drum sample and combine near-simultaneous hand hits."""

    def __init__(
        self,
        sound_path: Path,
        *,
        simultaneous_window_ms: int = 80,
        pygame_module: Any | None = None,
    ) -> None:
        if pygame_module is None:
            import pygame as pygame_module

        self._pygame = pygame_module
        self._pygame.mixer.init(frequency=48_000, size=-16, channels=2, buffer=256)
        self._pygame.mixer.set_num_channels(16)
        self._sound = self._pygame.mixer.Sound(str(sound_path))
        self._simultaneous_window_ms = simultaneous_window_ms
        self._pending_event: DrumEvent | None = None

    def process(self, events: tuple[DrumEvent, ...], timestamp_ms: int) -> None:
        """Buffer one hand briefly and combine an opposite-hand hit within 80 ms."""

        remaining_events = list(events)
        if self._pending_event is not None:
            partner_index = next(
                (
                    index
                    for index, event in enumerate(remaining_events)
                    if event.handedness != self._pending_event.handedness
                    and event.timestamp_ms - self._pending_event.timestamp_ms
                    <= self._simultaneous_window_ms
                ),
                None,
            )
            if partner_index is not None:
                partner = remaining_events.pop(partner_index)
                self._play((self._pending_event, partner))
                self._pending_event = None
            elif timestamp_ms - self._pending_event.timestamp_ms >= self._simultaneous_window_ms:
                self._play((self._pending_event,))
                self._pending_event = None

        for event in remaining_events:
            if self._pending_event is None:
                self._pending_event = event
            elif event.handedness != self._pending_event.handedness:
                self._play((self._pending_event, event))
                self._pending_event = None
            else:
                self._play((self._pending_event,))
                self._pending_event = event

    def _play(self, events: tuple[DrumEvent, ...]) -> None:
        volume = min(1.0, sum(event.volume for event in events))
        channel = self._pygame.mixer.find_channel(force=True)
        channel.play(self._sound)
        channel.set_volume(volume)

    def close(self) -> None:
        """Release the audio mixer."""

        self._pygame.mixer.quit()
