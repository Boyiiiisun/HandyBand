"""OpenCV rendering for hand and forearm observations."""

import cv2
import numpy as np

from handyband.models import (
    DrumGestureStatus,
    FingerGestureStatus,
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


class StyleMenu:
    """A one-style selector drawn in camera-image coordinates."""

    def __init__(self, style_name: str) -> None:
        self.style_name = style_name
        self.expanded = False
        self._left = 0
        self._right = 0

    def on_mouse(self, event: int, x: int, y: int, flags: int, param: object) -> None:
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        if self._left <= x < self._right and 10 <= y < 46:
            self.expanded = not self.expanded
        else:
            # Selecting the already-active style or clicking outside closes the list.
            self.expanded = False

    def draw(self, frame: np.ndarray) -> None:
        self._right = frame.shape[1] - 10
        self._left = max(0, self._right - 210)
        rows = [(10, f"{self.style_name} {'^' if self.expanded else 'v'}")]
        if self.expanded:
            rows.append((48, f"{self.style_name} (active)"))
        for top, label in rows:
            cv2.rectangle(frame, (self._left, top), (self._right, top + 36), (35, 35, 35), -1)
            cv2.rectangle(frame, (self._left, top), (self._right, top + 36), (180, 180, 180), 1)
            cv2.putText(
                frame, label, (self._left + 10, top + 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA,
            )


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
    finger_statuses: tuple[FingerGestureStatus, ...] = (),
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

    finger_status_by_side = {status.handedness: status for status in finger_statuses}
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

        gesture_status = finger_status_by_side.get(hand.handedness)
        if gesture_status is not None:
            candidate = gesture_status.candidate_gesture
            confirmed = gesture_status.confirmed_gesture
            gesture_label = "--" if candidate is None else str(candidate)
            cv2.putText(
                frame,
                f"Gesture: {gesture_label} | {gesture_status.phase}",
                (panel_x, panel_y + 6 * 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                color,
                1,
                cv2.LINE_AA,
            )
            event = gesture_status.recent_event
            if event is not None:
                result = "PLAYED" if event.gesture <= 4 else "NO AUDIO"
                detail = f"Last: {event.gesture} | {result}"
            elif confirmed is not None:
                detail = f"Confirmed: {confirmed}"
            else:
                detail = "Last: --"
            cv2.putText(
                frame,
                detail,
                (panel_x, panel_y + 7 * 24),
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
