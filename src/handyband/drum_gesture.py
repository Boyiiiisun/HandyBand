"""Recognize open-hand arm-downstroke drum gestures."""

from dataclasses import dataclass
from math import hypot

from handyband.models import (
    DrumEvent,
    DrumGestureStatus,
    ForearmObservation,
    HandObservation,
)


@dataclass(slots=True)
class _HandState:
    previous_wrist_y: float | None = None
    previous_elbow_y: float | None = None
    previous_timestamp_ms: int | None = None
    filtered_speed: float = 0.0
    open_hand_armed: bool = False
    swinging: bool = False
    stroke_started_ms: int = 0
    stroke_distance: float = 0.0
    last_trigger_ms: int | None = None
    last_event: DrumEvent | None = None
    event_visible_until_ms: int = 0

    def reset_tracking(self) -> None:
        self.previous_wrist_y = None
        self.previous_elbow_y = None
        self.previous_timestamp_ms = None
        self.filtered_speed = 0.0
        self.open_hand_armed = False
        self.swinging = False
        self.stroke_distance = 0.0


class DrumGestureRecognizer:
    """Maintain independent left/right open-hand downstroke state machines."""

    def __init__(
        self,
        *,
        start_speed: float = 0.60,
        stop_speed: float = 0.20,
        minimum_average_speed: float = 3.00,
        maximum_volume_speed: float = 10.00,
        minimum_volume: float = 0.10,
        maximum_volume: float = 0.75,
        volume_exponent: float = 2.00,
        minimum_distance: float = 0.20,
        speed_smoothing: float = 0.45,
        cooldown_ms: int = 500,
        event_display_ms: int = 350,
    ) -> None:
        self.start_speed = start_speed
        self.stop_speed = stop_speed
        self.minimum_average_speed = minimum_average_speed
        self.maximum_volume_speed = maximum_volume_speed
        self.minimum_volume = minimum_volume
        self.maximum_volume = maximum_volume
        self.volume_exponent = volume_exponent
        self.minimum_distance = minimum_distance
        self.speed_smoothing = speed_smoothing
        self.cooldown_ms = cooldown_ms
        self.event_display_ms = event_display_ms
        self._states = {side: _HandState() for side in ("Left", "Right")}

    def update(
        self,
        hands: tuple[HandObservation, ...],
        forearms: tuple[ForearmObservation, ...],
        timestamp_ms: int,
    ) -> tuple[DrumGestureStatus, ...]:
        """Update both hands and return display-ready gesture states."""

        hands_by_side = {hand.handedness: hand for hand in hands}
        forearms_by_side = {forearm.handedness: forearm for forearm in forearms}
        return tuple(
            self._update_hand(
                handedness,
                hands_by_side.get(handedness),
                forearms_by_side.get(handedness),
                timestamp_ms,
            )
            for handedness in ("Left", "Right")
        )

    def _update_hand(
        self,
        handedness: str,
        hand: HandObservation | None,
        forearm: ForearmObservation | None,
        timestamp_ms: int,
    ) -> DrumGestureStatus:
        state = self._states[handedness]
        recent_event = (
            state.last_event if timestamp_ms <= state.event_visible_until_ms else None
        )
        open_hand = hand is not None and all(finger.extended for finger in hand.fingers)

        if forearm is None:
            state.reset_tracking()
            return self._status(
                handedness,
                state,
                open_hand,
                "TRACKING LOST",
                recent_event,
            )

        if open_hand and not state.swinging:
            state.open_hand_armed = True

        arm_length = hypot(
            forearm.wrist.x - forearm.elbow.x,
            forearm.wrist.y - forearm.elbow.y,
        )
        previous_timestamp_ms = state.previous_timestamp_ms
        if (
            state.previous_wrist_y is None
            or state.previous_elbow_y is None
            or previous_timestamp_ms is None
            or arm_length <= 1e-6
        ):
            self._remember_forearm(state, forearm, timestamp_ms)
            return self._status(
                handedness,
                state,
                open_hand,
                self._idle_phase(state, open_hand, timestamp_ms),
                recent_event,
            )

        elapsed_seconds = (timestamp_ms - previous_timestamp_ms) / 1000.0
        if elapsed_seconds <= 0.0 or elapsed_seconds > 0.20:
            state.reset_tracking()
            state.open_hand_armed = open_hand
            self._remember_forearm(state, forearm, timestamp_ms)
            return self._status(
                handedness,
                state,
                open_hand,
                self._idle_phase(state, open_hand, timestamp_ms),
                recent_event,
            )

        wrist_delta = forearm.wrist.y - state.previous_wrist_y
        elbow_delta = forearm.elbow.y - state.previous_elbow_y
        relative_downward_delta = wrist_delta - elbow_delta
        relative_speed = relative_downward_delta / arm_length / elapsed_seconds
        raw_speed = relative_speed if wrist_delta > 0.0 else min(0.0, relative_speed)
        state.filtered_speed = (
            self.speed_smoothing * raw_speed
            + (1.0 - self.speed_smoothing) * state.filtered_speed
        )
        self._remember_forearm(state, forearm, timestamp_ms)

        cooldown_active = self._cooldown_active(state, timestamp_ms)
        phase = self._idle_phase(state, open_hand, timestamp_ms)
        if (
            not state.swinging
            and state.open_hand_armed
            and not cooldown_active
            and state.filtered_speed >= self.start_speed
        ):
            state.swinging = True
            state.open_hand_armed = False
            state.stroke_started_ms = timestamp_ms
            state.stroke_distance = 0.0

        if state.swinging:
            phase = "SWINGING"
            state.stroke_distance += max(0.0, relative_downward_delta / arm_length)
            if state.filtered_speed <= self.stop_speed:
                duration_seconds = max(
                    (timestamp_ms - state.stroke_started_ms) / 1000.0,
                    1e-6,
                )
                average_speed = state.stroke_distance / duration_seconds
                if (
                    state.stroke_distance >= self.minimum_distance
                    and average_speed >= self.minimum_average_speed
                ):
                    event = DrumEvent(
                        handedness=handedness,
                        name="DRUM_HIT",
                        speed=average_speed,
                        volume=self._volume_for_speed(average_speed),
                        timestamp_ms=timestamp_ms,
                    )
                    state.last_event = event
                    state.last_trigger_ms = timestamp_ms
                    state.event_visible_until_ms = timestamp_ms + self.event_display_ms
                    recent_event = event
                    phase = event.name
                else:
                    phase = self._idle_phase(state, open_hand, timestamp_ms)
                state.swinging = False
                state.stroke_distance = 0.0

        return self._status(handedness, state, open_hand, phase, recent_event)

    def _idle_phase(
        self,
        state: _HandState,
        open_hand: bool,
        timestamp_ms: int,
    ) -> str:
        if self._cooldown_active(state, timestamp_ms):
            return "COOLDOWN"
        if open_hand:
            return "OPEN HAND"
        if state.open_hand_armed:
            return "ARMED"
        return "SHOW OPEN HAND"

    def _cooldown_active(self, state: _HandState, timestamp_ms: int) -> bool:
        return (
            state.last_trigger_ms is not None
            and timestamp_ms - state.last_trigger_ms < self.cooldown_ms
        )

    def _volume_for_speed(self, speed: float) -> float:
        speed_range = self.maximum_volume_speed - self.minimum_average_speed
        progress = (speed - self.minimum_average_speed) / speed_range
        progress = max(0.0, min(1.0, progress))
        progress **= self.volume_exponent
        return self.minimum_volume + progress * (
            self.maximum_volume - self.minimum_volume
        )

    @staticmethod
    def _remember_forearm(
        state: _HandState,
        forearm: ForearmObservation,
        timestamp_ms: int,
    ) -> None:
        state.previous_wrist_y = forearm.wrist.y
        state.previous_elbow_y = forearm.elbow.y
        state.previous_timestamp_ms = timestamp_ms

    @staticmethod
    def _status(
        handedness: str,
        state: _HandState,
        open_hand: bool,
        phase: str,
        recent_event: DrumEvent | None,
    ) -> DrumGestureStatus:
        return DrumGestureStatus(
            handedness=handedness,
            phase=phase,
            open_hand=open_hand,
            speed=max(0.0, state.filtered_speed),
            recent_event=recent_event,
        )
