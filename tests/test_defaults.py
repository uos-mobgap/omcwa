"""Tests for centralized pipeline defaults."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from omcwa import (
    OmConvertCalibrate,
    OmConvertResample,
    _native,
    load_cwa,
    process_cwa,
)
from omcwa.defaults import (
    DEFAULT_CALIBRATE,
    DEFAULT_INTERPOLATE,
    DEFAULT_SAMPLE_RATE_HZ,
    DEFAULT_STATIONARY_TIME,
    USE_FILE_SAMPLE_RATE,
    InterpolateMode,
)
from omcwa.resample import processed_from_native
from omcwa.types import (
    CalibratedRecording,
    ProcessedRecording,
    UniformRecording,
)

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


def test_process_cwa_default_fast_path(omgui_cwa: Path) -> None:
    """Default process_cwa uses the fast path without AttributeError."""
    uniform = load_cwa(omgui_cwa)
    expected_rate = float(uniform.metadata["sample_rate_hz"])
    out = process_cwa(omgui_cwa)
    assert out.sample_rate_hz == pytest.approx(expected_rate)


def test_nondefault_omconvert_uses_fast_path(
    omgui_cwa: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-default OmConvert params must hit one-shot native process.

    Guards the widened fast path. Without this, non-default OmConvertCalibrate
    or OmConvertResample settings can silently fall back to the slow path
    again.
    """
    process_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    original_process = _native.process

    def spy_process(*args: object, **kwargs: object) -> dict[str, object]:
        process_calls.append((args, kwargs))
        return original_process(*args, **kwargs)

    monkeypatch.setattr(_native, "process", spy_process)

    stationary_time = 15.0
    rate = 100.0
    calibrate_fn = OmConvertCalibrate(stationary_time=stationary_time)
    resample_fn = OmConvertResample(sample_rate_hz=rate)

    out = process_cwa(
        omgui_cwa,
        calibrate_fn=calibrate_fn,
        resample_fn=resample_fn,
    )

    assert len(process_calls) == 1
    _, kwargs = process_calls[0]
    assert kwargs["sample_rate_hz"] == rate
    assert kwargs["calibrate"] is True
    assert kwargs["stationary_time"] == stationary_time

    path_str = str(omgui_cwa)
    ref = _native.process(
        path_str,
        sample_rate_hz=rate,
        calibrate=True,
        interpolate=int(DEFAULT_INTERPOLATE),
        stationary_time=stationary_time,
    )
    expected = processed_from_native(ref)

    assert out.sample_rate_hz == pytest.approx(expected.sample_rate_hz)
    np.testing.assert_allclose(out.acc, expected.acc)
    if out.gyr is not None and expected.gyr is not None:
        np.testing.assert_allclose(out.gyr, expected.gyr)
    assert out.calibration is not None
    assert expected.calibration is not None
    assert out.calibration.success == expected.calibration.success
    assert out.calibration.error_code == expected.calibration.error_code


def _assert_processed_matches(
    out: ProcessedRecording,
    expected: ProcessedRecording,
) -> None:
    assert out.sample_rate_hz == pytest.approx(expected.sample_rate_hz)
    np.testing.assert_allclose(out.acc, expected.acc)
    if out.gyr is not None and expected.gyr is not None:
        np.testing.assert_allclose(out.gyr, expected.gyr)
    assert out.calibration is not None
    assert expected.calibration is not None
    assert out.calibration.success == expected.calibration.success
    assert out.calibration.error_code == expected.calibration.error_code


def test_skip_calibration_uses_fast_path(
    omgui_cwa: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """calibrate_fn=None must hit native process with calibrate=False.

    Guards the skip-auto-cal fast-path branch. A wiring bug can silently run
    identity materialize instead of one-shot process.
    """
    process_calls: list[dict[str, object]] = []
    original_process = _native.process

    def spy_process(*args: object, **kwargs: object) -> dict[str, object]:
        process_calls.append(dict(kwargs))
        return original_process(*args, **kwargs)

    monkeypatch.setattr(_native, "process", spy_process)

    rate = 100.0
    out = process_cwa(
        omgui_cwa,
        calibrate_fn=None,
        resample_fn=OmConvertResample(sample_rate_hz=rate),
    )

    assert len(process_calls) == 1
    assert process_calls[0]["calibrate"] is False
    assert process_calls[0]["sample_rate_hz"] == rate

    path_str = str(omgui_cwa)
    ref = _native.process(
        path_str,
        sample_rate_hz=rate,
        calibrate=False,
        interpolate=int(DEFAULT_INTERPOLATE),
        stationary_time=DEFAULT_STATIONARY_TIME,
    )
    expected = processed_from_native(ref)
    _assert_processed_matches(out, expected)


def test_skip_resample_uses_fast_path(
    omgui_cwa: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """resample_fn=None must hit native process at file rate with cal on.

    Guards the calibrate-only fast-path branch (sample_rate_hz=0).
    """
    process_calls: list[dict[str, object]] = []
    original_process = _native.process

    def spy_process(*args: object, **kwargs: object) -> dict[str, object]:
        process_calls.append(dict(kwargs))
        return original_process(*args, **kwargs)

    monkeypatch.setattr(_native, "process", spy_process)

    out = process_cwa(
        omgui_cwa,
        calibrate_fn=OmConvertCalibrate(),
        resample_fn=None,
    )

    assert len(process_calls) == 1
    assert process_calls[0]["calibrate"] is True
    assert process_calls[0]["sample_rate_hz"] == USE_FILE_SAMPLE_RATE

    path_str = str(omgui_cwa)
    ref = _native.process(
        path_str,
        sample_rate_hz=USE_FILE_SAMPLE_RATE,
        calibrate=True,
        interpolate=int(DEFAULT_INTERPOLATE),
        stationary_time=DEFAULT_STATIONARY_TIME,
    )
    expected = processed_from_native(ref)
    _assert_processed_matches(out, expected)


def test_skip_both_stages_materializes_without_process(
    omgui_cwa: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both stages None must materialize once and never call native process.

    Guards the identity-cal file-rate branch. Without this, both-None can
    wrongly invoke process or double-load via the slow path.
    """
    process_calls: list[dict[str, object]] = []

    def forbid_process(*args: object, **kwargs: object) -> dict[str, object]:
        process_calls.append(dict(kwargs))
        msg = "_native.process must not run when both stages are None"
        raise AssertionError(msg)

    monkeypatch.setattr(_native, "process", forbid_process)

    out = process_cwa(omgui_cwa, calibrate_fn=None, resample_fn=None)

    assert process_calls == []

    uniform = load_cwa(omgui_cwa)
    expected_rate = float(uniform.metadata["sample_rate_hz"])
    assert out.sample_rate_hz == pytest.approx(expected_rate)
    np.testing.assert_allclose(out.acc, uniform.acc)
    if out.gyr is not None and uniform.gyr is not None:
        np.testing.assert_allclose(out.gyr, uniform.gyr)
    assert out.calibration is not None
    assert out.calibration.success is True
    assert out.calibration.error_code == 0
    assert "_cwa_handle" not in out.metadata
    assert "_native_calibration" not in out.metadata


def test_default_fast_and_slow_paths_agree(omgui_cwa: Path) -> None:
    """Default fast and injectable slow paths produce identical output."""
    fast = process_cwa(omgui_cwa)

    def calibrate_fn(uniform: UniformRecording) -> CalibratedRecording:
        return OmConvertCalibrate()(uniform)

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
