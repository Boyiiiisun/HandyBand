from math import sqrt

import pytest

from handyband.drum_gesture import DrumGestureRecognizer
from handyband.models import (
    FingerState,
    ForearmObservation,
    HandObservation,
    Landmark,
)


def _hand(handedness: str, *, open_hand: bool) -> HandObservation:
    landmarks = tuple(Landmark(0.5, 0.5, 0.0) for _ in range(21))
    fingers = tuple(
        FingerState(name=name, extended=open_hand, tip=landmarks[index])
        for name, index in zip(
            ("Thumb", "Index", "Middle", "Ring", "Pinky"),
            (4, 8, 12, 16, 20),
            strict=True,
        )
    )
    return HandObservation(handedness, 0.99, landmarks, fingers)


def _forearm(
    handedness: str,
    wrist_y: float,
    *,
    elbow_y: float = 0.30,
) -> ForearmObservation:
    vertical = wrist_y - elbow_y
    horizontal = sqrt(max(0.20**2 - vertical**2, 0.0))
    elbow = Landmark(0.5, elbow_y, 0.0)
    wrist = Landmark(elbow.x + horizontal, wrist_y, 0.0)
    midpoint = Landmark((elbow.x + wrist.x) / 2, (elbow.y + wrist.y) / 2, 0.0)
    return ForearmObservation(handedness, elbow, midpoint, wrist, 0.99)


def _left_status(
    recognizer: DrumGestureRecognizer,
    wrist_y: float,
    timestamp_ms: int,
    *,
    hand: HandObservation | None = None,
):
    hands = () if hand is None else (hand,)
    return recognizer.update(hands, (_forearm("Left", wrist_y),), timestamp_ms)[0]


def test_open_hand_starts_slow_pose_wrist_downstroke() -> None:
    recognizer = DrumGestureRecognizer(speed_smoothing=1.0)

    _left_status(recognizer, 0.38, 0, hand=_hand("Left", open_hand=True))
    for timestamp_ms, wrist_y in (
        (50, 0.39),
        (100, 0.40),
        (150, 0.41),
        (200, 0.42),
        (250, 0.43),
    ):
        assert _left_status(recognizer, wrist_y, timestamp_ms).recent_event is None
    result = _left_status(recognizer, 0.43, 300)

    assert result.recent_event is not None
    assert result.recent_event.name == "DRUM_HIT"
    assert result.recent_event.speed == pytest.approx(1.0)
    assert result.recent_event.volume == pytest.approx(0.0502222222)


def test_hand_tracking_may_disappear_after_open_hand_arms_stroke() -> None:
    recognizer = DrumGestureRecognizer(speed_smoothing=1.0)

    _left_status(recognizer, 0.38, 0, hand=_hand("Left", open_hand=True))
    for timestamp_ms, wrist_y in (
        (50, 0.39),
        (100, 0.40),
        (150, 0.41),
        (200, 0.42),
        (250, 0.43),
    ):
        _left_status(recognizer, wrist_y, timestamp_ms)
    result = _left_status(recognizer, 0.43, 300)

    assert result.recent_event is not None
    assert result.recent_event.name == "DRUM_HIT"
    assert result.open_hand is False


def test_higher_speed_downstroke_has_more_volume() -> None:
    recognizer = DrumGestureRecognizer(speed_smoothing=1.0)

    _left_status(recognizer, 0.38, 0, hand=_hand("Left", open_hand=True))
    _left_status(recognizer, 0.41, 50)
    _left_status(recognizer, 0.44, 100)
    result = _left_status(recognizer, 0.44, 150)

    assert result.recent_event is not None
    assert result.recent_event.name == "DRUM_HIT"
    assert result.recent_event.speed == pytest.approx(3.0)
    assert result.recent_event.volume == pytest.approx(0.068)


def test_maximum_reference_speed_reaches_single_hand_volume_cap() -> None:
    recognizer = DrumGestureRecognizer(speed_smoothing=1.0)

    _left_status(recognizer, 0.30, 0, hand=_hand("Left", open_hand=True))
    _left_status(recognizer, 0.42, 50)
    result = _left_status(recognizer, 0.42, 100)

    assert result.recent_event is not None
    assert result.recent_event.speed == pytest.approx(12.0)
    assert result.recent_event.volume == pytest.approx(0.5)


