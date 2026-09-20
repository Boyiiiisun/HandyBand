"""Exercise the real menu/style/audio wiring, replacing only camera and window I/O."""

import cv2
import numpy as np

from handyband import app, hand_tracking, pose_tracking


def test_switch_through_all_three_styles_without_leaving_stale_audio(monkeypatch, tmp_path):
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    callbacks = []
    images = []

    class Camera:
        frame = 0
        released = False

        def isOpened(self):
            return True

        def read(self):
            self.frame += 1
            if self.frame == 2:
                callbacks[0](cv2.EVENT_LBUTTONDOWN, 590, 25, 0, None)
                callbacks[0](cv2.EVENT_LBUTTONDOWN, 590, 140, 0, None)
            if self.frame == 4:
                callbacks[0](cv2.EVENT_LBUTTONDOWN, 900, 25, 0, None)
                callbacks[0](cv2.EVENT_LBUTTONDOWN, 900, 100, 0, None)
            return True, np.zeros((480, 640, 3), dtype=np.uint8)

        def release(self):
            self.released = True

    class Tracker:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def detect(self, *args):
            return ()

    camera = Camera()
    keys = iter((-1, ord("p"), 32, ord("q")))
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: camera)
    monkeypatch.setattr(cv2, "namedWindow", lambda *args: None)
    monkeypatch.setattr(cv2, "setMouseCallback", lambda _, cb: callbacks.append(cb))
    monkeypatch.setattr(cv2, "imshow", lambda _, frame: images.append(frame.shape))
    monkeypatch.setattr(cv2, "waitKey", lambda _: next(keys))
    monkeypatch.setattr(cv2, "getWindowProperty", lambda *args: 1)
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)
    monkeypatch.setattr(hand_tracking, "HandTracker", Tracker)
    monkeypatch.setattr(pose_tracking, "PoseTracker", Tracker)
    model = tmp_path / "fake.task"
    model.touch()
    assert app.run(0, model, True, 0.5, pose_model_path=model,
                   score_path=tmp_path / "missing-score.json") == 0
    assert camera.released
    assert images == [(480, 640, 3), (640, 960, 3), (640, 960, 3), (480, 640, 3)]
