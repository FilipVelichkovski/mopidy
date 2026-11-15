from unittest import mock

import pytest

from mopidy import audio, core
from mopidy.exceptions import ValidationError


@pytest.fixture
def audio_mock():
    return mock.Mock(spec=audio.Audio)


def make_core(audio_mock, mode="off"):
    return core.Core(
        config={"audio": {"replaygain": mode}},
        backends=[],
        audio=audio_mock,
    )


def test_mode_starts_as_configured(audio_mock):
    c = make_core(audio_mock, "track")

    assert c.playback.get_replaygain_mode() == "track"
    audio_mock.set_replaygain_mode.assert_called_once_with("track")


def test_mode_is_off_without_config(audio_mock):
    c = core.Core(config={}, backends=[], audio=audio_mock)

    assert c.playback.get_replaygain_mode() == "off"
    audio_mock.set_replaygain_mode.assert_not_called()


def test_auto_mode_starts_as_album_mode(audio_mock):
    make_core(audio_mock, "auto")

    audio_mock.set_replaygain_mode.assert_called_once_with("album")


def test_set_mode_applies_it_to_the_audio(audio_mock):
    c = make_core(audio_mock)

    c.playback.set_replaygain_mode("album")

    assert c.playback.get_replaygain_mode() == "album"
    audio_mock.set_replaygain_mode.assert_called_once_with("album")


def test_set_unknown_mode_fails(audio_mock):
    c = make_core(audio_mock)

    with pytest.raises(ValidationError):
        c.playback.set_replaygain_mode("loud")

    assert c.playback.get_replaygain_mode() == "off"
    audio_mock.set_replaygain_mode.assert_not_called()


@mock.patch.object(core.CoreListener, "send")
def test_mode_change_triggers_options_changed(send, audio_mock):
    c = make_core(audio_mock)

    c.playback.set_replaygain_mode("track")
    c.playback.set_replaygain_mode("track")

    send.assert_called_once_with("options_changed")


def test_auto_mode_follows_random(audio_mock):
    c = make_core(audio_mock, "auto")

    c.tracklist.set_random(True)
    audio_mock.set_replaygain_mode.assert_called_with("track")

    c.tracklist.set_random(False)
    audio_mock.set_replaygain_mode.assert_called_with("album")


def test_random_does_not_change_other_modes(audio_mock):
    c = make_core(audio_mock, "track")
    audio_mock.reset_mock()

    c.tracklist.set_random(True)

    audio_mock.set_replaygain_mode.assert_not_called()


def test_mode_can_be_set_without_audio():
    c = core.Core(config={}, backends=[])

    c.playback.set_replaygain_mode("track")

    assert c.playback.get_replaygain_mode() == "track"
