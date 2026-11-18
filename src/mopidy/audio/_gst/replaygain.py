"""ReplayGain: play every track at about the same loudness.

ReplayGain tags in a file say how much to turn the track up or down so it
plays at a reference loudness. Applying that as one fixed gain per track evens
out the loudness between tracks, but keeps the quiet and loud passages within
each track as they are.

Mopidy does not analyze audio itself. Tracks without ReplayGain tags play with
the configured fallback gain.
"""

from __future__ import annotations

import dataclasses
import logging
import threading
from typing import Literal

from mopidy import exceptions
from mopidy._lib.gi import Gst

logger = logging.getLogger(__name__)

type GainMode = Literal["off", "track", "album"]
"""The ReplayGain modes the audio layer applies. Core resolves `auto`."""

MAX_VOLUME = 10.0
"""The highest value GStreamer's volume element accepts, i.e. +20 dB."""


@dataclasses.dataclass(frozen=True)
class GainTags:
    """The ReplayGain tags of the current track. Gains in dB, peaks linear."""

    track_gain: float | None = None
    track_peak: float | None = None
    album_gain: float | None = None
    album_peak: float | None = None

    def updated_from(self, taglist: Gst.TagList) -> GainTags:
        """Return a copy with the values found in `taglist` replaced."""
        changes = {}
        for field, tag in _TAG_NAMES.items():
            found, value = taglist.get_double(tag)
            if found and _is_valid(field, value):
                changes[field] = value
        return dataclasses.replace(self, **changes)


_TAG_NAMES = {
    "track_gain": Gst.TAG_TRACK_GAIN,
    "track_peak": Gst.TAG_TRACK_PEAK,
    "album_gain": Gst.TAG_ALBUM_GAIN,
    "album_peak": Gst.TAG_ALBUM_PEAK,
}


def _is_valid(field: str, value: float) -> bool:
    """Reject broken tag values, using the same limits as GStreamer's rgvolume."""
    return -60 < value < 60 if field.endswith("gain") else value > 0


def compute_volume(
    mode: GainMode,
    tags: GainTags,
    *,
    preamp: float,
    fallback_gain: float,
) -> float:
    """Return the linear volume that applies ReplayGain to a track.

    Args:
        mode: Which gain to prefer. The other one is used if it is missing.
        tags: The track's ReplayGain tags.
        preamp: Extra gain in dB added to the tagged gain.
        fallback_gain: Gain in dB for tracks without any ReplayGain tags.
    """
    if mode == "off":
        return 1.0

    track = (tags.track_gain, tags.track_peak)
    album = (tags.album_gain, tags.album_peak)
    preferred, other = (album, track) if mode == "album" else (track, album)
    gain, peak = preferred if preferred[0] is not None else other

    volume = _db_to_linear(fallback_gain if gain is None else gain + preamp)

    # Don't turn the loudest sample up past full scale, as that would clip.
    # Like GStreamer's rgvolume, assume full scale if the peak is unknown, and
    # never turn a track down just because a lossy file peaks above it.
    limit = 1.0 / min(peak or 1.0, 1.0)
    return min(volume, limit, MAX_VOLUME)


def _db_to_linear(db: float) -> float:
    return 10 ** (db / 20)


class ReplayGain:
    """A GStreamer volume element that applies ReplayGain as tracks start.

    A probe on the element's sink pad sees each track's stream-start and tag
    events in order with its audio. So the new track's gain applies from its
    first buffer, also when the next track follows gaplessly.
    """

    element: Gst.Element
    """The volume element to link into the audio sink."""

    def __init__(self, *, preamp: float, fallback_gain: float) -> None:
        element = Gst.ElementFactory.make("volume", "replaygain")
        if element is None:
            msg = "Failed to create GStreamer volume element for ReplayGain."
            raise exceptions.AudioException(msg)
        self.element = element

        self._preamp = preamp
        self._fallback_gain = fallback_gain
        self._mode: GainMode = "off"
        self._tags = GainTags()

        # The probe runs on GStreamer's streaming thread, while set_mode() is
        # called from the audio actor's thread.
        self._lock = threading.Lock()

        sink_pad = element.get_static_pad("sink")
        if sink_pad is None:
            msg = "Failed to get sink pad of the ReplayGain volume element."
            raise exceptions.AudioException(msg)
        sink_pad.add_probe(Gst.PadProbeType.EVENT_DOWNSTREAM, self._on_event)

    def set_mode(self, mode: GainMode) -> None:
        """Change the mode. Takes effect immediately, also during playback."""
        with self._lock:
            self._mode = mode
            self._apply()

    def _on_event(self, _pad: Gst.Pad, info: Gst.PadProbeInfo) -> Gst.PadProbeReturn:
        event = info.get_event()
        if event is not None and event.type == Gst.EventType.STREAM_START:
            # A new track starts, so the previous track's tags no longer apply.
            with self._lock:
                self._tags = GainTags()
                self._apply()
        elif event is not None and event.type == Gst.EventType.TAG:
            taglist = event.parse_tag()
            with self._lock:
                self._tags = self._tags.updated_from(taglist)
                self._apply()
        return Gst.PadProbeReturn.OK

    def _apply(self) -> None:
        """Set the volume for the current mode and tags. Hold the lock."""
        volume = compute_volume(
            self._mode,
            self._tags,
            preamp=self._preamp,
            fallback_gain=self._fallback_gain,
        )
        self.element.set_property("volume", volume)
        logger.debug("ReplayGain %s, %s: volume %.3f", self._mode, self._tags, volume)
