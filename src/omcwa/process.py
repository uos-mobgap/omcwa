"""Load and process CWA recordings."""

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
    """Raised when omconvert cannot find a valid auto-calibration.

    -1 and -2 need opposite remedies: -1 means the recording barely held
    still, -2 means it held still but only ever in one posture. ``num_axes``
    and the axis coverage in the message tell them apart.
    """

    def __init__(self, error_code: int, calibration: Calibration) -> None:
        self.error_code = int(error_code)
        self.calibration = calibration
        super().__init__(
            "omconvert auto-calibration failed with "
            f"error code {self.error_code} "
            f"({calibration.num_stationary_points} stationary points, "
            f"{calibration.num_axes} axes within range, "
            f"axis_min={calibration.axis_min.tolist()}, "
            f"axis_max={calibration.axis_max.tolist()})"
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
    acc = np.asarray(result["acc"], dtype=np.float64)
    return ProcessedRecording(
        sample_rate_hz=float(result["sample_rate_hz"]),
        start_time=float(result["start_time"]),
        n_samples=acc.shape[0],
        acc=acc,
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
        with_time=False,
    )
    metadata = _public_metadata(
        loaded,
        sample_rate_hz=float(result["sample_rate_hz"]),
    )

    gyr = result.get("gyr")
    acc = np.asarray(result["acc"], dtype=np.float64)
    return UniformRecording(
        sample_rate_hz=float(result["sample_rate_hz"]),
        start_time=float(result["start_time"]),
        n_samples=acc.shape[0],
        acc=acc,
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

    Auto-calibration uses the first session. Calibration failure raises
    :class:`CalibrationError` before output arrays are allocated. Set
    ``on_calibration_failure="identity"`` to keep omconvert's identity
    fallback, or set ``calibrate=False`` to skip fitting.

    ``sample_rate_hz=0`` selects the file default rate. ``time_range`` is a
    half-open ``(start, stop)`` interval in Unix seconds. It trims the output
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
        raise CalibrationError(calibration.error_code, calibration)

    # ProcessedRecording has no temperature field and derives time from
    # start_time/sample_rate_hz, so skip allocating both. That is 16 bytes
    # per sample, 1.15 GB on a 200-hour 100 Hz recording.
    result = loaded.resample(
        native_calibration,
        sample_rate_hz=sample_rate_hz,
        interpolate=int(interpolate),
        with_temp=False,
        with_time=False,
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
