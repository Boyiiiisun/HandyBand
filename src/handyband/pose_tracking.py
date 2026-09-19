"""MediaPipe Pose Landmarker integration for forearm anchors."""

from pathlib import Path

import mediapipe as mp
import numpy as np

from handyband.forearm import extract_forearms
from handyband.models import ForearmObservation, Landmark


class PoseTracker:
    """Detect elbow and forearm-midpoint anchors for one person."""

    def __init__(
        self,
        model_path: Path,
        *,
        mirrored_input: bool = False,
        detection_confidence: float = 0.5,
        presence_confidence: float = 0.5,
        tracking_confidence: float = 0.5,
    ) -> None:
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=detection_confidence,
            min_pose_presence_confidence=presence_confidence,
            min_tracking_confidence=tracking_confidence,
            output_segmentation_masks=False,
        )
        self._detector = mp.tasks.vision.PoseLandmarker.create_from_options(options)
        self._mirrored_input = mirrored_input

    def detect(self, rgb_frame: np.ndarray, timestamp_ms: int) -> tuple[ForearmObservation, ...]:
        """Return visible forearm anchors for a single video frame."""

        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = self._detector.detect_for_video(image, timestamp_ms)
        if not result.pose_landmarks:
            return ()

        landmarks = tuple(
            Landmark(
                x=point.x,
                y=point.y,
                z=point.z,
                visibility=point.visibility or 0.0,
            )
            for point in result.pose_landmarks[0]
        )
        return extract_forearms(landmarks, mirrored=self._mirrored_input)

    def close(self) -> None:
        """Release MediaPipe resources."""

        self._detector.close()

    def __enter__(self) -> "PoseTracker":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
