"""omcwa: CWA load, calibrate, and resample."""

__version__ = "0.1.0"

from omcwa.defaults import (
    DEFAULT_CALIBRATE,
    DEFAULT_CALIBRATION_SOURCE,
    DEFAULT_INTERPOLATE,
    DEFAULT_SAMPLE_RATE_HZ,
    DEFAULT_STATIONARY_TIME,
    USE_FILE_SAMPLE_RATE,
    InterpolateMode,
)
from omcwa.process import CalibrationError, load_cwa, process_cwa
from omcwa.types import (
    Calibration,
    ProcessedRecording,
    UniformRecording,
)

__all__ = [
    "__version__",
    "load_cwa",
    "process_cwa",
    "CalibrationError",
    "Calibration",
    "UniformRecording",
    "ProcessedRecording",
    "InterpolateMode",
    "DEFAULT_SAMPLE_RATE_HZ",
    "DEFAULT_INTERPOLATE",
    "DEFAULT_STATIONARY_TIME",
    "DEFAULT_CALIBRATE",
    "DEFAULT_CALIBRATION_SOURCE",
    "USE_FILE_SAMPLE_RATE",
]
