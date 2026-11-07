from unittest import mock

import pytest

from mopidy import exceptions
from mopidy._lib.gi import GLib, Gst
from mopidy.audio._gst import types
from mopidy.audio._gst.pipeline import (
    GstOutputBin,
    GstPlaybackPipeline,
    make_output_bin,
)
from mopidy.types import PlaybackState


@pytest.fixture
def pipeline():
    config = {
        "audio": {
            "output": "testoutput",
            "buffer_time": None,
            "replaygain": "off",
            "replaygain_preamp": 0.0,
            "replaygain_fallback_gain": 0.0,
        },
    }
    pipeline = GstPlaybackPipeline(
        config,
        on_bus_message=mock.Mock(),
        on_position=mock.Mock(),
        on_about_to_finish=mock.Mock(),
        on_source_setup=mock.Mock(),
    )
    yield pipeline
    pipeline.teardown()


def test_playbin_plays_audio_only(pipeline):
    assert pipeline.playbin.get_property("flags") == types.GstPlayFlags.AUDIO


def test_rgvolume_is_in_the_audio_sink(pipeline):
    assert pipeline.rgvolume.get_factory().get_name() == "rgvolume"


def test_replaygain_is_disabled_by_default(pipeline):
    assert pipeline.get_replaygain() == "off"
    assert pipeline.rgvolume.get_property("target-gain") == 0.0


def test_set_replaygain_sets_album_mode(pipeline):
    assert pipeline.set_replaygain("album") is True

    assert pipeline.get_replaygain() == "album"
    assert pipeline.rgvolume.get_property("album-mode") is True

    assert pipeline.set_replaygain("track") is True

    assert pipeline.get_replaygain() == "track"
    assert pipeline.rgvolume.get_property("album-mode") is False


def test_set_replaygain_preamp_is_applied_when_enabled(pipeline):
    pipeline.set_replaygain("track")
    pipeline.set_replaygain_preamp(6.0)

    assert pipeline.get_replaygain_preamp() == 6.0
    assert pipeline.rgvolume.get_property("pre-amp") == 6.0
    assert pipeline.rgvolume.get_property("target-gain") == 6.0

def test_cancel_replaygain_clamps_preamp_to_bounds(pipeline):
    pipeline.set_replaygain("off")

    with mock.patch.object(pipeline.rgvolume, "get_property") as mock_get_prop:
        def fake_get_property(name):
            if name == "target-gain":
                return -70.0
            if name == "pre-amp":
                return 0.0
            return mock.DEFAULT

        mock_get_prop.side_effect = fake_get_property
        pipeline._cancel_replaygain()

    assert pipeline.rgvolume.get_property("pre-amp") == 60.0



def test_set_replaygain_fallback_gain_is_applied(pipeline):
    pipeline.set_replaygain("track")
    pipeline.set_replaygain_fallback_gain(-3.0)

    assert pipeline.get_replaygain_fallback_gain() == -3.0
    assert pipeline.rgvolume.get_property("fallback-gain") == -3.0
    assert pipeline.rgvolume.get_property("target-gain") == -3.0


def test_disabling_replaygain_cancels_the_applied_gain(pipeline):
    pipeline.set_replaygain("track")
    pipeline.set_replaygain_preamp(6.0)
    assert pipeline.rgvolume.get_property("target-gain") == 6.0

    pipeline.set_replaygain("off")

    assert pipeline.get_replaygain() == "off"
    assert pipeline.get_replaygain_preamp() == 6.0
    assert pipeline.rgvolume.get_property("target-gain") == 0.0


def test_disabling_replaygain_cancels_the_fallback_gain(pipeline):
    pipeline.set_replaygain_fallback_gain(-3.0)

    assert pipeline.get_replaygain_fallback_gain() == -3.0
    assert pipeline.rgvolume.get_property("target-gain") == 0.0


def test_enabling_replaygain_restores_the_preamp(pipeline):
    pipeline.set_replaygain("track")
    pipeline.set_replaygain_preamp(6.0)
    pipeline.set_replaygain("off")

    pipeline.set_replaygain("track")

    assert pipeline.rgvolume.get_property("pre-amp") == 6.0
    assert pipeline.rgvolume.get_property("target-gain") == 6.0


def test_download_flag_is_passed_to_playbin_if_download_buffering_is_enabled(pipeline):
    pipeline.set_uri("some:uri", download=True)

    flags = pipeline.playbin.get_property("flags")
    assert flags == types.GstPlayFlags.AUDIO | types.GstPlayFlags.DOWNLOAD


def test_download_flag_is_not_passed_to_playbin_if_download_buffering_is_disabled(
    pipeline,
):
    pipeline.set_uri("some:uri", download=False)

    flags = pipeline.playbin.get_property("flags")
    assert flags == types.GstPlayFlags.AUDIO


