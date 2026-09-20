import pytest

from handyband.finger_gesture import FingerGestureRecognizer, classify_numbered_gesture
from handyband.models import FingerState, HandObservation, Landmark


def _hand(handedness: str, pattern: tuple[bool, bool, bool, bool, bool]) -> HandObservation:
    landmarks = tuple(Landmark(0.5, 0.5, 0.0) for _ in range(21))
    fingers = tuple(
        FingerState(name, extended, landmarks[index])
        for name, extended, index in zip(
            ("Thumb", "Index", "Middle", "Ring", "Pinky"),
            pattern,
            (4, 8, 12, 16, 20),
            strict=True,
        )
    )
    return HandObservation(handedness, 0.99, landmarks, fingers)


PATTERNS = {
    1: (False, True, False, False, False),
    2: (False, True, True, False, False),
    3: (False, True, True, True, False),
    4: (False, True, True, True, True),
    5: (True, True, True, True, True),
    6: (True, False, False, False, True),
}


@pytest.mark.parametrize(("gesture", "pattern"), PATTERNS.items())
def test_classifies_six_exact_patterns(gesture: int, pattern: tuple[bool, ...]) -> None:
    assert classify_numbered_gesture(_hand("Left", pattern)) == gesture


def test_undefined_pattern_is_not_classified() -> None:
    assert classify_numbered_gesture(_hand("Left", (True, False, False, False, False))) is None


def test_requires_150_ms_hold_then_repeats_after_500_ms() -> None:
    recognizer = FingerGestureRecognizer()
    hand = _hand("Left", PATTERNS[1])

    assert recognizer.update((hand,), 0)[0].phase == "HOLDING"
    assert recognizer.update((hand,), 149)[0].phase == "HOLDING"
    first = recognizer.update((hand,), 150)[0]
    assert first.phase == "TRIGGERED"
    assert first.recent_event is not None

    assert recognizer.update((hand,), 649)[0].phase == "SAFETY WAIT"
    repeated = recognizer.update((hand,), 650)[0]
    assert repeated.phase == "TRIGGERED"
    assert repeated.recent_event is not None


def test_different_gesture_triggers_as_soon_as_it_is_stable() -> None:
    recognizer = FingerGestureRecognizer()
    one = _hand("Left", PATTERNS[1])
    two = _hand("Left", PATTERNS[2])

    recognizer.update((one,), 0)
    recognizer.update((one,), 150)
    recognizer.update((two,), 200)
    result = recognizer.update((two,), 350)[0]

    assert result.phase == "TRIGGERED"
    assert result.recent_event is not None
    assert result.recent_event.gesture == 2


def test_undefined_shape_breaks_the_hold_timer() -> None:
    recognizer = FingerGestureRecognizer()
    one = _hand("Left", PATTERNS[1])
    undefined = _hand("Left", (True, False, False, False, False))

    recognizer.update((one,), 0)
    assert recognizer.update((undefined,), 100)[0].phase == "NO GESTURE"
    assert recognizer.update((one,), 120)[0].phase == "HOLDING"
    assert recognizer.update((one,), 269)[0].phase == "HOLDING"
    assert recognizer.update((one,), 270)[0].phase == "TRIGGERED"


def test_hands_have_independent_safety_intervals() -> None:
    recognizer = FingerGestureRecognizer()
    left = _hand("Left", PATTERNS[1])
    right = _hand("Right", PATTERNS[2])

    recognizer.update((left,), 0)
    recognizer.update((left,), 150)
    recognizer.update((left, right), 200)
    left_status, right_status = recognizer.update((left, right), 350)

    assert left_status.phase == "SAFETY WAIT"
    assert right_status.phase == "TRIGGERED"


@pytest.mark.parametrize("gesture", [5, 6])
def test_gestures_without_audio_still_trigger_and_start_safety_interval(gesture: int) -> None:
    recognizer = FingerGestureRecognizer()
    hand = _hand("Left", PATTERNS[gesture])

    recognizer.update((hand,), 0)
    result = recognizer.update((hand,), 150)[0]

    assert result.phase == "TRIGGERED"
    assert result.recent_event is not None
    assert result.recent_event.gesture == gesture
    assert recognizer.update((hand,), 200)[0].phase == "SAFETY WAIT"
