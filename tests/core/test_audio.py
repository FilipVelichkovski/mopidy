from unittest import mock

import pytest

from mopidy import audio, core, exceptions


@pytest.fixture
def audio_mock():
    return mock.Mock(spec=audio.Audio)


@pytest.fixture
def core_with_audio_mock(audio_mock):
    return core.Core(
        config={},
        backends=[],
        audio=audio_mock,
    )


def test_get_replaygain(core_with_audio_mock, audio_mock):
    audio_mock.get_replaygain.return_value.get.return_value = "track"

    assert core_with_audio_mock.audio.get_replaygain() == "track"
    audio_mock.get_replaygain.assert_called_once_with()


def test_set_replaygain(core_with_audio_mock, audio_mock):
    audio_mock.set_replaygain.return_value.get.return_value = True

    assert core_with_audio_mock.audio.set_replaygain("album") is True
    audio_mock.set_replaygain.assert_called_once_with("album")


def test_set_replaygain_rejects_unknown_mode(core_with_audio_mock, audio_mock):
    with pytest.raises(exceptions.ValidationError):
        core_with_audio_mock.audio.set_replaygain("bogus")

    audio_mock.set_replaygain.assert_not_called()


def test_get_replaygain_preamp(core_with_audio_mock, audio_mock):
    audio_mock.get_replaygain_preamp.return_value.get.return_value = -3.5

    assert core_with_audio_mock.audio.get_replaygain_preamp() == -3.5
    audio_mock.get_replaygain_preamp.assert_called_once_with()


def test_set_replaygain_preamp(core_with_audio_mock, audio_mock):
    audio_mock.set_replaygain_preamp.return_value.get.return_value = True

    assert core_with_audio_mock.audio.set_replaygain_preamp(-3.5) is True
    audio_mock.set_replaygain_preamp.assert_called_once_with(-3.5)


def test_set_replaygain_preamp_rejects_non_numbers(core_with_audio_mock, audio_mock):
    with pytest.raises(exceptions.ValidationError):
        core_with_audio_mock.audio.set_replaygain_preamp("loud")

    audio_mock.set_replaygain_preamp.assert_not_called()


def test_get_replaygain_fallback_gain(core_with_audio_mock, audio_mock):
    audio_mock.get_replaygain_fallback_gain.return_value.get.return_value = -3.5

    assert core_with_audio_mock.audio.get_replaygain_fallback_gain() == -3.5
    audio_mock.get_replaygain_fallback_gain.assert_called_once_with()


def test_set_replaygain_fallback_gain(core_with_audio_mock, audio_mock):
    audio_mock.set_replaygain_fallback_gain.return_value.get.return_value = True

    assert core_with_audio_mock.audio.set_replaygain_fallback_gain(-3.5) is True
    audio_mock.set_replaygain_fallback_gain.assert_called_once_with(-3.5)


def test_set_replaygain_fallback_gain_rejects_non_numbers(
    core_with_audio_mock,
    audio_mock,
):
    with pytest.raises(exceptions.ValidationError):
        core_with_audio_mock.audio.set_replaygain_fallback_gain("quiet")

    audio_mock.set_replaygain_fallback_gain.assert_not_called()

@pytest.mark.parametrize("value", [-60.1, 60.1])
def test_set_replaygain_preamp_rejects_out_of_range(
    core_with_audio_mock,
    audio_mock,
    value,
):
    with pytest.raises(exceptions.ValidationError):
        core_with_audio_mock.audio.set_replaygain_preamp(value)

    audio_mock.set_replaygain_preamp.assert_not_called()


@pytest.mark.parametrize("value", [-60.1, 60.1])
def test_set_replaygain_fallback_gain_rejects_out_of_range(
    core_with_audio_mock,
    audio_mock,
    value,
):
    with pytest.raises(exceptions.ValidationError):
        core_with_audio_mock.audio.set_replaygain_fallback_gain(value)

    audio_mock.set_replaygain_fallback_gain.assert_not_called()



@pytest.fixture
def core_without_audio():
    return core.Core(
        config={},
        backends=[],
    )


def test_none_audio_get_replaygain_returns_none(core_without_audio):
    assert core_without_audio.audio.get_replaygain() is None


def test_none_audio_set_replaygain_returns_false(core_without_audio):
    assert core_without_audio.audio.set_replaygain("track") is False


def test_none_audio_get_replaygain_preamp_returns_none(core_without_audio):
    assert core_without_audio.audio.get_replaygain_preamp() is None


def test_none_audio_set_replaygain_preamp_returns_false(core_without_audio):
    assert core_without_audio.audio.set_replaygain_preamp(3.0) is False


def test_none_audio_get_replaygain_fallback_gain_returns_none(core_without_audio):
    assert core_without_audio.audio.get_replaygain_fallback_gain() is None


def test_none_audio_set_replaygain_fallback_gain_returns_false(core_without_audio):
    assert core_without_audio.audio.set_replaygain_fallback_gain(3.0) is False
