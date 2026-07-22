"""High-level CWA processing entry points."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import numpy as np

from omcwa import _native
from omcwa.defaults import (
    DEFAULT_CALIBRATE,
    DEFAULT_INTERPOLATE,
    DEFAULT_SAMPLE_RATE_HZ,
    DEFAULT_STATIONARY_TIME,
    USE_FILE_SAMPLE_RATE,
)
from omcwa.slice import slice_recording
from omcwa.types import (
    Calibration,
    ProcessedRecording,
    UniformRecording,
    ensure_path_str,
)

CalibrationFailurePolicy = Literal["raise", "identity"]


class CalibrationError(RuntimeError):
    """Raised when omconvert cannot find a valid auto-calibration."""

    def __init__(self, error_code: int) -> None:
        self.error_code = int(error_code)
        super().__init__(
            "omconvert auto-calibration failed with "
            f"error code {self.error_code}"
        )


def _validate_failure_policy(
    on_calibration_failure: str,
) -> CalibrationFailurePolicy:
    if on_calibration_failure not in {"raise", "identity"}:
        msg = (
            "on_calibration_failure must be 'raise' or 'identity', "
            f"got {on_calibration_failure!r}"
        )
        raise ValueError(msg)
    return on_calibration_failure


def _public_metadata(
    loaded: Any,
    *,
    sample_rate_hz: float,
) -> dict[str, Any]:
    """Return device/session metadata without retaining native state."""
    metadata = dict(loaded.metadata())
    metadata["sample_rate_hz"] = float(sample_rate_hz)
    return metadata


def _processed_from_native(
    result: Mapping[str, Any],
    *,
    calibration: Calibration,
    metadata: dict[str, Any],
) -> ProcessedRecording:
    gyr = result.get("gyr")
    return ProcessedRecording(
        sample_rate_hz=float(result["sample_rate_hz"]),
        time=np.asarray(result["time"], dtype=np.float64),
        acc=np.asarray(result["acc"], dtype=np.float64),
        gyr=None if gyr is None else np.asarray(gyr, dtype=np.float64),
        calibration=calibration,
        metadata=metadata,
        valid=np.asarray(result["valid"], dtype=np.bool_),
        clipped=np.asarray(result["clipped"], dtype=np.bool_),
    )


def load_cwa(path: str | Path) -> UniformRecording:
    """Load uncalibrated samples at the file default sample rate.

    The returned arrays are uniformly resampled with identity calibration.
    Accelerometer values are in g, gyroscope values are in degrees per second,
    temperature is in degrees Celsius, and time is Unix seconds.
    """
    path_str = ensure_path_str(path)
    loaded = _native.LoadedCwa.load(path_str)
    result = loaded.resample(
        _native.identity_calibration(),
        sample_rate_hz=USE_FILE_SAMPLE_RATE,
        interpolate=int(DEFAULT_INTERPOLATE),
    )
    metadata = _public_metadata(
        loaded,
        sample_rate_hz=float(result["sample_rate_hz"]),
    )

    gyr = result.get("gyr")
    return UniformRecording(
        time=np.asarray(result["time"], dtype=np.float64),
        acc=np.asarray(result["acc"], dtype=np.float64),
        gyr=None if gyr is None else np.asarray(gyr, dtype=np.float64),
        temp=np.asarray(result["temp"], dtype=np.float64),
        metadata=metadata,
        path=path_str,
    )


def process_cwa(
    path: str | Path,
    *,
    sample_rate_hz: float = DEFAULT_SAMPLE_RATE_HZ,
    calibrate: bool = DEFAULT_CALIBRATE,
    interpolate: int = int(DEFAULT_INTERPOLATE),
    stationary_time: float = DEFAULT_STATIONARY_TIME,
    on_calibration_failure: CalibrationFailurePolicy = "raise",
    time_range: tuple[float, float] | None = None,
) -> ProcessedRecording:
    """Auto-calibrate and resample a CWA recording with vendored omconvert.

    Auto-calibration uses the complete first session. By default, calibration
    failure raises :class:`CalibrationError` before output arrays are
    allocated. Set ``on_calibration_failure="identity"`` to explicitly accept
    omconvert's identity fallback, or set ``calibrate=False`` to skip fitting.

    ``sample_rate_hz=0`` selects the file default rate. ``time_range`` is a
    half-open ``(start, stop)`` interval in Unix seconds and trims the output
    only after full-file calibration and resampling.
    """
    failure_policy = _validate_failure_policy(on_calibration_failure)
    path_str = ensure_path_str(path)
    loaded = _native.LoadedCwa.load(path_str)

    if calibrate:
        native_calibration = loaded.auto_calibrate(
            sample_rate_hz=sample_rate_hz,
            interpolate=int(interpolate),
            stationary_time=stationary_time,
        )
    else:
        native_calibration = _native.identity_calibration()

    calibration = Calibration.from_native(native_calibration)
    if calibrate and not calibration.success and failure_policy == "raise":
        raise CalibrationError(calibration.error_code)

    result = loaded.resample(
        native_calibration,
        sample_rate_hz=sample_rate_hz,
        interpolate=int(interpolate),
    )
    metadata = _public_metadata(
        loaded,
        sample_rate_hz=float(result["sample_rate_hz"]),
    )
    out = _processed_from_native(
        result,
        calibration=calibration,
        metadata=metadata,
    )

    if time_range is not None:
        start, stop = time_range
        out = slice_recording(out, start=start, stop=stop)

    return out
