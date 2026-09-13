"""``Calibration`` construction.

``Calibration.identity()`` is public API, while every pipeline path takes
the native identity calibration instead. These tests are what keeps the two
from drifting apart.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from numpy.testing import assert_array_equal

from omcwa import Calibration, _native

FIELD_NAMES = [field.name for field in dataclasses.fields(Calibration)]


def test_identity_leaves_acceleration_unchanged() -> None:
    identity = Calibration.identity()

    assert_array_equal(identity.scale, np.ones(3))
    assert_array_equal(identity.offset, np.zeros(3))
    assert_array_equal(identity.temp_offset, np.zeros(3))
    assert identity.ref_temp == 0.0
    assert identity.error_code == 0
    assert identity.success


def test_identity_reports_no_diagnostics() -> None:
    """There are no stationary points behind an identity calibration."""
    identity = Calibration.identity()

    assert identity.num_axes == 0
    assert identity.num_stationary_points == 0
    assert identity.mean_svm_error == 0.0
    assert_array_equal(identity.axis_min, np.zeros(3))
    assert_array_equal(identity.axis_max, np.zeros(3))


@pytest.mark.parametrize("field_name", FIELD_NAMES)
def test_identity_matches_the_native_identity(field_name: str) -> None:
    native = Calibration.from_native(_native.identity_calibration())

    assert_array_equal(
        getattr(Calibration.identity(), field_name),
        getattr(native, field_name),
    )
