"""Shared pipeline defaults and the option types they range over.

Keep values in sync with ``native/omcwa_defaults.h``.
"""

from enum import IntEnum
from typing import Final, Literal

CalibrationFailurePolicy = Literal["raise", "identity"]
CalibrationSource = Literal["data", "player"]
Dtype = Literal["float64", "float32"]


class InterpolateMode(IntEnum):
    """Interpolation modes used by omconvert / omgui."""

    NEAREST = 1
    LINEAR = 2
    CUBIC = 3


# omconvert convention: ``sample_rate_hz <= 0`` selects
# ``arrangement.defaultRate``.
USE_FILE_SAMPLE_RATE: Final[float] = 0.0

# Default process_cwa / omgui: sample_rate_hz=0, no explicit resample.
DEFAULT_SAMPLE_RATE_HZ: Final[float] = USE_FILE_SAMPLE_RATE
DEFAULT_INTERPOLATE: Final[InterpolateMode] = InterpolateMode.CUBIC
DEFAULT_STATIONARY_TIME: Final[float] = 10.0
DEFAULT_CALIBRATE: Final[bool] = True
# Direct CWA sectors avoid a full interpolating-player pass during AX6
# calibration. The player remains available as a compatibility option.
DEFAULT_CALIBRATION_SOURCE: Final[CalibrationSource] = "data"

# float64 output matches every consumer today. float32 halves acc/gyr, but
# needs verification downstream before it becomes the default.
DEFAULT_DTYPE: Final[Dtype] = "float64"
