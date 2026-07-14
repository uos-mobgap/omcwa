"""Tests for centralized pipeline defaults."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from omcwa import OmConvertCalibrate, OmConvertResample, load_cwa, process_cwa
from omcwa.defaults import (
    DEFAULT_CALIBRATE,
    DEFAULT_INTERPOLATE,
    DEFAULT_SAMPLE_RATE_HZ,
    DEFAULT_STATIONARY_TIME,
    USE_FILE_SAMPLE_RATE,
    InterpolateMode,
)
from omcwa.process import _is_default_calibrate
from omcwa.types import CalibratedRecording, ProcessedRecording, RawRecording

_CPP_DEFAULTS = (
    Path(__file__).resolve().parents[1] / "native" / "omcwa_defaults.h"
)


def _cpp_constexpr(name: str) -> str:
    text = _CPP_DEFAULTS.read_text(encoding="utf-8")
    match = re.search(
        rf"constexpr\s+\w+\s+{re.escape(name)}\s*=\s*([^;]+);", text
    )
    assert match is not None, f"{name} missing from {_CPP_DEFAULTS}"
    return match.group(1).strip()


def _cpp_int(name: str) -> int:
    value = _cpp_constexpr(name)
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    # Resolve aliases such as kDefaultInterpolate = kInterpolateCubic
    return _cpp_int(value)


def _cpp_float(name: str) -> float:
    value = _cpp_constexpr(name)
    try:
        return float(value)
    except ValueError:
        return _cpp_float(value)


def test_interpolate_mode_values() -> None:
    """InterpolateMode matches omconvert / omgui numbering."""
    assert InterpolateMode.NEAREST == 1
    assert InterpolateMode.LINEAR == 2
    assert InterpolateMode.CUBIC == 3
    assert DEFAULT_INTERPOLATE == InterpolateMode.CUBIC


def test_default_constants() -> None:
    """DEFAULT_* constants match omgui defaults."""
    assert DEFAULT_SAMPLE_RATE_HZ == USE_FILE_SAMPLE_RATE
    assert int(DEFAULT_INTERPOLATE) == 3
    assert DEFAULT_STATIONARY_TIME == 10.0
    assert USE_FILE_SAMPLE_RATE == 0.0
    assert DEFAULT_CALIBRATE is True


def test_python_defaults_match_cpp_header() -> None:
    """Python defaults stay in sync with native/omcwa_defaults.h."""
    assert _cpp_float("kDefaultSampleRateHz") == DEFAULT_SAMPLE_RATE_HZ
    assert _cpp_float("kUseFileSampleRate") == USE_FILE_SAMPLE_RATE
    assert _cpp_int("kInterpolateNearest") == InterpolateMode.NEAREST
    assert _cpp_int("kInterpolateLinear") == InterpolateMode.LINEAR
    assert _cpp_int("kInterpolateCubic") == InterpolateMode.CUBIC
    assert _cpp_int("kDefaultInterpolate") == int(DEFAULT_INTERPOLATE)
    assert _cpp_float("kDefaultStationaryTime") == DEFAULT_STATIONARY_TIME
    assert _cpp_constexpr("kDefaultCalibrate") == "true"


def test_backend_constructors_use_defaults() -> None:
    """Default OmConvertCalibrate and OmConvertResample use shared defaults."""
    calibrate = OmConvertCalibrate()
    assert calibrate.sample_rate_hz == USE_FILE_SAMPLE_RATE
    assert calibrate.interpolate == int(DEFAULT_INTERPOLATE)
    assert calibrate.stationary_time == DEFAULT_STATIONARY_TIME

    resample = OmConvertResample()
    assert resample.sample_rate_hz == USE_FILE_SAMPLE_RATE
    assert resample.interpolate == int(DEFAULT_INTERPOLATE)


def test_is_default_calibrate() -> None:
    """Default OmConvertCalibrate is recognized for the fast path."""
    assert _is_default_calibrate(OmConvertCalibrate()) is True


def test_process_cwa_default_fast_path(omgui_cwa: Path) -> None:
    """Default process_cwa uses the fast path without AttributeError."""
    raw = load_cwa(omgui_cwa)
    expected_rate = float(raw.metadata["sample_rate_hz"])
    out = process_cwa(omgui_cwa)
    assert out.sample_rate_hz == pytest.approx(expected_rate)


def test_default_fast_and_slow_paths_agree(omgui_cwa: Path) -> None:
    """Default fast and injectable slow paths produce identical output."""
    fast = process_cwa(omgui_cwa)

    def calibrate_fn(raw: RawRecording) -> CalibratedRecording:
        return OmConvertCalibrate()(raw)

    def resample_fn(calibrated: CalibratedRecording) -> ProcessedRecording:
        return OmConvertResample()(calibrated)

    slow = process_cwa(
        omgui_cwa,
        calibrate_fn=calibrate_fn,
        resample_fn=resample_fn,
    )

    assert slow.sample_rate_hz == pytest.approx(fast.sample_rate_hz)
    np.testing.assert_allclose(slow.acc, fast.acc)
    if fast.gyr is not None and slow.gyr is not None:
        np.testing.assert_allclose(slow.gyr, fast.gyr)
    assert slow.calibration is not None
    assert fast.calibration is not None
    assert slow.calibration.success == fast.calibration.success
    assert slow.calibration.error_code == fast.calibration.error_code
