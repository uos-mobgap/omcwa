"""The package root is the public API.

``__all__`` is the list of names a user may import from ``omcwa``. These
tests hold it to itself: every name on it resolves, and the list matches the
one pinned below. That the documentation promises the same names is checked
by review, not here. See ``docs/adr/0005-documentation-parity-is-reviewed``.
"""

from __future__ import annotations

import omcwa

# Adding a name to the public API means adding it here too, so a new export
# lands as a deliberate edit rather than a surprise.
EXPORTED_NAMES = frozenset(
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


def test_all_lists_the_exported_names() -> None:
    assert set(omcwa.__all__) == EXPORTED_NAMES


def test_all_has_no_duplicates() -> None:
    assert len(omcwa.__all__) == len(set(omcwa.__all__))


def test_every_listed_name_is_exported() -> None:
    """``from omcwa import *`` would fail on a name that is only listed."""
    assert [name for name in omcwa.__all__ if not hasattr(omcwa, name)] == []
