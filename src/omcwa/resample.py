"""Resampling backends."""

from __future__ import annotations

from typing import Any

import numpy as np

from omcwa import _native
from omcwa.defaults import DEFAULT_INTERPOLATE, USE_FILE_SAMPLE_RATE
from omcwa.handle import CwaHandle
from omcwa.types import (
    CalibratedRecording,
    Calibration,
    ProcessedRecording,
    source_path,
)

_INTERNAL_METADATA_KEYS = ("_cwa_handle", "_native_calibration")


def _public_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Copy metadata without pipeline-only keys that retain native state."""
    out = dict(metadata or {})
    for key in _INTERNAL_METADATA_KEYS:
        out.pop(key, None)
    return out


def processed_from_native(
    result: dict[str, Any],
    *,
    calibration: Calibration | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProcessedRecording:
    """Build a ``ProcessedRecording`` from a native resample/process result."""
    if calibration is None and "calibration" in result:
        calibration = Calibration.from_native(result["calibration"])

    gyr = result.get("gyr")
    return ProcessedRecording(
        sample_rate_hz=float(result["sample_rate_hz"]),
        time=np.asarray(result["time"], dtype=np.float64),
        acc=np.asarray(result["acc"], dtype=np.float64),
        gyr=None if gyr is None else np.asarray(gyr, dtype=np.float64),
        calibration=calibration,
        metadata=_public_metadata(metadata),
        valid=np.asarray(result["valid"], dtype=np.bool_),
        clipped=np.asarray(result["clipped"], dtype=np.bool_),
    )


def _loaded_from_recording(recording: CalibratedRecording) -> Any:
    """Return native LoadedCwa for ``recording``, reusing handle when set."""
    handle = recording.metadata.get("_cwa_handle")
    if isinstance(handle, CwaHandle):
        return handle._loaded

    return _native.LoadedCwa.load(source_path(recording))


class OmConvertResample:
    """Resample a recording using vendored omconvert.

    Uses the shared ``_cwa_handle`` when present instead of reloading the file.
    Calls ``LoadedCwa.resample`` with the native calibration stored in
    ``metadata["_native_calibration"]``.
    """

    def __init__(
        self,
        sample_rate_hz: float = USE_FILE_SAMPLE_RATE,
        interpolate: int = int(DEFAULT_INTERPOLATE),
    ) -> None:
        """Configure resampling parameters.

        Parameters
        ----------
        sample_rate_hz :
            Target uniform rate in Hz. ``0`` uses the file default rate.
        interpolate :
            ``1`` nearest, ``2`` linear, ``3`` cubic.
        """
        self.sample_rate_hz = sample_rate_hz
        self.interpolate = interpolate

    def __call__(self, recording: CalibratedRecording) -> ProcessedRecording:
        """Return ``recording`` resampled to a uniform rate."""
        loaded = _loaded_from_recording(recording)

        native_cal = recording.metadata.get("_native_calibration")
        if native_cal is None:
            msg = (
                "Recording metadata is missing _native_calibration. "
                "Use OmConvertCalibrate or "
                "uniform_to_calibrated_identity first."
            )
            raise ValueError(msg)

        result = loaded.resample(
            native_cal,
            self.sample_rate_hz,
            self.interpolate,
        )

        return processed_from_native(
            result,
            calibration=recording.calibration,
            metadata=recording.metadata,
        )


def calibrated_to_processed_identity_rate(
    recording: CalibratedRecording,
) -> ProcessedRecording:
    """Promote calibrated arrays to ``ProcessedRecording`` without resampling.

    ``sample_rate_hz`` is taken from metadata (``sample_rate_hz``, else
    ``default_rate``). ``valid`` and ``clipped`` are left unset. Pipeline-only
    keys (``_cwa_handle``, ``_native_calibration``) are dropped.
    """
    rate = float(recording.metadata.get("sample_rate_hz", 0.0))
    if rate < 0.0:
        msg = "sample_rate_hz must not be negative"
        raise ValueError(msg)
    if rate == 0.0:
        rate = float(recording.metadata.get("default_rate", 0.0))

    return ProcessedRecording(
        sample_rate_hz=rate,
        time=recording.time,
        acc=recording.acc,
        gyr=recording.gyr,
        calibration=recording.calibration,
        metadata=_public_metadata(recording.metadata),
    )
