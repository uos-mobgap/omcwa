"""Type stub for the pybind11 extension built from ``native/bridge.cpp``.

Names here are checked against the compiled module by
``tests/test_native_stub.py``.
"""

from typing import Any

import numpy as np
import numpy.typing as npt

class Calibration:
    """Calibration parameters from auto-calibrate or the identity fallback."""

    scale: npt.NDArray[np.float64]
    offset: npt.NDArray[np.float64]
    temp_offset: npt.NDArray[np.float64]
    reference_temperature: float
    error_code: int
    num_axes: int
    success: bool
    num_stationary_points: int
    axis_min: npt.NDArray[np.float64]
    axis_max: npt.NDArray[np.float64]
    mean_svm_error: float

class LoadedCwa:
    """In-memory CWA file, freed on destruction."""

    @staticmethod
    def load(path: str) -> LoadedCwa: ...
    def metadata(self) -> dict[str, Any]: ...
    def auto_calibrate(
        self,
        sample_rate_hz: float = ...,
        interpolate: int = ...,
        stationary_time: float = ...,
        calibrate_from_data: bool = ...,
    ) -> Calibration: ...
    def apply_calibration(
        self,
        acc: npt.NDArray[np.floating],
        temp: float | npt.NDArray[np.floating],
        calibration: Calibration,
    ) -> npt.NDArray[np.float64]: ...
    def resample(
        self,
        calibration: Calibration,
        sample_rate_hz: float = ...,
        interpolate: int = ...,
        with_temp: bool = ...,
        with_time: bool = ...,
        as_float32: bool = ...,
    ) -> dict[str, Any]: ...

def identity_calibration() -> Calibration: ...
def process(
    path: str,
    sample_rate_hz: float = ...,
    calibrate: bool = ...,
    interpolate: int = ...,
    stationary_time: float = ...,
    as_float32: bool = ...,
    calibrate_from_data: bool = ...,
) -> dict[str, Any]: ...
def version() -> str: ...