def test_set_uri_sets_the_uri_on_the_playbin(pipeline):
    pipeline.set_uri("file:///tmp/foo.mp3")

    assert pipeline.playbin.get_property("uri") == "file:///tmp/foo.mp3"


def test_get_position_is_zero_before_playback(pipeline):
    assert pipeline.get_position() == 0


def test_set_state_returns_true_on_success(pipeline):
    assert pipeline.set_state(types.GstState.READY) is True


def test_make_output_bin_uses_a_fakesink_for_the_test_output():
    output_bin = make_output_bin("testoutput")

    assert not isinstance(output_bin, GstOutputBin)
    assert output_bin.get_factory().get_name() == "fakesink"


def test_make_output_bin_builds_the_described_output():
    output_bin = make_output_bin("fakesink")

    assert isinstance(output_bin, GstOutputBin)
    assert output_bin.get_static_pad("sink") is not None


def test_output_bin_takes_more_than_one_output():
    output_bin = GstOutputBin()
    output_bin.add_output("fakesink")
    output_bin.add_output("fakesink")

    assert output_bin.numchildren == 5  # tee, and a queue plus a bin per output


def test_make_output_bin_raises_on_an_unknown_output():
    with pytest.raises(exceptions.AudioException):
        make_output_bin("definitelynotanelement")


def test_output_bin_rejects_an_unknown_output():
    output_bin = GstOutputBin()

    with pytest.raises(exceptions.AudioException):
        output_bin.add_output("definitelynotanelement")


def test_decode_bus_message_ignores_state_changes_from_other_elements(pipeline):
    other = Gst.ElementFactory.make("fakesink")
    message = Gst.Message.new_state_changed(
        other, Gst.State.NULL, Gst.State.READY, Gst.State.VOID_PENDING
    )

    assert pipeline._decode_bus_message(message) is None


def test_decode_bus_message_decodes_the_playbin_state_change(pipeline):
    message = Gst.Message.new_state_changed(
        pipeline.playbin, Gst.State.NULL, Gst.State.READY, Gst.State.PLAYING
    )

    assert pipeline._decode_bus_message(message) == types.GstStateChanged(
        old_state=types.GstState.NULL,
        new_state=types.GstState.READY,
        pending_state=types.GstState.PLAYING,
    )


def test_decode_bus_message_decodes_buffering_with_its_mode(pipeline):
    message = Gst.Message.new_buffering(pipeline.playbin, 42)

    decoded = pipeline._decode_bus_message(message)

    assert isinstance(decoded, types.GstBuffering)
    assert decoded.percent == 42
    assert decoded.mode == Gst.BufferingMode.STREAM


def test_decode_bus_message_decodes_end_of_stream(pipeline):
    message = Gst.Message.new_eos(pipeline.playbin)

    assert pipeline._decode_bus_message(message) == types.GstEndOfStream()


def test_decode_bus_message_decodes_a_warning(pipeline):
    error = GLib.Error.new_literal(Gst.CoreError.quark(), "bad", Gst.CoreError.FAILED)
    message = Gst.Message.new_warning(pipeline.playbin, error, "debug text")

    decoded = pipeline._decode_bus_message(message)

    assert isinstance(decoded, types.GstWarning)
    assert decoded.debug == "debug text"


def test_decode_bus_message_converts_the_tags(pipeline):
    taglist = Gst.TagList.new_empty()
    taglist.add_value(Gst.TagMergeMode.APPEND, "title", "a title")
    message = Gst.Message.new_tag(pipeline.playbin, taglist)

    assert pipeline._decode_bus_message(message) == types.GstTag({"title": ["a title"]})


def test_decode_bus_message_drops_what_the_audio_layer_ignores(pipeline):
    message = Gst.Message.new_latency(pipeline.playbin)

    assert pipeline._decode_bus_message(message) is None


def test_gst_state_maps_to_playback_state():
    assert types.GstState.NULL.playback_state == PlaybackState.STOPPED
    assert types.GstState.PAUSED.playback_state == PlaybackState.PAUSED
    assert types.GstState.PLAYING.playback_state == PlaybackState.PLAYING


def test_gst_state_has_no_playback_state_between_tracks():
    assert types.GstState.READY.playback_state is None
    assert types.GstState.VOID_PENDING.playback_state is None


def test_gst_state_converts_both_ways():
    assert types.GstState(Gst.State.PAUSED) is types.GstState.PAUSED
    assert types.GstState.PAUSED.value == Gst.State.PAUSED


def test_decode_bus_message_drops_extended_message_types(pipeline):
    message = Gst.Message.new_property_notify(pipeline.playbin, "foo", None)

    assert pipeline._decode_bus_message(message) is None
