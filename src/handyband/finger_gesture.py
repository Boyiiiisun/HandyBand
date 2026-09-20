"""Recognize six numbered hand shapes without using arm motion."""

from dataclasses import dataclass

from handyband.models import (
    FingerGestureEvent,
    FingerGestureStatus,
    HandObservation,
)

FINGER_ORDER = ("Thumb", "Index", "Middle", "Ring", "Pinky")
GESTURE_PATTERNS = {
    (False, False, False, False, False): 0,
    (False, True, False, False, False): 1,
    (False, True, True, False, False): 2,
    (False, False, True, True, True) or (False, True, True, True, False): 3,
    (False, True, True, True, True): 4,
    (True, True, True, True, True): 5,
    (True, False, False, False, True): 6,
    (True, True, False, False, False): 7,
}


@dataclass(slots=True)
class _HandState:
    candidate_gesture: int | None = None
    candidate_since_ms: int | None = None
    confirmed_gesture: int | None = None
    last_trigger_ms: int | None = None
    last_event: FingerGestureEvent | None = None
    event_visible_until_ms: int = 0

    def reset_candidate(self) -> None:
        self.candidate_gesture = None
        self.candidate_since_ms = None
        self.confirmed_gesture = None


def classify_numbered_gesture(hand: HandObservation) -> int | None:
    """Return the exact numbered hand shape, or ``None`` when it is undefined."""

    states_by_name = {finger.name: finger.extended for finger in hand.fingers}
    if any(name not in states_by_name for name in FINGER_ORDER):
        return None
    pattern = tuple(states_by_name[name] for name in FINGER_ORDER)
    return GESTURE_PATTERNS.get(pattern)


class FingerGestureRecognizer:
    """Maintain independent stable-shape and safety timers for both hands."""

    def __init__(
        self,
        *,
        hold_ms: int = 150,
        safety_interval_ms: int = 750,
        event_display_ms: int = 350,
    ) -> None:
        self.hold_ms = hold_ms
        self.safety_interval_ms = safety_interval_ms
        self.event_display_ms = event_display_ms
        self._states = {side: _HandState() for side in ("Left", "Right")}

    def update(
        self,
        hands: tuple[HandObservation, ...],
        timestamp_ms: int,
    ) -> tuple[FingerGestureStatus, ...]:
        """Update both hands and return display-ready gesture states."""

        hands_by_side = {hand.handedness: hand for hand in hands}
        return tuple(
            self._update_hand(handedness, hands_by_side.get(handedness), timestamp_ms)
            for handedness in ("Left", "Right")
        )

    def _update_hand(
        self,
        handedness: str,
        hand: HandObservation | None,
        timestamp_ms: int,
    ) -> FingerGestureStatus:
        state = self._states[handedness]
        recent_event = (
            state.last_event if timestamp_ms <= state.event_visible_until_ms else None
        )
        if hand is None:
            state.reset_candidate()
            return self._status(handedness, state, "TRACKING LOST", recent_event)

        gesture = classify_numbered_gesture(hand)
        if gesture is None:
            state.reset_candidate()
            return self._status(handedness, state, "NO GESTURE", recent_event)

        if gesture != state.candidate_gesture:
            state.candidate_gesture = gesture
            state.candidate_since_ms = timestamp_ms
            state.confirmed_gesture = None

        candidate_since_ms = state.candidate_since_ms
        if (
            candidate_since_ms is None
            or timestamp_ms - candidate_since_ms < self.hold_ms
        ):
            return self._status(handedness, state, "HOLDING", recent_event)

        state.confirmed_gesture = gesture
        safety_elapsed = (
            state.last_trigger_ms is None
            or timestamp_ms - state.last_trigger_ms >= self.safety_interval_ms
            or (state.last_event is not None and state.last_event.gesture != gesture)
        )
        if not safety_elapsed:
            return self._status(handedness, state, "SAFETY WAIT", recent_event)

        event = FingerGestureEvent(handedness, gesture, timestamp_ms)
        state.last_trigger_ms = timestamp_ms
        state.last_event = event
        state.event_visible_until_ms = timestamp_ms + self.event_display_ms
        return self._status(handedness, state, "TRIGGERED", event)

    @staticmethod
    def _status(
        handedness: str,
        state: _HandState,
        phase: str,
        recent_event: FingerGestureEvent | None,
    ) -> FingerGestureStatus:
        return FingerGestureStatus(
            handedness=handedness,
            phase=phase,
            candidate_gesture=state.candidate_gesture,
            confirmed_gesture=state.confirmed_gesture,
            recent_event=recent_event,
        )
