"""Render MIDI notes locally; melody only sounds after a successful cue."""

import numpy as np

from handyband.guided_score import Note, Score
from handyband.guided_session import GuidedSession

SAMPLE_RATE = 24_000


def render_notes(notes: tuple[Note, ...], duration_ms: float) -> np.ndarray:
    """Soft organ/piano hybrid, with bounded mix level and click-free envelopes."""
    result = np.zeros(round(duration_ms * SAMPLE_RATE / 1000), dtype=np.float32)
    for note in notes:
        start = round(note.start_ms * SAMPLE_RATE / 1000)
        length = min(round(note.duration_ms * SAMPLE_RATE / 1000), len(result) - start)
        if length <= 0:
            continue
        t = np.arange(length, dtype=np.float32) / SAMPLE_RATE
        frequency = 440 * 2 ** ((note.pitch - 69) / 12)
        wave = np.sin(2 * np.pi * frequency * t)
        for harmonic, level in ((2, 0.32), (3, 0.12), (4, 0.04)):
            if frequency * harmonic < SAMPLE_RATE / 2:
                wave += level * np.sin(2 * np.pi * frequency * harmonic * t)
        duration = length / SAMPLE_RATE
        envelope = np.minimum(t / 0.018, 1) * np.minimum((duration - t) / 0.14, 1)
        envelope *= 0.55 + 0.45 * np.exp(-t * 2)
        result[start:start + length] += wave * envelope * note.velocity / 127 * 0.14
    return (np.tanh(result) * 26000).astype(np.int16)


class GuidedAudio:
    def __init__(self, score: Score) -> None:
        import pygame

        self.pygame = pygame
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=256)
        self.backing_channel = pygame.mixer.Channel(0)
        self.melody_channel = pygame.mixer.Channel(1)
        self.backing = render_notes(score.accompaniment, score.duration_ms)
        self.melodies = [render_notes(cue.notes, cue.duration_ms) for cue in score.cues]
        self._playing = False
        self._active: int | None = None
        self._position = 0.0

    def _play(self, channel, samples: np.ndarray, offset_ms: float, volume: float) -> None:
        start = max(0, round(offset_ms * SAMPLE_RATE / 1000))
        if start >= len(samples):
            channel.stop()
            return
        samples = samples[start:]
        stereo = np.ascontiguousarray(np.column_stack((samples, samples)))
        channel.play(self.pygame.sndarray.make_sound(stereo), fade_ms=12)
        channel.set_volume(volume)

    def sync(self, session: GuidedSession) -> None:
        playing = session.sounding
        jump = session.position_ms < self._position or session.position_ms - self._position > 300
        restart = playing and (not self._playing or jump)
        if not playing:
            if self._playing:
                self.backing_channel.fadeout(70)
                self.melody_channel.fadeout(70)
            self._active = None
        else:
            if restart:
                self._play(self.backing_channel, self.backing, session.position_ms, 0.55)
            if session.active != self._active or restart:
                self.melody_channel.fadeout(70)
                if session.active is not None:
                    cue = session.score.cues[session.active]
                    self._play(self.melody_channel, self.melodies[session.active],
                               session.position_ms - cue.start_ms, 0.9)
            self._active = session.active
        self._playing, self._position = playing, session.position_ms

    def stop(self) -> None:
        self.backing_channel.stop()
        self.melody_channel.stop()
        self._playing, self._active = False, None

    def close(self) -> None:
        self.stop()
        self.pygame.mixer.quit()
