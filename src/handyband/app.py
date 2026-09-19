"""Command-line entry point and camera loop for HandyBand."""

import argparse
import sys
import time
from pathlib import Path

DEFAULT_MODEL_PATH = Path("models/hand_landmarker.task")
DEFAULT_POSE_MODEL_PATH = Path("models/pose_landmarker_lite.task")
DEFAULT_DRUM_SOUND_PATH = Path("assets/audio/drum.wav")
WINDOW_TITLE = "HandyBand - Hand Tracking"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track two hands, five fingers, and forearm anchors from a camera."
    )
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index (default: 0)")
    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help=f"MediaPipe Hand Landmarker model (default: {DEFAULT_MODEL_PATH})",
    )
    parser.add_argument(
        "--pose-model",
        type=Path,
        default=DEFAULT_POSE_MODEL_PATH,
        help=f"MediaPipe Pose Landmarker model (default: {DEFAULT_POSE_MODEL_PATH})",
    )
    parser.add_argument(
        "--no-mirror",
        action="store_true",
        help="Do not mirror camera frames horizontally",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.5,
        help="Detection, presence, and tracking confidence from 0 to 1 (default: 0.5)",
    )
    return parser


def _validate_confidence(parser: argparse.ArgumentParser, confidence: float) -> None:
    if not 0.0 <= confidence <= 1.0:
        parser.error("--confidence must be between 0 and 1")


def _window_is_closed(cv2_module: object) -> bool:
    try:
        visibility = cv2_module.getWindowProperty(  # type: ignore[attr-defined]
            WINDOW_TITLE,
            cv2_module.WND_PROP_VISIBLE,  # type: ignore[attr-defined]
        )
    except Exception:
        return True
    return visibility < 1


def run(
    camera_index: int,
    model_path: Path,
    mirror: bool,
    confidence: float,
    pose_model_path: Path = DEFAULT_POSE_MODEL_PATH,
    drum_sound_path: Path = DEFAULT_DRUM_SOUND_PATH,
) -> int:
    if not model_path.is_file():
        print(
            f"Model file not found: {model_path}\n"
            "Run `python scripts/download_model.py` or pass --model PATH.",
            file=sys.stderr,
        )
        return 2
    if not pose_model_path.is_file():
        print(
            f"Pose model file not found: {pose_model_path}\n"
            "Run `python scripts/download_model.py` or pass --pose-model PATH.",
            file=sys.stderr,
        )
        return 2
    if not drum_sound_path.is_file():
        print(f"Drum sound file not found: {drum_sound_path}", file=sys.stderr)
        return 2

    import cv2

    from handyband.display import draw_observations
    from handyband.drum_audio import DrumAudioPlayer
    from handyband.drum_gesture import DrumGestureRecognizer
    from handyband.hand_tracking import HandTracker
    from handyband.pose_tracking import PoseTracker

    camera = cv2.VideoCapture(camera_index)
    if not camera.isOpened():
        print(
            f"Could not open camera index {camera_index}. "
            "Close other camera applications or try --camera 1.",
            file=sys.stderr,
        )
        camera.release()
        return 3

    started_at = time.perf_counter()
    previous_frame_at = started_at
    last_timestamp_ms = -1
    smoothed_fps = 0.0
    drum_recognizer = DrumGestureRecognizer()
    audio_player = None
    try:
        audio_player = DrumAudioPlayer(drum_sound_path)
        cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)
        with (
            HandTracker(
                model_path,
                mirrored_input=mirror,
                detection_confidence=confidence,
                presence_confidence=confidence,
                tracking_confidence=confidence,
            ) as hand_tracker,
            PoseTracker(
                pose_model_path,
                mirrored_input=mirror,
                detection_confidence=confidence,
                presence_confidence=confidence,
                tracking_confidence=confidence,
            ) as pose_tracker,
        ):
            while True:
                ok, frame = camera.read()
                if not ok:
                    print("The camera stopped returning frames.", file=sys.stderr)
                    return 4
                if mirror:
                    frame = cv2.flip(frame, 1)

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                timestamp_ms = max(
                    last_timestamp_ms + 1,
                    int((time.perf_counter() - started_at) * 1000),
                )
                last_timestamp_ms = timestamp_ms
                hands = hand_tracker.detect(rgb_frame, timestamp_ms)
                forearms = pose_tracker.detect(rgb_frame, timestamp_ms)
                drum_statuses = drum_recognizer.update(hands, forearms, timestamp_ms)
                drum_events = []
                for status in drum_statuses:
                    event = status.recent_event
                    if event is not None and status.phase == "DRUM_HIT":
                        drum_events.append(event)
                audio_player.process(tuple(drum_events), timestamp_ms)

                now = time.perf_counter()
                instantaneous_fps = 1.0 / max(now - previous_frame_at, 1e-9)
                smoothed_fps = (
                    instantaneous_fps
                    if smoothed_fps == 0.0
                    else 0.9 * smoothed_fps + 0.1 * instantaneous_fps
                )
                previous_frame_at = now

                draw_observations(frame, hands, forearms, smoothed_fps, drum_statuses)
                cv2.imshow(WINDOW_TITLE, frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), ord("Q"), 27) or _window_is_closed(cv2):
                    return 0
    finally:
        if audio_player is not None:
            audio_player.close()
        camera.release()
        cv2.destroyAllWindows()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _validate_confidence(parser, args.confidence)
    return run(
        args.camera,
        args.model,
        not args.no_mirror,
        args.confidence,
        args.pose_model,
    )
