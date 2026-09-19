"""Extract forearm anchors from MediaPipe pose landmarks."""

from handyband.models import ForearmObservation, Landmark, correct_handedness

FOREARM_INDICES = {
    "Left": (13, 15),
    "Right": (14, 16),
}


def _midpoint(first: Landmark, second: Landmark, visibility: float) -> Landmark:
    return Landmark(
        x=(first.x + second.x) / 2,
        y=(first.y + second.y) / 2,
        z=(first.z + second.z) / 2,
        visibility=visibility,
    )


def extract_forearms(
    pose_landmarks: tuple[Landmark, ...],
    *,
    mirrored: bool,
    minimum_visibility: float = 0.5,
) -> tuple[ForearmObservation, ...]:
    """Return elbow and midpoint anchors for each visible forearm."""

    if len(pose_landmarks) != 33:
        raise ValueError(f"Expected 33 pose landmarks, received {len(pose_landmarks)}")

    forearms = []
    for handedness, (elbow_index, wrist_index) in FOREARM_INDICES.items():
        elbow = pose_landmarks[elbow_index]
        wrist = pose_landmarks[wrist_index]
        confidence = min(elbow.visibility, wrist.visibility)
        if confidence < minimum_visibility:
            continue
        forearms.append(
            ForearmObservation(
                handedness=correct_handedness(handedness, mirrored=mirrored),
                elbow=elbow,
                midpoint=_midpoint(elbow, wrist, confidence),
                wrist=wrist,
                confidence=confidence,
            )
        )
    return tuple(forearms)
