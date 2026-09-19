from pathlib import Path

from handyband.drum_audio import DrumAudioPlayer
from handyband.models import DrumEvent


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
        self.init_options = None
        self.channel_count = None
        self.loaded_paths = []
        self.channels = []
        self.closed = False

    def init(self, **options) -> None:
        self.init_options = options

    def set_num_channels(self, count: int) -> None:
        self.channel_count = count

    def Sound(self, path: str):
        self.loaded_paths.append(path)
        return path

    def find_channel(self, force: bool):
        assert force is True
        channel = _FakeChannel()
        self.channels.append(channel)
        return channel

    def quit(self) -> None:
        self.closed = True


class _FakePygame:
    def __init__(self) -> None:
        self.mixer = _FakeMixer()


def _event(handedness: str, volume: float, timestamp_ms: int) -> DrumEvent:
    return DrumEvent(handedness, "DRUM_HIT", 1.0, volume, timestamp_ms)


def test_loads_only_the_centered_drum_sample() -> None:
    pygame = _FakePygame()

    player = DrumAudioPlayer(Path("drum.wav"), pygame_module=pygame)

    assert pygame.mixer.loaded_paths == ["drum.wav"]
    player.close()
    assert pygame.mixer.closed is True


def test_single_hit_plays_after_80_ms_at_its_velocity_volume() -> None:
    pygame = _FakePygame()
    player = DrumAudioPlayer(Path("drum.wav"), pygame_module=pygame)

    player.process((_event("Left", 0.30, 100),), 100)
    player.process((), 179)
    assert pygame.mixer.channels == []

    player.process((), 180)
    assert pygame.mixer.channels[0].sound == "drum.wav"
    assert pygame.mixer.channels[0].volume == 0.30


def test_opposite_hand_hits_within_80_ms_combine_their_volumes() -> None:
    pygame = _FakePygame()
    player = DrumAudioPlayer(Path("drum.wav"), pygame_module=pygame)

    player.process((_event("Left", 0.35, 100),), 100)
    player.process((_event("Right", 0.45, 170),), 170)

    assert len(pygame.mixer.channels) == 1
    assert pygame.mixer.channels[0].volume == 0.80


def test_combined_volume_is_limited_to_one() -> None:
    pygame = _FakePygame()
    player = DrumAudioPlayer(Path("drum.wav"), pygame_module=pygame)

    player.process(
        (_event("Left", 0.60, 100), _event("Right", 0.60, 100)),
        100,
    )

    assert pygame.mixer.channels[0].volume == 1.0


def test_hits_outside_window_play_separately() -> None:
    pygame = _FakePygame()
    player = DrumAudioPlayer(Path("drum.wav"), pygame_module=pygame)

    player.process((_event("Left", 0.30, 100),), 100)
    player.process((_event("Right", 0.40, 181),), 181)
    player.process((), 261)

    assert [channel.volume for channel in pygame.mixer.channels] == [0.30, 0.40]
