"""Infer individual finger extension from hand landmark geometry."""

from math import acos, degrees, dist

from handyband.models import FingerState, HandLandmark, Landmark

FINGER_JOINTS = {
    "Thumb": (
        HandLandmark.THUMB_CMC,
        HandLandmark.THUMB_MCP,
        HandLandmark.THUMB_IP,
        HandLandmark.THUMB_TIP,
    ),
    "Index": (
        HandLandmark.INDEX_MCP,
        HandLandmark.INDEX_PIP,
        HandLandmark.INDEX_DIP,
        HandLandmark.INDEX_TIP,
    ),
    "Middle": (
        HandLandmark.MIDDLE_MCP,
        HandLandmark.MIDDLE_PIP,
        HandLandmark.MIDDLE_DIP,
        HandLandmark.MIDDLE_TIP,
    ),
    "Ring": (
        HandLandmark.RING_MCP,
        HandLandmark.RING_PIP,
        HandLandmark.RING_DIP,
        HandLandmark.RING_TIP,
    ),
    "Pinky": (
        HandLandmark.PINKY_MCP,
        HandLandmark.PINKY_PIP,
        HandLandmark.PINKY_DIP,
        HandLandmark.PINKY_TIP,
    ),
}


def _coordinates(point: Landmark) -> tuple[float, float, float]:
    return point.x, point.y, point.z


def _joint_angle(first: Landmark, joint: Landmark, last: Landmark) -> float:
    """Return the smaller angle at ``joint`` in degrees."""

    vector_a = tuple(a - b for a, b in zip(_coordinates(first), _coordinates(joint), strict=True))
    vector_b = tuple(a - b for a, b in zip(_coordinates(last), _coordinates(joint), strict=True))
    magnitude_a = sum(component * component for component in vector_a) ** 0.5
    magnitude_b = sum(component * component for component in vector_b) ** 0.5
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0
    cosine = sum(a * b for a, b in zip(vector_a, vector_b, strict=True)) / (
        magnitude_a * magnitude_b
    )
    return degrees(acos(max(-1.0, min(1.0, cosine))))


def classify_fingers(
    landmarks: tuple[Landmark, ...],
    *,
    straight_angle_degrees: float = 155.0,
) -> tuple[FingerState, ...]:
    """Classify all five fingers with an orientation-independent heuristic."""

    if len(landmarks) != 21:
        raise ValueError(f"Expected 21 hand landmarks, received {len(landmarks)}")

    wrist = landmarks[HandLandmark.WRIST]
    states = []
    for name, (
        base_index,
        first_joint_index,
        second_joint_index,
        tip_index,
    ) in FINGER_JOINTS.items():
        base = landmarks[base_index]
        first_joint = landmarks[first_joint_index]
        second_joint = landmarks[second_joint_index]
        tip = landmarks[tip_index]
        first_angle = _joint_angle(base, first_joint, second_joint)
        second_angle = _joint_angle(first_joint, second_joint, tip)
        points_away_from_wrist = dist(_coordinates(wrist), _coordinates(tip)) > dist(
            _coordinates(wrist), _coordinates(first_joint)
        )
        states.append(
            FingerState(
                name=name,
                extended=(
                    first_angle >= straight_angle_degrees
                    and second_angle >= straight_angle_degrees
                    and points_away_from_wrist
                ),
                tip=tip,
            )
        )
    return tuple(states)
