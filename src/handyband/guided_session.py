"""Deterministic guided-performance state machine, independent of camera/audio."""

from handyband.guided_score import Cue, Score


class GuidedSession:
    hold_ms = 150
    late_ms = 200
    loss_ms = 350
    release_ms = 100

    def __init__(self, score: Score) -> None:
        self.score = score
        self.hand = "Right"
        self.mode = "Tutorial"
        self.phrase = score.phrases[0]
        self.reset()

    def reset(self) -> None:
        if self.mode == "Tutorial":
            seen: set[int] = set()
            self.indices = []
            for i, cue in enumerate(self.score.cues):
                if cue.gesture not in seen:
                    self.indices.append(i)
                    seen.add(cue.gesture)
        else:
            self.indices = [i for i, cue in enumerate(self.score.cues)
                            if self.mode == "Perform" or cue.phrase == self.phrase]
        self.cursor = 0
        self.position_ms = self.cue.start_ms
        self.state = "Ready"
        self.feedback = "SPACE to begin"
        self.hits: set[int] = set()
        self.misses: set[int] = set()
        self.cut_short: set[int] = set()
        self.active: int | None = None
        self.candidate: int | None = None
        self.stable: int | None = None
        self._candidate_ms = 0.0
        self._missing_ms = 0.0
        self._wrong_ms = 0.0
        self._release_elapsed = 0.0
        self._last_gesture: int | None = None
        self._released = True
        self._last_ms: int | None = None
        self.countdown_ms = 0.0
        self._resume_state = "Playing"
        self._auto_pause = False

    @property
    def cue(self) -> Cue:
        return self.score.cues[self.indices[min(self.cursor, len(self.indices) - 1)]]

    @property
    def index(self) -> int:
        return self.indices[min(self.cursor, len(self.indices) - 1)]

    @property
    def sounding(self) -> bool:
        return self.state == "Playing"

    def start(self) -> None:
        self.state = "Countdown"
        self.countdown_ms = 4 * 60_000 / self.score.bpm
        self._resume_state = "Playing"
        self._auto_pause = False
        self.feedback = "Get ready"

    def toggle_pause(self) -> None:
        if self.state in ("Ready", "Finished"):
            self.reset()
            self.start()
        elif self.state == "Paused":
            self.state = "Countdown"
            self.countdown_ms = 4 * 60_000 / self.score.bpm
            self._auto_pause = False
        else:
            self._resume_state = "Waiting" if self.state == "Waiting" else "Playing"
            self.state = "Paused"
            self._auto_pause = False
            self.feedback = "Paused - SPACE to resume"

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.reset()

    def step_phrase(self, step: int) -> None:
        phrases = self.score.phrases
        self.phrase = phrases[(phrases.index(self.phrase) + step) % len(phrases)]
        self.mode = "Practice"
        self.reset()

    def update(self, timestamp_ms: int, gesture: int | None, tracked: bool) -> None:
        dt = 0 if self._last_ms is None else max(0, timestamp_ms - self._last_ms)
        self._last_ms = timestamp_ms
        # An unobserved interval must not count as a stable hand shape.
        if dt > 250:
            self.candidate = self.stable = None
            self._candidate_ms = 0
        raw = gesture if tracked else None
        if raw != self.candidate:
            self.candidate, self._candidate_ms, self.stable = raw, 0, None
        else:
            self._candidate_ms += dt
            self.stable = raw if self._candidate_ms >= self.hold_ms else None
        if tracked and raw != self._last_gesture:
            self._release_elapsed += dt
            if self._release_elapsed >= self.release_ms:
                self._released = True
        else:
            self._release_elapsed = 0
        self._missing_ms = 0 if tracked else self._missing_ms + dt
        if self.state in ("Ready", "Finished"):
            return
        if self._missing_ms >= self.loss_ms and self.state != "Paused":
            self._resume_state = "Waiting" if self.state == "Waiting" else "Playing"
            self.state, self._auto_pause = "Paused", True
            self.feedback = f"Show your {self.hand.lower()} hand to resume"
        if self.state == "Paused":
            if self._auto_pause and tracked and self._candidate_ms >= self.hold_ms:
                self.state = "Countdown"
                self.countdown_ms = 4 * 60_000 / self.score.bpm
                self._auto_pause = False
            return
        if self.state == "Countdown":
            self.countdown_ms -= dt
            if self.countdown_ms > 0:
                return
            self.state = self._resume_state
            dt = 0
        if self.state == "Playing":
            # Freeze at the next cue in practice: waiting never advances the backing.
            next_position = self.position_ms + dt
            if self.mode != "Perform" and self.index not in self.hits:
                next_position = min(next_position, self.cue.start_ms)
            self.position_ms = next_position
        while self.position_ms >= self.cue.start_ms + self.cue.duration_ms:
            if self.index not in self.hits:
                self.misses.add(self.index)
            self.active = None
            self.cursor += 1
            if self.cursor >= len(self.indices):
                self.position_ms = self.cue.start_ms + self.cue.duration_ms
                self.state = "Finished"
                self.feedback = {
                    "Tutorial": "Shapes learned! P to practice, SPACE to begin",
                    "Practice": "Phrase complete! N for next, E to perform",
                    "Perform": "Complete! A retries misses; SPACE plays again",
                }[self.mode]
                return
            if self.mode != "Perform":
                self.position_ms = self.cue.start_ms
                self.state = "Waiting"
                break
        cue, index = self.cue, self.index
        if index in self.hits:
            self.feedback = "HOLD - then prepare the next shape"
            if self.active is not None and self.position_ms < cue.start_ms + cue.duration_ms - 300:
                self._wrong_ms = self._wrong_ms + dt if tracked and raw != cue.gesture else 0
                if self._wrong_ms >= 300:
                    self.active = None
                    self.cut_short.add(index)
                    self.feedback = "Released early - continue with the next cue"
            return
        can_repeat = self._last_gesture != cue.gesture or self._released
        correct = self.stable == cue.gesture and can_repeat
        if self.position_ms < cue.start_ms:
            self.feedback = "Ready for the beat" if correct else "Prepare the next shape"
            return
        if self.mode != "Perform":
            self.state = "Waiting"
        if correct and (self.mode != "Perform"
                        or self.position_ms <= cue.start_ms + self.late_ms):
            self.hits.add(index)
            self.active = index
            self._last_gesture, self._released = cue.gesture, False
            self._wrong_ms = 0
            self.state, self.feedback = "Playing", "Matched - HOLD"
        elif self.mode == "Perform" and self.position_ms > cue.start_ms + self.late_ms:
            self.misses.add(index)
            self.feedback = "Missed - prepare the next cue"
        else:
            self.feedback = "Relax, then repeat" if not can_repeat else "Match the hand picture"
