"""omcwa: CWA load, calibrate, and resample."""

__version__ = "0.1.1"

from omcwa.defaults import (
    DEFAULT_CALIBRATE,
    DEFAULT_CALIBRATION_SOURCE,
    DEFAULT_INTERPOLATE,
    DEFAULT_SAMPLE_RATE_HZ,
    DEFAULT_STATIONARY_TIME,
    USE_FILE_SAMPLE_RATE,
    CalibrationFailurePolicy,
    CalibrationSource,
    Dtype,
    InterpolateMode,
)
from omcwa.process import CalibrationError, load_cwa, process_cwa
from omcwa.slice import slice_recording
from omcwa.types import (
    Calibration,
    ProcessedRecording,
    UniformRecording,
)

__all__ = [
    "__version__",
    "load_cwa",
    "process_cwa",
    "slice_recording",
    "CalibrationError",
    "Calibration",
    "UniformRecording",
    "ProcessedRecording",
    "CalibrationFailurePolicy",
    "CalibrationSource",
    "Dtype",
    "InterpolateMode",
    "DEFAULT_SAMPLE_RATE_HZ",
    "DEFAULT_INTERPOLATE",
    "DEFAULT_STATIONARY_TIME",
    "DEFAULT_CALIBRATE",
    "DEFAULT_CALIBRATION_SOURCE",
    "USE_FILE_SAMPLE_RATE",
]