def test_folded_hand_does_not_arm_downstroke() -> None:
    recognizer = DrumGestureRecognizer(speed_smoothing=1.0)

    _left_status(recognizer, 0.38, 0, hand=_hand("Left", open_hand=False))
    _left_status(recognizer, 0.41, 50)
    _left_status(recognizer, 0.44, 100)
    result = _left_status(recognizer, 0.44, 150)

    assert result.recent_event is None
    assert result.phase == "SHOW OPEN HAND"


def test_rejects_fast_motion_below_minimum_distance() -> None:
    recognizer = DrumGestureRecognizer(speed_smoothing=1.0)

    _left_status(recognizer, 0.38, 0, hand=_hand("Left", open_hand=True))
    _left_status(recognizer, 0.41, 50)
    result = _left_status(recognizer, 0.41, 100)

    assert result.recent_event is None


def test_each_hand_has_independent_500_ms_cooldown() -> None:
    recognizer = DrumGestureRecognizer(speed_smoothing=1.0, event_display_ms=0)

    _left_status(recognizer, 0.38, 0, hand=_hand("Left", open_hand=True))
    for timestamp_ms, wrist_y in (
        (50, 0.39),
        (100, 0.40),
        (150, 0.41),
        (200, 0.42),
        (250, 0.43),
    ):
        _left_status(recognizer, wrist_y, timestamp_ms)
    first = _left_status(recognizer, 0.43, 300)

    _left_status(recognizer, 0.38, 350, hand=_hand("Left", open_hand=True))
    for timestamp_ms, wrist_y in (
        (400, 0.39),
        (450, 0.40),
        (500, 0.41),
        (550, 0.42),
        (600, 0.43),
    ):
        _left_status(recognizer, wrist_y, timestamp_ms)
    blocked = _left_status(recognizer, 0.43, 650)

    _left_status(recognizer, 0.38, 700, hand=_hand("Left", open_hand=True))
    _left_status(recognizer, 0.38, 750)
    for timestamp_ms, wrist_y in (
        (800, 0.39),
        (850, 0.40),
        (900, 0.41),
        (950, 0.42),
        (1000, 0.43),
    ):
        _left_status(recognizer, wrist_y, timestamp_ms)
    second = _left_status(recognizer, 0.43, 1050)

    assert first.recent_event is not None
    assert blocked.recent_event is None
    assert second.recent_event is not None
    assert second.recent_event.timestamp_ms - first.recent_event.timestamp_ms >= 500


def test_elbow_translation_is_removed_from_downward_speed() -> None:
    recognizer = DrumGestureRecognizer(speed_smoothing=1.0)
    recognizer.update(
        (_hand("Left", open_hand=True),),
        (_forearm("Left", 0.38, elbow_y=0.30),),
        0,
    )

    status = recognizer.update((), (_forearm("Left", 0.42, elbow_y=0.34),), 50)[0]

    assert status.phase == "ARMED"
    assert status.speed == pytest.approx(0.0)


def test_hands_have_independent_events_and_volumes() -> None:
    recognizer = DrumGestureRecognizer(speed_smoothing=1.0)
    open_hands = (_hand("Left", open_hand=True), _hand("Right", open_hand=True))
    recognizer.update(
        open_hands,
        (_forearm("Left", 0.38), _forearm("Right", 0.38)),
        0,
    )
    recognizer.update((), (_forearm("Left", 0.41), _forearm("Right", 0.39)), 50)
    recognizer.update((), (_forearm("Left", 0.44), _forearm("Right", 0.40)), 100)
    recognizer.update((), (_forearm("Left", 0.44), _forearm("Right", 0.41)), 150)
    recognizer.update((), (_forearm("Left", 0.44), _forearm("Right", 0.42)), 200)
    recognizer.update((), (_forearm("Left", 0.44), _forearm("Right", 0.43)), 250)
    left, right = recognizer.update(
        (),
        (_forearm("Left", 0.44), _forearm("Right", 0.43)),
        300,
    )

    assert left.recent_event is not None
    assert left.recent_event.name == "DRUM_HIT"
    assert left.recent_event.volume == pytest.approx(0.068)
    assert right.recent_event is not None
    assert right.recent_event.name == "DRUM_HIT"
    assert right.recent_event.volume == pytest.approx(0.0502222222)


def test_missing_forearm_cancels_tracking() -> None:
    recognizer = DrumGestureRecognizer(speed_smoothing=1.0)

    status = recognizer.update((_hand("Left", open_hand=True),), (), 0)[0]

    assert status.phase == "TRACKING LOST"
    assert status.recent_event is None
