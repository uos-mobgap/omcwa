"""Core recording and calibration types."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    num_axes: int = 0

    # diagnostics below are only meaningful after auto-calibrate. identity()
    # leaves them at their zero defaults. There are no stationary points to
    # report.
    num_stationary_points: int = 0
    axis_min: npt.NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )
    axis_max: npt.NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )
    mean_svm_error: float = 0.0

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
            num_axes=int(native_cal.num_axes),
            num_stationary_points=int(native_cal.num_stationary_points),
            axis_min=np.asarray(native_cal.axis_min, dtype=np.float64),
            axis_max=np.asarray(native_cal.axis_max, dtype=np.float64),
            mean_svm_error=float(native_cal.mean_svm_error),
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
    temp: npt.NDArray[np.float64]
    metadata: dict[str, Any]
    path: str


@dataclass
class ProcessedRecording:
    """Uniformly resampled IMU streams.

    Temperature is not retained on this type.
    """

    sample_rate_hz: float
    time: npt.NDArray[np.float64]
    acc: npt.NDArray[np.float64]
    gyr: npt.NDArray[np.float64] | None
    calibration: Calibration
    metadata: dict[str, Any]
    valid: npt.NDArray[np.bool_]
    clipped: npt.NDArray[np.bool_]


def ensure_path_str(path: str | Path) -> str:
    """Normalise a filesystem path to a string."""
    return str(Path(path))
