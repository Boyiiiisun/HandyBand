"""OpenCV rendering for hand and forearm observations."""

import cv2
import numpy as np

from handyband.models import (
    DrumGestureStatus,
    ForearmObservation,
    HandLandmark,
    HandObservation,
    Landmark,
)

HAND_CONNECTIONS = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (13, 17),
    (17, 18),
    (18, 19),
    (19, 20),
    (0, 17),
)

TIP_INDICES = {
    HandLandmark.THUMB_TIP,
    HandLandmark.INDEX_TIP,
    HandLandmark.MIDDLE_TIP,
    HandLandmark.RING_TIP,
    HandLandmark.PINKY_TIP,
}


def _pixel(point: Landmark, width: int, height: int) -> tuple[int, int]:
    x = max(0, min(width - 1, round(point.x * width)))
    y = max(0, min(height - 1, round(point.y * height)))
    return x, y


def draw_observations(
    frame: np.ndarray,
    hands: tuple[HandObservation, ...],
    forearms: tuple[ForearmObservation, ...],
    fps: float,
    drum_statuses: tuple[DrumGestureStatus, ...] = (),
) -> None:
    """Draw hand and forearm observations onto ``frame`` in place."""

    height, width = frame.shape[:2]
    for forearm in forearms:
        elbow = _pixel(forearm.elbow, width, height)
        midpoint = _pixel(forearm.midpoint, width, height)
        wrist = _pixel(forearm.wrist, width, height)
        color = (80, 220, 80) if forearm.handedness == "Right" else (255, 180, 60)
        cv2.line(frame, elbow, wrist, color, 5, cv2.LINE_AA)
        cv2.circle(frame, elbow, 10, color, -1, cv2.LINE_AA)
        cv2.circle(frame, midpoint, 8, (255, 255, 0), -1, cv2.LINE_AA)
        cv2.putText(
            frame,
            f"{forearm.handedness} elbow",
            (elbow[0] + 12, elbow[1]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            f"{forearm.handedness} mid",
            (midpoint[0] + 12, midpoint[1]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 0),
            2,
            cv2.LINE_AA,
        )

    for hand_index, hand in enumerate(hands):
        points = [_pixel(point, width, height) for point in hand.landmarks]
        color = (80, 220, 80) if hand.handedness == "Right" else (255, 180, 60)

        for start, end in HAND_CONNECTIONS:
            cv2.line(frame, points[start], points[end], color, 2, cv2.LINE_AA)
        for index, point in enumerate(points):
            radius = 7 if index in TIP_INDICES else 4
            cv2.circle(frame, point, radius, color, -1, cv2.LINE_AA)

        panel_x = 12 + hand_index * max(260, width // 2)
        panel_y = 58
        cv2.putText(
            frame,
            f"{hand.handedness} ({hand.confidence:.2f})",
            (panel_x, panel_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
            cv2.LINE_AA,
        )
        for row, finger in enumerate(hand.fingers, start=1):
            state = "EXTENDED" if finger.extended else "FOLDED"
            cv2.putText(
                frame,
                f"{finger.name}: {state}",
                (panel_x, panel_y + row * 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                color,
                1,
                cv2.LINE_AA,
            )

    cv2.putText(
        frame,
        f"FPS: {fps:.1f} | Q / Esc: quit",
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    for index, status in enumerate(drum_statuses):
        panel_x = 12 + index * max(300, width // 2)
        panel_y = max(28, height - 54)
        event = status.recent_event
        phase = event.name if event is not None else status.phase
        color = (0, 220, 255) if event is not None else (255, 255, 255)
        cv2.putText(
            frame,
            f"{status.handedness}: {phase} | open: {'YES' if status.open_hand else 'NO'}",
            (panel_x, panel_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )
        detail = f"speed: {status.speed:.2f} arm/s"
        if event is not None:
            detail = f"speed: {event.speed:.2f} arm/s | volume: {event.volume:.2f}"
        cv2.putText(
            frame,
            detail,
            (panel_x, panel_y + 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
            cv2.LINE_AA,
        )
