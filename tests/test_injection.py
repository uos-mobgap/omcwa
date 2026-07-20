"""Tests for injectable calibration and resampling backends."""

from __future__ import annotations

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
from omcwa.defaults import DEFAULT_STATIONARY_TIME, InterpolateMode
from omcwa.types import (
    CalibratedRecording,
    ProcessedRecording,
    UniformRecording,
)

EXPLICIT_SAMPLE_RATE_HZ = 100.0


def test_custom_calibrate_and_resample_invoked(omgui_cwa: Path) -> None:
    """Custom calibrate_fn and resample_fn hooks are called by process_cwa."""
    calls: list[str] = []

    def calibrate_fn(uniform: UniformRecording) -> CalibratedRecording:
        calls.append("calibrate")
        return OmConvertCalibrate()(uniform)

    def resample_fn(calibrated: CalibratedRecording) -> ProcessedRecording:
        calls.append("resample")
        return OmConvertResample(sample_rate_hz=EXPLICIT_SAMPLE_RATE_HZ)(
            calibrated
        )

    process_cwa(
        omgui_cwa,
        sample_rate_hz=EXPLICIT_SAMPLE_RATE_HZ,
        calibrate_fn=calibrate_fn,
        resample_fn=resample_fn,
    )

    assert calls == ["calibrate", "resample"]


def test_custom_hooks_reuse_cwa_handle(
    omgui_cwa: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wrapped OmConvert hooks must load the CWA file once via handle reuse.

    Custom callables force the slow path. Without handle reuse, calibrate and
    resample each reopen the file and LoadedCwa.load runs three times.
    """
    load_count = 0
    original_load = _native.LoadedCwa.load

    def counting_load(path: str) -> object:
        nonlocal load_count
        load_count += 1
        return original_load(path)

    monkeypatch.setattr(_native.LoadedCwa, "load", counting_load)

    def calibrate_fn(uniform: UniformRecording) -> CalibratedRecording:
        return OmConvertCalibrate(stationary_time=10.0)(uniform)

    def resample_fn(calibrated: CalibratedRecording) -> ProcessedRecording:
        return OmConvertResample(sample_rate_hz=EXPLICIT_SAMPLE_RATE_HZ)(
            calibrated
        )

    out = process_cwa(
        omgui_cwa,
        sample_rate_hz=EXPLICIT_SAMPLE_RATE_HZ,
        calibrate_fn=calibrate_fn,
        resample_fn=resample_fn,
    )

    assert load_count == 1
    assert "_cwa_handle" not in out.metadata
    assert "_native_calibration" not in out.metadata


def test_interpolate_mismatch_bypasses_fast_path(
    omgui_cwa: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Disagreeing interpolate uses slow path with one load and valid output.

    Guards documented fallthrough plus apply_to_arrays=False correctness.
    Without this, mismatched backends can hit one-shot process with wrong
    interpolate or reload the file multiple times.
    """
    process_calls: list[dict[str, object]] = []
    original_process = _native.process
    load_count = 0
    original_load = _native.LoadedCwa.load

    def forbid_process(*args: object, **kwargs: object) -> dict[str, object]:
        process_calls.append(dict(kwargs))
        return original_process(*args, **kwargs)

    def counting_load(path: str) -> object:
        nonlocal load_count
        load_count += 1
        return original_load(path)

    monkeypatch.setattr(_native, "process", forbid_process)
    monkeypatch.setattr(_native.LoadedCwa, "load", counting_load)

    calibrate_fn = OmConvertCalibrate(
        interpolate=int(InterpolateMode.LINEAR),
        stationary_time=DEFAULT_STATIONARY_TIME,
    )
    resample_fn = OmConvertResample(
        sample_rate_hz=EXPLICIT_SAMPLE_RATE_HZ,
        interpolate=int(InterpolateMode.CUBIC),
    )

    out = process_cwa(
        omgui_cwa,
        sample_rate_hz=EXPLICIT_SAMPLE_RATE_HZ,
        calibrate_fn=calibrate_fn,
        resample_fn=resample_fn,
    )

    assert process_calls == []
    assert load_count == 1

    uniform = load_cwa(omgui_cwa)
    ref_cal = OmConvertCalibrate(
        interpolate=int(InterpolateMode.LINEAR),
        stationary_time=DEFAULT_STATIONARY_TIME,
    )(uniform)
    expected = OmConvertResample(
        sample_rate_hz=EXPLICIT_SAMPLE_RATE_HZ,
        interpolate=int(InterpolateMode.CUBIC),
    )(ref_cal)

    assert out.sample_rate_hz == pytest.approx(expected.sample_rate_hz)
    np.testing.assert_allclose(out.acc, expected.acc)
    if out.gyr is not None and expected.gyr is not None:
        np.testing.assert_allclose(out.gyr, expected.gyr)
    assert out.calibration is not None
    assert expected.calibration is not None
    assert out.calibration.success == expected.calibration.success
    assert out.calibration.error_code == expected.calibration.error_code
