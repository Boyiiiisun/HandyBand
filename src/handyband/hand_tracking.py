"""MediaPipe Hand Landmarker integration."""

from pathlib import Path

import mediapipe as mp
import numpy as np

from handyband.finger_state import classify_fingers
from handyband.models import HandObservation, Landmark, correct_handedness


class HandTracker:
    """Detect up to two hands in a sequence of RGB frames."""

    def __init__(
        self,
        model_path: Path,
        *,
        max_hands: int = 2,
        mirrored_input: bool = False,
        detection_confidence: float = 0.5,
        presence_confidence: float = 0.5,
        tracking_confidence: float = 0.5,
    ) -> None:
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=max_hands,
            min_hand_detection_confidence=detection_confidence,
            min_hand_presence_confidence=presence_confidence,
            min_tracking_confidence=tracking_confidence,
        )
        self._detector = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self._mirrored_input = mirrored_input

    def detect(self, rgb_frame: np.ndarray, timestamp_ms: int) -> tuple[HandObservation, ...]:
        """Return structured observations for a single video frame."""

        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = self._detector.detect_for_video(image, timestamp_ms)
        observations = []
        for index, detected_landmarks in enumerate(result.hand_landmarks):
            landmarks = tuple(
                Landmark(x=point.x, y=point.y, z=point.z) for point in detected_landmarks
            )
            category = result.handedness[index][0]
            observations.append(
                HandObservation(
                    handedness=correct_handedness(
                        category.category_name or "Unknown",
                        mirrored=self._mirrored_input,
                    ),
                    confidence=category.score or 0.0,
                    landmarks=landmarks,
                    fingers=classify_fingers(landmarks),
                )
            )
        return tuple(observations)

    def close(self) -> None:
        """Release MediaPipe resources."""

        self._detector.close()

    def __enter__(self) -> "HandTracker":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
