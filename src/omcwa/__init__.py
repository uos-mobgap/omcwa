"""omcwa: CWA load, calibrate, and resample."""

__version__ = "0.1.0"

from omcwa.calibrate import OmConvertCalibrate
from omcwa.defaults import (
    DEFAULT_CALIBRATE,
    DEFAULT_INTERPOLATE,
    DEFAULT_SAMPLE_RATE_HZ,
    DEFAULT_STATIONARY_TIME,
    USE_FILE_SAMPLE_RATE,
    InterpolateMode,
)
from omcwa.process import load_cwa, process_cwa
from omcwa.resample import OmConvertResample
from omcwa.types import (
    CalibratedRecording,
    CalibrateFn,
    Calibration,
    ProcessedRecording,
    RawRecording,
    ResampleFn,
)

__all__ = [
    "__version__",
    "load_cwa",
    "process_cwa",
    "OmConvertCalibrate",
    "OmConvertResample",
    "CalibrateFn",
    "ResampleFn",
    "Calibration",
    "RawRecording",
    "CalibratedRecording",
    "ProcessedRecording",
    "InterpolateMode",
    "DEFAULT_SAMPLE_RATE_HZ",
    "DEFAULT_INTERPOLATE",
    "DEFAULT_STATIONARY_TIME",
    "DEFAULT_CALIBRATE",
    "USE_FILE_SAMPLE_RATE",
]
