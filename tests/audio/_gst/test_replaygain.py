import math

import pytest

from mopidy._lib.gi import Gst
from mopidy.audio._gst.replaygain import (
    MAX_VOLUME,
    GainTags,
    ReplayGain,
    compute_volume,
)

TAGGED = GainTags(track_gain=-4.3, track_peak=0.3, album_gain=-7.0, album_peak=0.3)


def to_db(volume):
    return 20 * math.log10(volume)


def make_taglist(values):
    fields = ", ".join(f"{tag}=(double){value}" for tag, value in values.items())
    return Gst.TagList.new_from_string(f"taglist, {fields}")


class ProbeInfo:
    """Stands in for the Gst.PadProbeInfo that a pad probe gets."""

    def __init__(self, event):
        self._event = event

    def get_event(self):
        return self._event


@pytest.mark.parametrize(
    ("mode", "expected_db"),
    [("off", 0.0), ("track", -4.3), ("album", -7.0)],
)
def test_mode_picks_the_gain(mode, expected_db):
    volume = compute_volume(mode, TAGGED, preamp=0, fallback_gain=0)

    assert to_db(volume) == pytest.approx(expected_db)


def test_album_mode_falls_back_to_track_gain():
    tags = GainTags(track_gain=-4.3)

    volume = compute_volume("album", tags, preamp=0, fallback_gain=0)

    assert to_db(volume) == pytest.approx(-4.3)


def test_track_mode_falls_back_to_album_gain():
    tags = GainTags(album_gain=-7.0)

    volume = compute_volume("track", tags, preamp=0, fallback_gain=0)

    assert to_db(volume) == pytest.approx(-7.0)


def test_preamp_is_added_to_the_tagged_gain():
    volume = compute_volume("track", TAGGED, preamp=3, fallback_gain=0)

    assert to_db(volume) == pytest.approx(-1.3)


def test_untagged_track_gets_the_fallback_gain_without_preamp():
    volume = compute_volume("track", GainTags(), preamp=3, fallback_gain=-6)

    assert to_db(volume) == pytest.approx(-6.0)


def test_off_ignores_the_fallback_gain():
    volume = compute_volume("off", GainTags(), preamp=0, fallback_gain=-6)

    assert volume == 1.0


def test_peak_limits_the_gain_so_the_track_does_not_clip():
    # +10 dB would take a peak of 0.5 to 1.58, so it is limited to 1/0.5.
    tags = GainTags(track_gain=10.0, track_peak=0.5)

    volume = compute_volume("track", tags, preamp=0, fallback_gain=0)

    assert volume == pytest.approx(2.0)


def test_peak_above_full_scale_does_not_turn_the_track_down():
    tags = GainTags(track_gain=-1.0, track_peak=1.4)

    volume = compute_volume("track", tags, preamp=0, fallback_gain=0)

    assert to_db(volume) == pytest.approx(-1.0)


def test_volume_never_exceeds_what_the_volume_element_accepts():
    tags = GainTags(track_gain=30.0)

    volume = compute_volume("track", tags, preamp=0, fallback_gain=0)

    assert volume == MAX_VOLUME


def test_tags_are_read_from_a_taglist():
    taglist = make_taglist({Gst.TAG_TRACK_GAIN: -4.3, Gst.TAG_ALBUM_PEAK: 0.5})

    tags = GainTags().updated_from(taglist)

    assert tags == GainTags(track_gain=-4.3, album_peak=0.5)


def test_later_tags_keep_the_earlier_values():
    tags = GainTags(track_gain=-4.3)

    tags = tags.updated_from(make_taglist({Gst.TAG_ALBUM_GAIN: -7.0}))

    assert tags == GainTags(track_gain=-4.3, album_gain=-7.0)


@pytest.fixture
def replaygain():
    return ReplayGain(preamp=0.0, fallback_gain=-6.0)


def send(replaygain, event):
    replaygain._on_event(None, ProbeInfo(event))


def volume_db(replaygain):
    return to_db(replaygain.element.get_property("volume"))


def test_element_is_a_volume_element(replaygain):
    assert replaygain.element.get_factory().get_name() == "volume"


def test_is_off_until_a_mode_is_set(replaygain):
    send(replaygain, Gst.Event.new_stream_start("track-1"))
    send(replaygain, Gst.Event.new_tag(make_taglist({Gst.TAG_TRACK_GAIN: -4.3})))

    assert replaygain.element.get_property("volume") == 1.0


def test_tags_of_the_playing_track_set_the_volume(replaygain):
    replaygain.set_mode("track")

    send(replaygain, Gst.Event.new_stream_start("track-1"))
    assert volume_db(replaygain) == pytest.approx(-6.0)  # No tags yet.

    send(replaygain, Gst.Event.new_tag(make_taglist({Gst.TAG_TRACK_GAIN: -4.3})))
    assert volume_db(replaygain) == pytest.approx(-4.3)


def test_next_track_does_not_keep_the_previous_tracks_gain(replaygain):
    # In gapless playback, the next track's stream-start is the only sign
    # that the track changed.
    replaygain.set_mode("track")
    send(replaygain, Gst.Event.new_stream_start("track-1"))
    send(replaygain, Gst.Event.new_tag(make_taglist({Gst.TAG_TRACK_GAIN: -4.3})))

    send(replaygain, Gst.Event.new_stream_start("track-2"))

    assert volume_db(replaygain) == pytest.approx(-6.0)


def test_mode_change_applies_to_the_playing_track(replaygain):
    send(replaygain, Gst.Event.new_stream_start("track-1"))
    taglist = make_taglist({Gst.TAG_TRACK_GAIN: -4.3, Gst.TAG_ALBUM_GAIN: -7.0})
    send(replaygain, Gst.Event.new_tag(taglist))

    replaygain.set_mode("album")
    assert volume_db(replaygain) == pytest.approx(-7.0)

    replaygain.set_mode("track")
    assert volume_db(replaygain) == pytest.approx(-4.3)

    replaygain.set_mode("off")
    assert replaygain.element.get_property("volume") == 1.0
