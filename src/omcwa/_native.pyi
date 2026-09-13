"""Type stub for the pybind11 extension built from ``native/bridge.cpp``.

Names here are checked against the compiled module by
``tests/test_native_stub.py``.
"""

from typing import Any

import numpy as np
import numpy.typing as npt

class Calibration:
    """Calibration parameters from auto-calibrate or the identity fallback.

    ``bridge.cpp`` exposes every field with ``def_readonly``, so each one
    is a property with no setter.
    """

    @property
    def scale(self) -> npt.NDArray[np.float64]: ...
    @property
    def offset(self) -> npt.NDArray[np.float64]: ...
    @property
    def temp_offset(self) -> npt.NDArray[np.float64]: ...
    @property
    def reference_temperature(self) -> float: ...
    @property
    def error_code(self) -> int: ...
    @property
    def num_axes(self) -> int: ...
    @property
    def success(self) -> bool: ...
    @property
    def num_stationary_points(self) -> int: ...
    @property
    def axis_min(self) -> npt.NDArray[np.float64]: ...
    @property
    def axis_max(self) -> npt.NDArray[np.float64]: ...
    @property
    def mean_svm_error(self) -> float: ...

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
