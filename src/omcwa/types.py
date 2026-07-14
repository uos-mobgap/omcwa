"""Core recording and calibration types."""

from __future__ import annotations

from dataclasses import dataclass
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
class RawRecording:
    """CWA samples at the file default rate, with device/session metadata."""

    time: npt.NDArray[np.float64]
    acc: npt.NDArray[np.float64]
    gyr: npt.NDArray[np.float64] | None
    temp: npt.NDArray[np.float64] | None
    metadata: dict[str, Any]
    path: str | None = None

    def slice(
        self, start: float | None = None, stop: float | None = None
    ) -> RawRecording:
        """Return samples satisfying ``start <= time < stop``."""
        from omcwa.slice import slice_recording

        sliced = slice_recording(self, start=start, stop=stop)
        if not isinstance(sliced, RawRecording):
            msg = "slice_recording returned unexpected type for RawRecording"
            raise TypeError(msg)
        return sliced


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


def source_path(recording: RawRecording | CalibratedRecording) -> str:
    """Return the on-disk CWA path required by native omconvert backends."""
    if recording.path:
        return str(recording.path)
    if "source_path" in recording.metadata:
        return str(recording.metadata["source_path"])
    msg = "Recording has no source_path. Cannot run native omconvert backend."
    raise ValueError(msg)


def ensure_path_str(path: str | Path) -> str:
    """Normalise a filesystem path to a string."""
    return str(Path(path))
