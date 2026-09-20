from dataclasses import replace

import pytest

from handyband.guided_score import Cue, Note, Score, load_score, training_score
from handyband.guided_session import GuidedSession


def score(gestures=(1, 2, 4)):
    return Score("Test", 120, tuple(
        Cue(i * 1000, 1000, g, i // 2, (Note(0, 900, 60 + i),))
        for i, g in enumerate(gestures)))


class Player:
    def __init__(self, session):
        self.session = session
        self.time = 0
        session.update(0, None, True)

    def advance(self, ms, gesture=None, tracked=True):
        for _ in range(ms // 50):
            self.time += 50
            self.session.update(self.time, gesture, tracked)


def ready(mode="Perform", gestures=(1, 2, 4)):
    session = GuidedSession(score(gestures))
    session.set_mode(mode)
    session.start()
    player = Player(session)
    return session, player


def test_practice_waits_with_wrong_shape_and_frozen_backing():
    session, player = ready("Practice")
    player.advance(5000, 5)
    assert session.state == "Waiting"
    assert session.position_ms == 0
    assert session.hits == set()
    assert not session.sounding
    player.advance(200, 1)
    assert session.hits == {0}
    assert session.active == 0


def test_early_correct_shape_is_quantized_to_start_and_triggers_once():
    session, player = ready()
    player.advance(1950, 1)
    assert not session.hits
    player.advance(50, 1)
    assert session.hits == {0}
    assert session.position_ms == 0
    player.advance(800, 1)
    assert session.hits == {0}
    assert session.active == 0


def test_wrong_shape_never_plays_melody_and_misses_do_not_stop_timeline():
    session, player = ready()
    player.advance(3500, 5)
    assert session.misses == {0, 1}
    assert session.active is None
    assert session.position_ms == 1500


def test_repeated_shape_requires_release():
    session, player = ready(gestures=(1, 1, 2))
    player.advance(3250, 1)
    assert session.hits == {0}
    assert 1 in session.misses


def test_release_and_repeat_can_play_adjacent_equal_cues():
    session, player = ready(gestures=(1, 1, 2))
    player.advance(2700, 1)
    player.advance(100, None)
    player.advance(400, 1)
    assert session.hits == {0, 1}


def test_tracking_loss_freezes_and_recovery_counts_in_at_same_position():
    session, player = ready()
    player.advance(2200, 1)
    player.advance(400, None, False)
    frozen = session.position_ms
    assert session.state == "Paused"
    assert session.active == 0
    assert not session.cut_short
    player.advance(2000, None, False)
    assert session.position_ms == frozen
    player.advance(250, 1)
    assert session.state == "Countdown"
    assert session.position_ms == frozen
    player.advance(1900, 1)
    assert session.position_ms == frozen


def test_manual_pause_does_not_auto_resume():
    session, player = ready()
    player.advance(2200, 1)
    session.toggle_pause()
    frozen = session.position_ms
    player.advance(4000, 1)
    assert session.state == "Paused"
    assert session.position_ms == frozen


def test_brief_jitter_does_not_cut_long_note_but_early_release_does():
    session, player = ready()
    player.advance(2050, 1)
    player.advance(100, None)
    assert session.active == 0
    player.advance(100, 1)
    player.advance(300, None)
    assert session.active is None
    assert session.cut_short == {0}


def test_finish_and_reset_clear_previous_results():
    session, player = ready()
    player.advance(5000, 5)
    assert session.state == "Finished"
    assert session.misses == {0, 1, 2}
    session.toggle_pause()
    assert session.state == "Countdown"
    assert not session.hits and not session.misses


def test_practice_next_phrase_starts_at_correct_score_position():
    session = GuidedSession(score())
    session.step_phrase(1)
    assert session.indices == [2]
    assert session.position_ms == 2000
    assert session.mode == "Practice"


def test_tutorial_has_one_cue_per_used_shape():
    session = GuidedSession(score((1, 1, 2)))
    assert session.indices == [0, 2]


def test_score_roundtrip(tmp_path):
    expected = training_score()
    path = tmp_path / "score.json"
    expected.save(path)
    assert load_score(path) == expected


@pytest.mark.parametrize("cue", [
    Cue(0, 1000, 3, 0, (Note(0, 900, 60),)),
    Cue(0, 1000, 1, 0, (Note(0, 1100, 60),)),
    Cue(float("nan"), 1000, 1, 0, (Note(0, 900, 60),)),
])
def test_invalid_cues_fail_before_audio(cue):
    with pytest.raises(ValueError):
        replace(score(), cues=(cue,))


def test_shape_withdrawn_before_beat_is_not_latched():
    session, player = ready()
    player.advance(1750, 1)
    player.advance(500, 2)
    assert not session.hits
    assert 0 in session.misses


def test_late_input_inside_window_plays_but_outside_does_not():
    session, player = ready()
    player.advance(1950, None)
    player.advance(200, 1)
    assert session.hits == {0}
    session, player = ready()
    player.advance(2050, None)
    player.advance(200, 1)
    assert session.hits == set()
    assert 0 in session.misses
