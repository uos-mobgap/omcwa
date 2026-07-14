"""Shared pipeline defaults.

Keep values in sync with ``native/omcwa_defaults.h``.
"""

from enum import IntEnum


class InterpolateMode(IntEnum):
    """Interpolation modes used by omconvert / omgui."""

    NEAREST = 1
    LINEAR = 2
    CUBIC = 3


# omconvert convention: ``sample_rate_hz <= 0`` selects
# ``arrangement.defaultRate``.
USE_FILE_SAMPLE_RATE = 0.0

# Default ``process_cwa`` / omgui form: auto rate (no explicit resample).
DEFAULT_SAMPLE_RATE_HZ = USE_FILE_SAMPLE_RATE
DEFAULT_INTERPOLATE = InterpolateMode.CUBIC
DEFAULT_STATIONARY_TIME = 10.0
DEFAULT_CALIBRATE = True
