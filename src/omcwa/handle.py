"""CWA file handle with single native load."""

from __future__ import annotations

from pathlib import Path

from omcwa import _native
from omcwa.defaults import DEFAULT_INTERPOLATE, USE_FILE_SAMPLE_RATE
from omcwa.types import UniformRecording, ensure_path_str


class CwaHandle:
    """Owns one loaded CWA file for reuse across pipeline stages.

    Parameters
    ----------
    path :
        Path to a ``.cwa`` file.
    """

    def __init__(self, path: str | Path) -> None:
        """Load ``path`` once into a native ``LoadedCwa`` instance."""
        self.path = ensure_path_str(path)
        self._loaded = _native.LoadedCwa.load(self.path)

    def metadata(self) -> dict:
        """Return device and session metadata from the loaded file."""
        return dict(self._loaded.metadata())

    def materialize(
        self,
        *,
        sample_rate_hz: float = USE_FILE_SAMPLE_RATE,
        interpolate: int = int(DEFAULT_INTERPOLATE),
    ) -> UniformRecording:
        """Resample into float64 ``UniformRecording`` with identity cal.

        Parameters
        ----------
        sample_rate_hz :
            Target uniform rate in Hz. ``0`` uses the file default rate.
        interpolate :
            ``1`` nearest, ``2`` linear, ``3`` cubic.

        Returns
        -------
        UniformRecording
            Uncalibrated samples on a uniform grid at the requested rate.
        """
        identity = _native.identity_calibration()
        result = self._loaded.resample(
            identity,
            sample_rate_hz=sample_rate_hz,
            interpolate=interpolate,
        )
        metadata = self.metadata()
        metadata["sample_rate_hz"] = float(result["sample_rate_hz"])
        metadata["_cwa_handle"] = self

        gyr = result.get("gyr")
        return UniformRecording(
            time=result["time"],
            acc=result["acc"],
            gyr=None if gyr is None else gyr,
            temp=result["temp"],
            metadata=metadata,
            path=self.path,
        )


def open_cwa(path: str | Path) -> CwaHandle:
    """Open a CWA file and return a reusable handle.

    Parameters
    ----------
    path :
        Path to a ``.cwa`` file.

    Returns
    -------
    CwaHandle
        Handle that owns the native load for ``path``.
    """
    return CwaHandle(path)
