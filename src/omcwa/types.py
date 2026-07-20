"""Core recording and calibration types."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeAlias

import numpy as np
import numpy.typing as npt


@dataclass
class Calibration:
    """Accelerometer calibration parameters.

    Produced by omconvert auto-calibrate, or via ``identity()`` for a no-op.
    """

    scale: npt.NDArray[np.float64]  # shape (3,)
    offset: npt.NDArray[np.float64]  # shape (3,)
    temp_offset: npt.NDArray[np.float64]  # shape (3,)
    ref_temp: float
    error_code: int
    success: bool

    @classmethod
    def from_native(cls, native_cal: Any) -> Calibration:
        """Construct from an ``omcwa._native.Calibration`` instance."""
        return cls(
            scale=np.asarray(native_cal.scale, dtype=np.float64),
            offset=np.asarray(native_cal.offset, dtype=np.float64),
            temp_offset=np.asarray(native_cal.temp_offset, dtype=np.float64),
            ref_temp=float(native_cal.reference_temperature),
            error_code=int(native_cal.error_code),
            success=bool(native_cal.success),
        )

    @classmethod
    def identity(cls) -> Calibration:
        """Return identity (no-op) calibration parameters."""
        return cls(
            scale=np.ones(3, dtype=np.float64),
            offset=np.zeros(3, dtype=np.float64),
            temp_offset=np.zeros(3, dtype=np.float64),
            ref_temp=0.0,
            error_code=0,
            success=True,
        )


@dataclass
class UniformRecording:
    """Uncalibrated IMU samples on a uniform grid at the file default rate.

    Arrays are float64 in physical units (g for accelerometer, dps for
    gyroscope). Calibration is identity (pre-cal / uncalibrated).
    """

    time: npt.NDArray[np.float64]
    acc: npt.NDArray[np.float64]
    gyr: npt.NDArray[np.float64] | None
    temp: npt.NDArray[np.float64] | None
    metadata: dict[str, Any]
    path: str | None = None


@dataclass
class CalibratedRecording:
    """Recording after accelerometer calibration."""

    time: npt.NDArray[np.float64]
    acc: npt.NDArray[np.float64]
    gyr: npt.NDArray[np.float64] | None
    temp: npt.NDArray[np.float64] | None
    calibration: Calibration
    metadata: dict[str, Any]
    path: str | None = None


@dataclass
class ProcessedRecording:
    """Uniformly resampled IMU streams.

    Temperature is not retained on this type.
    """

    sample_rate_hz: float
    time: npt.NDArray[np.float64]
    acc: npt.NDArray[np.float64]
    gyr: npt.NDArray[np.float64] | None
    calibration: Calibration | None
    metadata: dict[str, Any]
    valid: npt.NDArray[np.bool_] | None = None
    clipped: npt.NDArray[np.bool_] | None = None


# pipeline hook: uniform pre-cal samples -> calibrated recording.
CalibrateFn: TypeAlias = Callable[[UniformRecording], CalibratedRecording]

# pipeline hook: calibrated recording -> uniformly resampled output.
ResampleFn: TypeAlias = Callable[[CalibratedRecording], ProcessedRecording]


def source_path(recording: UniformRecording | CalibratedRecording) -> str:
    """Return the on-disk CWA path required by native omconvert backends."""
    if recording.path:
        return str(recording.path)

    msg = "Recording has no path. Cannot run native omconvert backend."
    raise ValueError(msg)


def ensure_path_str(path: str | Path) -> str:
    """Normalise a filesystem path to a string."""
    return str(Path(path))
