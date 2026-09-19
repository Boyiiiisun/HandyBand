import pytest

from handyband.forearm import extract_forearms
from handyband.models import Landmark


def _pose_landmarks() -> list[Landmark]:
    return [Landmark(0.0, 0.0, 0.0, visibility=0.0) for _ in range(33)]


def test_extracts_elbow_and_midpoint_for_each_visible_forearm() -> None:
    landmarks = _pose_landmarks()
    landmarks[13] = Landmark(0.2, 0.4, -0.1, visibility=0.9)
    landmarks[15] = Landmark(0.4, 0.8, -0.3, visibility=0.8)
    landmarks[14] = Landmark(0.8, 0.4, 0.1, visibility=0.95)
    landmarks[16] = Landmark(0.6, 0.8, 0.3, visibility=0.85)

    forearms = extract_forearms(tuple(landmarks), mirrored=False)

    assert [forearm.handedness for forearm in forearms] == ["Left", "Right"]
    assert forearms[0].elbow == landmarks[13]
    assert forearms[0].midpoint.x == pytest.approx(0.3)
    assert forearms[0].midpoint.y == pytest.approx(0.6)
    assert forearms[0].midpoint.z == pytest.approx(-0.2)
    assert forearms[0].confidence == pytest.approx(0.8)


def test_mirrored_pose_uses_anatomical_handedness() -> None:
    landmarks = _pose_landmarks()
    landmarks[13] = Landmark(0.2, 0.4, 0.0, visibility=0.9)
    landmarks[15] = Landmark(0.4, 0.8, 0.0, visibility=0.9)

    forearms = extract_forearms(tuple(landmarks), mirrored=True)

    assert len(forearms) == 1
    assert forearms[0].handedness == "Right"


def test_omits_forearm_when_an_anchor_is_not_visible() -> None:
    landmarks = _pose_landmarks()
    landmarks[13] = Landmark(0.2, 0.4, 0.0, visibility=0.9)
    landmarks[15] = Landmark(0.4, 0.8, 0.0, visibility=0.2)

    assert extract_forearms(tuple(landmarks), mirrored=False) == ()


def test_requires_all_pose_landmarks() -> None:
    with pytest.raises(ValueError, match="Expected 33"):
        extract_forearms(tuple(_pose_landmarks()[:-1]), mirrored=False)
