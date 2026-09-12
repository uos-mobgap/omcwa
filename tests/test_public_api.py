"""The package root is the public API.

Everything the README tells a user to import comes from ``omcwa`` itself,
and ``__all__`` is the record of it. A name the documentation promises but
the package never exports fails here, which is how ``slice_recording``
stayed documented and unreachable.
"""

from __future__ import annotations

import omcwa

# Adding a name to the public API means adding it here too. That is the
# point: the surface grows on purpose, not as a side effect of an import.
PUBLIC_NAMES = frozenset(
    {
        "__version__",
        "load_cwa",
        "process_cwa",
        "slice_recording",
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
    }
)


def test_all_lists_the_documented_surface() -> None:
    assert set(omcwa.__all__) == PUBLIC_NAMES


def test_all_has_no_duplicates() -> None:
    assert len(omcwa.__all__) == len(set(omcwa.__all__))


def test_every_listed_name_is_exported() -> None:
    """``from omcwa import *`` would fail on a name that is only listed."""
    missing = [name for name in omcwa.__all__ if not hasattr(omcwa, name)]
    assert missing == []
