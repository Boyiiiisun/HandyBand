from pathlib import Path

from handyband.app import (
    DEFAULT_DRUM_SOUND_PATH,
    DEFAULT_MODEL_PATH,
    DEFAULT_POSE_MODEL_PATH,
    _window_is_closed,
    build_parser,
    run,
)


def test_cli_defaults() -> None:
    args = build_parser().parse_args([])

    assert args.camera == 0
    assert args.model == DEFAULT_MODEL_PATH
    assert args.pose_model == DEFAULT_POSE_MODEL_PATH
    assert args.no_mirror is False
    assert args.confidence == 0.5


def test_odysseus_default_sound_is_grouped_with_its_style() -> None:
    assert Path("HandyBand_Audio/Odysseus/drum.wav") == DEFAULT_DRUM_SOUND_PATH
    assert DEFAULT_DRUM_SOUND_PATH.is_file()


def test_missing_model_fails_before_opening_camera(tmp_path: Path, capsys) -> None:
    missing_model = tmp_path / "missing.task"

    exit_code = run(camera_index=0, model_path=missing_model, mirror=True, confidence=0.5)

    assert exit_code == 2
    assert "Model file not found" in capsys.readouterr().err


def test_missing_pose_model_fails_before_opening_camera(tmp_path: Path, capsys) -> None:
    hand_model = tmp_path / "hand.task"
    hand_model.touch()

    exit_code = run(
        camera_index=0,
        model_path=hand_model,
        mirror=True,
        confidence=0.5,
        pose_model_path=tmp_path / "missing-pose.task",
    )

    assert exit_code == 2
    assert "Pose model file not found" in capsys.readouterr().err


def test_missing_sound_fails_before_opening_camera(tmp_path: Path, capsys) -> None:
    hand_model = tmp_path / "hand.task"
    pose_model = tmp_path / "pose.task"
    hand_model.touch()
    pose_model.touch()

    exit_code = run(
        camera_index=0,
        model_path=hand_model,
        mirror=True,
        confidence=0.5,
        pose_model_path=pose_model,
        drum_sound_path=tmp_path / "missing-drum.wav",
    )

    assert exit_code == 2
    assert "Drum sound file not found" in capsys.readouterr().err


class _FakeCv2:
    WND_PROP_VISIBLE = 4

    def __init__(self, visibility: float | Exception) -> None:
        self.visibility = visibility

    def getWindowProperty(self, _title: str, _property: int) -> float:
        if isinstance(self.visibility, Exception):
            raise self.visibility
        return self.visibility


def test_closed_window_is_detected() -> None:
    assert _window_is_closed(_FakeCv2(0.0)) is True
    assert _window_is_closed(_FakeCv2(1.0)) is False


def test_missing_window_is_treated_as_closed() -> None:
    assert _window_is_closed(_FakeCv2(RuntimeError("window is gone"))) is True
