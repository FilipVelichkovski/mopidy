from __future__ import annotations

from typing import TYPE_CHECKING

from pykka.typing import proxy_method

from mopidy.core import _validation as validation

if TYPE_CHECKING:
    from mopidy.audio import AudioProxy
    from mopidy.types import ReplayGainMode

REPLAYGAIN_MODES = ("off", "track", "album")


class AudioController:
    """Manages audio settings."""

    def __init__(self, audio: AudioProxy | None) -> None:
        self._audio = audio

    def get_replaygain(self) -> ReplayGainMode | None:
        """Get the ReplayGain mode.

        Returns:
            One of `"off"`, `"track"`, or `"album"`, or `None` if the audio
            layer is unavailable.
        """
        if self._audio is None:
            return None
        return self._audio.get_replaygain().get()

    def set_replaygain(self, mode: ReplayGainMode) -> bool:
        """Set the ReplayGain mode.

        Can be changed while audio is playing.

        Args:
            mode: The ReplayGain mode to set. Must be one of `"off"`,
                `"track"`, or `"album"`.

        Returns:
            `True` if successful, else `False`.
        """
        validation.check_choice(mode, REPLAYGAIN_MODES)
        if self._audio is None:
            return False
        return self._audio.set_replaygain(mode).get()

    def get_replaygain_preamp(self) -> float | None:
        """Get the ReplayGain pre-amp in dB.

        Returns:
            The pre-amp in dB, or `None` if the audio layer is unavailable.
        """
        if self._audio is None:
            return None
        return self._audio.get_replaygain_preamp().get()

    def set_replaygain_preamp(self, preamp: float) -> bool:
        """Set the ReplayGain pre-amp in dB.

        Can be changed while audio is playing.

        Args:
            preamp: The pre-amp in dB, between -60 and 60.

        Returns:
            `True` if successful, else `False`.
        """
        validation.check_number(preamp, min=-60, max=60)
        if self._audio is None:
            return False
        return self._audio.set_replaygain_preamp(preamp).get()

    def get_replaygain_fallback_gain(self) -> float | None:
        """Get the gain in dB used for streams without ReplayGain tags.

        Returns:
            The fallback gain in dB, or `None` if the audio layer is unavailable.
        """
        if self._audio is None:
            return None
        return self._audio.get_replaygain_fallback_gain().get()

    def set_replaygain_fallback_gain(self, fallback_gain: float) -> bool:
        """Set the gain in dB used for streams without ReplayGain tags.

        Can be changed while audio is playing.

        Args:
            fallback_gain: The fallback gain in dB, between -60 and 60.

        Returns:
            `True` if successful, else `False`.
        """
        validation.check_number(fallback_gain, min=-60, max=60)
        if self._audio is None:
            return False
        return self._audio.set_replaygain_fallback_gain(fallback_gain).get()


class AudioControllerProxy:
    get_replaygain = proxy_method(AudioController.get_replaygain)
    set_replaygain = proxy_method(AudioController.set_replaygain)
    get_replaygain_preamp = proxy_method(AudioController.get_replaygain_preamp)
    set_replaygain_preamp = proxy_method(AudioController.set_replaygain_preamp)
    get_replaygain_fallback_gain = proxy_method(
        AudioController.get_replaygain_fallback_gain
    )
    set_replaygain_fallback_gain = proxy_method(
        AudioController.set_replaygain_fallback_gain
    )
