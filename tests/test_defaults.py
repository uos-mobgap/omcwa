"""Default synchronisation and native option-forwarding tests."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from omcwa import CalibrationError, _native, load_cwa, process_cwa
from omcwa.defaults import (
    DEFAULT_CALIBRATE,
    DEFAULT_INTERPOLATE,
    DEFAULT_SAMPLE_RATE_HZ,
    DEFAULT_STATIONARY_TIME,
    USE_FILE_SAMPLE_RATE,
    InterpolateMode,
)

_CPP_DEFAULTS = (
    Path(__file__).resolve().parents[1] / "native" / "omcwa_defaults.h"
)


def _cpp_constexpr(name: str) -> str:
    text = _CPP_DEFAULTS.read_text(encoding="utf-8")
    match = re.search(
        # regex for "constexpr <type> <name> = <value>;"
        rf"constexpr\s+\w+\s+{re.escape(name)}\s*=\s*([^;]+);",
        text,
    )
    assert match is not None, f"{name} missing from {_CPP_DEFAULTS}"
    return match.group(1).strip()


def _cpp_int(name: str) -> int:
    # resolve constexpr aliases such as kDefaultInterpolate = kInterpolateCubic
    value = _cpp_constexpr(name)
    if re.fullmatch(r"-?\d+", value):
        return int(value)

    return _cpp_int(value)


def _cpp_float(name: str) -> float:
    value = _cpp_constexpr(name)
    try:
        return float(value)
    except ValueError:
        return _cpp_float(value)


def _calibration(error_code: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        scale=np.ones(3, dtype=np.float64),
        offset=np.zeros(3, dtype=np.float64),
        temp_offset=np.zeros(3, dtype=np.float64),
        reference_temperature=0.0,
        error_code=error_code,
        success=error_code == 0,
        num_axes=0,
        num_stationary_points=0,
        axis_min=np.zeros(3, dtype=np.float64),
        axis_max=np.zeros(3, dtype=np.float64),
        mean_svm_error=0.0,
    )


class _FakeLoaded:
    """Stub LoadedCwa that records native API calls"""

    def __init__(self, calls: dict[str, list[Any]], error_code: int = 0):
        self.calls = calls
        self.error_code = error_code

    def metadata(self) -> dict[str, Any]:
        self.calls["metadata"].append(None)
        return {
            "device_id": 17,
            "session_id": 23,
            "default_rate": 100.0,
        }

    def auto_calibrate(self, **kwargs: Any) -> SimpleNamespace:
        self.calls["auto_calibrate"].append(kwargs)
        return _calibration(self.error_code)

    def resample(
        self,
        calibration: SimpleNamespace,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.calls["resample"].append((calibration, kwargs))
        requested_rate = float(kwargs["sample_rate_hz"])
        output_rate = requested_rate if requested_rate > 0 else 100.0
        return {
            "sample_rate_hz": output_rate,
            "start_time": 1.0,
            "time": np.array([1.0, 1.0 + 1.0 / output_rate]),
            "acc": np.zeros((2, 3), dtype=np.float64),
            "gyr": np.ones((2, 3), dtype=np.float64),
            "temp": np.full(2, 20.0),
            "valid": np.ones(2, dtype=np.bool_),
            "clipped": np.zeros(2, dtype=np.bool_),
        }


def _native_spy(
    monkeypatch: pytest.MonkeyPatch,
    *,
    error_code: int = 0,
) -> dict[str, list[Any]]:
    """Spy on the native API calls made by process_cwa."""
    calls: dict[str, list[Any]] = {
        "load": [],
        "metadata": [],
        "auto_calibrate": [],
        "resample": [],
        "identity": [],
    }
    loaded = _FakeLoaded(calls, error_code)

    def load(path: str) -> _FakeLoaded:
        calls["load"].append(path)
        return loaded

    def identity() -> SimpleNamespace:
        calls["identity"].append(None)
        return _calibration()

    monkeypatch.setattr(
        _native,
        "LoadedCwa",
        SimpleNamespace(load=load),
    )
    monkeypatch.setattr(_native, "identity_calibration", identity)
    return calls


def test_default_constants() -> None:
    assert DEFAULT_SAMPLE_RATE_HZ == USE_FILE_SAMPLE_RATE == 0.0
    assert DEFAULT_INTERPOLATE == InterpolateMode.CUBIC
    assert int(DEFAULT_INTERPOLATE) == 3
    assert DEFAULT_STATIONARY_TIME == 10.0
    assert DEFAULT_CALIBRATE is True


def test_python_defaults_match_cpp_header() -> None:
    assert _cpp_float("kDefaultSampleRateHz") == DEFAULT_SAMPLE_RATE_HZ
    assert _cpp_float("kUseFileSampleRate") == USE_FILE_SAMPLE_RATE
    assert _cpp_int("kInterpolateNearest") == InterpolateMode.NEAREST
    assert _cpp_int("kInterpolateLinear") == InterpolateMode.LINEAR
    assert _cpp_int("kInterpolateCubic") == InterpolateMode.CUBIC
    assert _cpp_int("kDefaultInterpolate") == int(DEFAULT_INTERPOLATE)
    assert _cpp_float("kDefaultStationaryTime") == DEFAULT_STATIONARY_TIME
    assert _cpp_constexpr("kDefaultCalibrate") == "true"


def test_process_forwards_defaults_and_loads_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _native_spy(monkeypatch)

    out = process_cwa("recording.cwa")

    assert calls["load"] == ["recording.cwa"]
    assert calls["auto_calibrate"] == [
        {
            "sample_rate_hz": DEFAULT_SAMPLE_RATE_HZ,
            "interpolate": int(DEFAULT_INTERPOLATE),
            "stationary_time": DEFAULT_STATIONARY_TIME,
        }
    ]
    assert len(calls["resample"]) == 1
    _, resample_options = calls["resample"][0]
    assert resample_options == {
        "sample_rate_hz": DEFAULT_SAMPLE_RATE_HZ,
        "interpolate": int(DEFAULT_INTERPOLATE),
        # ProcessedRecording drops temperature and derives time, so neither
        # is ever allocated.
        "with_temp": False,
        "with_time": False,
    }
    assert calls["identity"] == []
    assert out.sample_rate_hz == 100.0
    assert out.metadata == {
        "device_id": 17,
        "session_id": 23,
        "default_rate": 100.0,
        "sample_rate_hz": 100.0,
    }


def test_process_forwards_explicit_primitive_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _native_spy(monkeypatch)

    out = process_cwa(
        "recording.cwa",
        sample_rate_hz=50.0,
        calibrate=False,
        interpolate=InterpolateMode.LINEAR,
        stationary_time=4.0,
    )

    assert calls["load"] == ["recording.cwa"]
    assert calls["auto_calibrate"] == []
    assert calls["identity"] == [None]
    assert len(calls["resample"]) == 1
    _, options = calls["resample"][0]
    assert options == {
        "sample_rate_hz": 50.0,
        "interpolate": int(InterpolateMode.LINEAR),
        "with_temp": False,
        "with_time": False,
    }
    assert out.sample_rate_hz == 50.0
    assert out.calibration.success is True


def test_strict_calibration_failure_precedes_resample(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _native_spy(monkeypatch, error_code=-2)

    with pytest.raises(CalibrationError, match="error code -2") as error:
        process_cwa("recording.cwa")

    assert error.value.error_code == -2
    assert calls["load"] == ["recording.cwa"]
    assert len(calls["auto_calibrate"]) == 1
    assert calls["resample"] == []
    assert calls["metadata"] == []


def test_load_cwa_uses_identity_at_file_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _native_spy(monkeypatch)

    recording = load_cwa("recording.cwa")

    assert calls["load"] == ["recording.cwa"]
    assert calls["identity"] == [None]
    assert calls["auto_calibrate"] == []
    assert len(calls["resample"]) == 1
    _, options = calls["resample"][0]
    assert options == {
        "sample_rate_hz": USE_FILE_SAMPLE_RATE,
        "interpolate": int(DEFAULT_INTERPOLATE),
        "with_time": False,
    }
    assert recording.acc.shape == (2, 3)
    assert recording.gyr is not None
    assert recording.temp.shape == (2,)
    assert recording.path == "recording.cwa"
