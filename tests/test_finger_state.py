from math import cos, sin

import pytest

from handyband.finger_state import classify_fingers
from handyband.models import HandLandmark, Landmark, correct_handedness


def _blank_hand() -> list[Landmark]:
    return [Landmark(0.0, 0.0, 0.0) for _ in range(21)]


def _straight_hand(angle: float = 0.0) -> tuple[Landmark, ...]:
    """Build a synthetic open hand, optionally rotated in the image plane."""

    points = _blank_hand()
    points[HandLandmark.WRIST] = Landmark(0.0, 0.0, 0.0)
    directions = (-0.9, -0.45, 0.0, 0.45, 0.9)
    joint_groups = (
        (1, 2, 3, 4),
        (5, 6, 7, 8),
        (9, 10, 11, 12),
        (13, 14, 15, 16),
        (17, 18, 19, 20),
    )
    for direction, indices in zip(directions, joint_groups, strict=True):
        base_x = direction * 0.12
        for distance_index, landmark_index in enumerate(indices, start=1):
            x = base_x + direction * distance_index * 0.025
            y = distance_index * 0.18
            rotated_x = x * cos(angle) - y * sin(angle)
            rotated_y = x * sin(angle) + y * cos(angle)
            points[landmark_index] = Landmark(rotated_x, rotated_y, 0.0)
    return tuple(points)


def test_all_straight_fingers_are_extended() -> None:
    states = classify_fingers(_straight_hand())

    assert [state.name for state in states] == ["Thumb", "Index", "Middle", "Ring", "Pinky"]
    assert all(state.extended for state in states)


def test_classification_is_rotation_independent() -> None:
    states = classify_fingers(_straight_hand(angle=1.2))

    assert all(state.extended for state in states)


def test_folded_index_is_not_extended() -> None:
    points = list(_straight_hand())
    points[HandLandmark.INDEX_DIP] = Landmark(0.25, 0.36, 0.0)
    points[HandLandmark.INDEX_TIP] = Landmark(0.25, 0.18, 0.0)

    states = {state.name: state.extended for state in classify_fingers(tuple(points))}

    assert states["Index"] is False
    assert states["Middle"] is True


def test_requires_exactly_21_landmarks() -> None:
    with pytest.raises(ValueError, match="Expected 21"):
        classify_fingers(tuple(_blank_hand()[:-1]))


@pytest.mark.parametrize(
    ("label", "mirrored", "expected"),
    [
        ("Left", True, "Right"),
        ("Right", True, "Left"),
        ("Left", False, "Left"),
        ("Right", False, "Right"),
        ("Unknown", True, "Unknown"),
    ],
)
def test_handedness_correction(label: str, mirrored: bool, expected: str) -> None:
    assert correct_handedness(label, mirrored=mirrored) == expected
