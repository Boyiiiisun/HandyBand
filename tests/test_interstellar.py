import importlib.util
from pathlib import Path

import mido
import numpy as np
import pytest

from handyband.guided_audio import GuidedAudio, render_notes
from handyband.guided_score import Note, training_score
from handyband.interstellar import Interstellar

spec = importlib.util.spec_from_file_location(
    "import_interstellar", Path(__file__).parents[1] / "scripts/import_interstellar.py")
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


def test_midi_tempo_changes_pedal_and_track_separation(tmp_path):
    midi = mido.MidiFile(ticks_per_beat=480)
    melody = mido.MidiTrack([
        mido.MetaMessage("set_tempo", tempo=500_000),
        mido.Message("control_change", control=64, value=127),
        mido.Message("note_on", note=72, velocity=80),
        mido.MetaMessage("set_tempo", tempo=1_000_000, time=480),
        mido.Message("note_off", note=72, time=480),
        mido.Message("control_change", control=64, value=0, time=480),
    ])
    bass = mido.MidiTrack([
        mido.Message("note_on", note=48, velocity=60),
        mido.Message("note_off", note=48, time=1440),
    ])
    midi.tracks.extend([melody, bass, mido.MidiTrack()])
    path = tmp_path / "fixture.mid"
    midi.save(path)
    tracks, bpm, _ = importer.read_midi(path)
    assert tracks[0][0].duration_ms == 2500
    assert tracks[1][0].duration_ms == 2500
    score = importer.make_score(tracks, bpm, 0, 0, 2000, 2, "test")
    assert all(n.pitch == 72 for cue in score.cues for n in cue.notes)
    assert all(n.pitch == 48 for n in score.accompaniment)
    assert score.duration_ms == 2000


def test_invalid_import_ranges_do_not_loop():
    for end in (float("inf"), float("nan"), -1, 100_000):
        with pytest.raises(ValueError):
            importer.make_score([[Note(0, 2000, 60)]], 120, 0, 0, end, 2, "test")


def test_synthesis_has_audio_and_no_integer_overflow():
    samples = render_notes((Note(0, 1000, 69),), 1200)
    assert samples.dtype == np.int16
    assert np.max(np.abs(samples)) > 1000
    assert np.max(np.abs(samples)) < 32767
    assert np.all(samples[24000:] == 0)


def test_theme_can_render_and_switch_modes_without_camera(tmp_path, monkeypatch):
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    theme = Interstellar(tmp_path / "absent.json")
    try:
        theme.on_key(ord("e"))
        theme.on_key(ord("l"))
        theme.on_key(32)
        theme.update((), 0)
        frame = theme.draw(np.zeros((480, 640, 3), dtype=np.uint8))
        assert frame.shape == (640, 960, 3)
        assert theme.session.hand == "Left"
        assert theme.session.mode == "Perform"
        assert theme.session.score.is_demo
    finally:
        theme.close()


def test_audio_has_no_melody_before_hit_and_stops_on_pause(monkeypatch):
    from handyband.guided_session import GuidedSession

    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    score = training_score()
    audio = GuidedAudio(score)
    session = GuidedSession(score)
    try:
        session.state = "Playing"
        audio.sync(session)
        assert not audio.melody_channel.get_busy()
        session.active = 0
        audio.sync(session)
        assert audio.melody_channel.get_busy()
        session.state = "Paused"
        audio.sync(session)
        assert not audio._playing
        audio.stop()
        assert not audio.melody_channel.get_busy()
        assert not audio.backing_channel.get_busy()
    finally:
        audio.close()
