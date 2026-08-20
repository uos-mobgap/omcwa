"""Recording and calibration types."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
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

    Accelerometer values are in g and gyroscope values are in dps.
    Calibration is identity. ``acc`` and ``gyr`` are float64 unless
    ``load_cwa`` was called with ``dtype="float32"``. ``temp`` and ``time``
    are float64 regardless.
    """

    sample_rate_hz: float
    start_time: float
    n_samples: int
    acc: npt.NDArray[np.floating]
    gyr: npt.NDArray[np.floating] | None
    temp: npt.NDArray[np.float64]
    metadata: dict[str, Any]
    path: str

    # set only when the timeline is not uniform, e.g. after dropping invalid
    # samples. None means every sample sits on the start_time/sample_rate_hz
    # grid, so time is computed from those fields instead of stored.
    time_override: npt.NDArray[np.float64] | None = None

    @cached_property
    def time(self) -> npt.NDArray[np.float64]:
        """Unix seconds per sample. Built on first access, cached after."""
        if self.time_override is not None:
            return self.time_override

        return (
            self.start_time
            + np.arange(self.n_samples, dtype=np.float64) / self.sample_rate_hz
        )

    @property
    def first_sample_time(self) -> float:
        """Time of the first sample. Allocates nothing."""
        if self.time_override is not None:
            return float(self.time_override[0])

        return self.start_time


@dataclass
class ProcessedRecording:
    """Uniformly resampled IMU streams.

    Temperature is not retained on this type. ``acc`` and ``gyr`` are
    float64 unless ``process_cwa`` was called with ``dtype="float32"``.
    ``time`` is float64 regardless.
    """

    sample_rate_hz: float
    start_time: float
    n_samples: int
    acc: npt.NDArray[np.floating]
    gyr: npt.NDArray[np.floating] | None
    calibration: Calibration
    metadata: dict[str, Any]
    valid: npt.NDArray[np.bool_]
    clipped: npt.NDArray[np.bool_]

    # see UniformRecording.time_override.
    time_override: npt.NDArray[np.float64] | None = None

    @cached_property
    def time(self) -> npt.NDArray[np.float64]:
        """Unix seconds per sample. Built on first access, cached after."""
        if self.time_override is not None:
            return self.time_override

        return (
            self.start_time
            + np.arange(self.n_samples, dtype=np.float64) / self.sample_rate_hz
        )

    @property
    def first_sample_time(self) -> float:
        """Time of the first sample. Allocates nothing."""
        if self.time_override is not None:
            return float(self.time_override[0])

        return self.start_time


def ensure_path_str(path: str | Path) -> str:
    """Normalise a filesystem path to a string."""
    return str(Path(path))
