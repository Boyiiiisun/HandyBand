from pathlib import Path

from handyband.finger_audio import FingerAudioPlayer
from handyband.models import FingerGestureEvent


class _FakeChannel:
    def __init__(self) -> None:
        self.sound = None
        self.volume = None

    def play(self, sound) -> None:
        self.sound = sound

    def set_volume(self, volume: float) -> None:
        self.volume = volume


class _FakeMixer:
    def __init__(self) -> None:
        self.loaded_paths = []
        self.channels = []
        self.initialized = None

    def get_init(self):
        return self.initialized

    def init(self, **kwargs) -> None:
        self.initialized = True

    def set_num_channels(self, count: int) -> None:
        assert count == 16

    def quit(self) -> None:
        self.initialized = None

    def Sound(self, path: str):
        self.loaded_paths.append(path)
        return path

    def find_channel(self, force: bool):
        assert force is True
        channel = _FakeChannel()
        self.channels.append(channel)
        return channel


class _FakePygame:
    def __init__(self) -> None:
        self.mixer = _FakeMixer()


def _event(handedness: str, gesture: int, timestamp_ms: int) -> FingerGestureEvent:
    return FingerGestureEvent(handedness, gesture, timestamp_ms)


def test_loads_only_four_mapped_odysseus_sounds() -> None:
    pygame = _FakePygame()
    paths = {number: Path(f"od_oboe_{number:02d}.wav") for number in range(1, 5)}

    FingerAudioPlayer(paths, pygame_module=pygame)

    assert pygame.mixer.loaded_paths == [
        "od_oboe_01.wav",
        "od_oboe_02.wav",
        "od_oboe_03.wav",
        "od_oboe_04.wav",
    ]


def test_loads_six_mapped_piano_sounds() -> None:
    pygame = _FakePygame()
    paths = {number: Path(f"pi_{number}.wav") for number in range(1, 7)}

    FingerAudioPlayer(paths, pygame_module=pygame)

    assert pygame.mixer.loaded_paths == [f"pi_{number}.wav" for number in range(1, 7)]
    assert pygame.mixer.initialized


def test_each_mapped_event_plays_on_an_independent_channel() -> None:
    pygame = _FakePygame()
    player = FingerAudioPlayer(
        {1: Path("one.wav"), 2: Path("two.wav")},
        pygame_module=pygame,
    )

    player.process((_event("Left", 1, 100), _event("Right", 2, 120)))

    assert [channel.sound for channel in pygame.mixer.channels] == ["one.wav", "two.wav"]
    assert [channel.volume for channel in pygame.mixer.channels] == [1.0, 1.0]


def test_unmapped_gestures_are_recognized_but_silent() -> None:
    pygame = _FakePygame()
    player = FingerAudioPlayer({1: Path("one.wav")}, pygame_module=pygame)

    player.process((_event("Left", 5, 100), _event("Right", 6, 100)))

    assert pygame.mixer.channels == []
