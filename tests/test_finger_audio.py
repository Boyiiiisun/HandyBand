from pathlib import Path

from handyband.finger_audio import FingerAudioPlayer
from handyband.models import FingerGestureEvent


class _FakeChannel:
    def __init__(self) -> None:
        self.sound = None
        self.volume = None
        self.fadeout_ms = None

    def play(self, sound) -> None:
        self.sound = sound

    def set_volume(self, volume: float) -> None:
        self.volume = volume

    def fadeout(self, milliseconds: int) -> None:
        self.fadeout_ms = milliseconds

    def get_sound(self):
        return self.sound


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


def test_loads_right_and_left_piano_sounds() -> None:
    pygame = _FakePygame()
    right_paths = {number: Path(f"pi_{number}.wav") for number in range(1, 7)}
    left_paths = {number: Path(f"lef_{number}.wav") for number in range(1, 7)}

    FingerAudioPlayer(
        right_paths,
        left_sound_paths=left_paths,
        pygame_module=pygame,
    )

    assert pygame.mixer.loaded_paths == [
        *(f"pi_{number}.wav" for number in range(1, 7)),
        *(f"lef_{number}.wav" for number in range(1, 7)),
    ]
    assert pygame.mixer.initialized


def test_left_and_right_events_use_their_own_audio() -> None:
    pygame = _FakePygame()
    player = FingerAudioPlayer(
        {1: Path("right-one.wav")},
        left_sound_paths={1: Path("left-one.wav")},
        pygame_module=pygame,
    )

    player.process((_event("Right", 1, 0), _event("Left", 1, 0)))

    assert [channel.sound for channel in pygame.mixer.channels] == [
        "right-one.wav",
        "left-one.wav",
    ]


def test_each_mapped_event_plays_on_an_independent_channel() -> None:
    pygame = _FakePygame()
    player = FingerAudioPlayer(
        {1: Path("one.wav"), 2: Path("two.wav")},
        pygame_module=pygame,
    )

    player.process((_event("Left", 1, 100), _event("Right", 2, 120)))

    assert [channel.sound for channel in pygame.mixer.channels] == ["one.wav", "two.wav"]
    assert [channel.volume for channel in pygame.mixer.channels] == [1.0, 1.0]
    assert [channel.fadeout_ms for channel in pygame.mixer.channels] == [None, None]


def test_new_gesture_fades_only_the_same_hands_audio() -> None:
    pygame = _FakePygame()
    player = FingerAudioPlayer(
        {1: Path("one.wav"), 2: Path("two.wav")},
        pygame_module=pygame,
    )

    player.process((_event("Left", 1, 0), _event("Right", 1, 0)))
    left_channel, right_channel = pygame.mixer.channels
    player.process((_event("Left", 2, 350),))

    assert left_channel.fadeout_ms == 150
    assert right_channel.fadeout_ms is None
    assert pygame.mixer.channels[-1].sound == "two.wav"


def test_repeated_same_gesture_does_not_fade_previous_audio() -> None:
    pygame = _FakePygame()
    player = FingerAudioPlayer({1: Path("one.wav")}, pygame_module=pygame)

    player.process((_event("Left", 1, 0),))
    first_channel = pygame.mixer.channels[0]
    player.process((_event("Left", 1, 500),))

    assert first_channel.fadeout_ms is None


def test_silent_gesture_fades_the_same_hands_audio() -> None:
    pygame = _FakePygame()
    player = FingerAudioPlayer({1: Path("one.wav")}, pygame_module=pygame)

    player.process((_event("Left", 1, 0), _event("Right", 1, 0)))
    left_channel, right_channel = pygame.mixer.channels
    player.process((_event("Left", 5, 350),))

    assert left_channel.fadeout_ms == 150
    assert right_channel.fadeout_ms is None


def test_switch_does_not_fade_a_channel_reused_by_drum_audio() -> None:
    pygame = _FakePygame()
    player = FingerAudioPlayer(
        {1: Path("one.wav"), 2: Path("two.wav")},
        pygame_module=pygame,
    )

    player.process((_event("Left", 1, 0),))
    reused_channel = pygame.mixer.channels[0]
    reused_channel.sound = "drum.wav"
    player.process((_event("Left", 2, 350),))

    assert reused_channel.fadeout_ms is None


def test_unmapped_gestures_are_recognized_but_silent() -> None:
    pygame = _FakePygame()
    player = FingerAudioPlayer({1: Path("one.wav")}, pygame_module=pygame)

    player.process((_event("Left", 5, 100), _event("Right", 6, 100)))

    assert pygame.mixer.channels == []
