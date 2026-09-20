"""Exercise bundled native libraries and assets without a camera or speakers."""

import os


def check_bundle() -> int:
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    import numpy as np

    from handyband.app import DEFAULT_MODEL_PATH, DEFAULT_POSE_MODEL_PATH
    from handyband.hand_tracking import HandTracker
    from handyband.interstellar import Interstellar
    from handyband.pose_tracking import PoseTracker
    from handyband.styles import Odysseus, Piano

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    with HandTracker(DEFAULT_MODEL_PATH) as hands, PoseTracker(DEFAULT_POSE_MODEL_PATH) as pose:
        hands.detect(frame, 0)
        pose.detect(frame, 0)
    for style_class in (Odysseus, Piano, Interstellar):
        style = style_class()
        style.close()
    print("HandyBand bundle self-test passed: models, inference, audio and styles.")
    return 0
