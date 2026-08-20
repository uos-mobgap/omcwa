"""Golden-oracle tests for the fixed process_cwa pipeline.

Uses committed synthetic CWAs under tests/fixtures/golden/. Provenance and
regeneration: tests/fixtures/README.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from omcwa import CalibrationError, load_cwa, process_cwa
from omcwa.defaults import InterpolateMode

# LSB tolerances from omconvert WAV contract:
# physical = int16 * (2 * Scale-N) / 65536
# ref: native/vendored/omconvert/omdata.c
TARGET_RATE_HZ = 100.0
ACCEL_LSB_G = 16.0 / 65536.0
GYRO_LSB_DPS = 4000.0 / 65536.0
CALIBRATION_TOLERANCE = 1e-4


def _load_output_golden(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as golden:
        return {name: golden[name] for name in golden.files}


def _assert_output_matches_golden(
    actual_acc: np.ndarray,
    actual_gyr: np.ndarray | None,
    golden: dict[str, np.ndarray],
) -> None:
    """LSB-based comparison of processed output with golden oracles."""
    assert actual_gyr is not None
    assert actual_acc.shape == golden["accel"].shape
    assert actual_gyr.shape == golden["gyro"].shape
    np.testing.assert_allclose(
        actual_acc,
        golden["accel"],
        atol=ACCEL_LSB_G,
        rtol=0.0,
    )
    np.testing.assert_allclose(
        actual_gyr,
        golden["gyro"],
        atol=GYRO_LSB_DPS,
        rtol=0.0,
    )


def test_calibrate_false_matches_resample_golden(
    resample_only_cwa: Path,
    golden_dir: Path,
) -> None:
    golden = _load_output_golden(golden_dir / "resample_only.golden.npz")

    out = process_cwa(
        resample_only_cwa,
        sample_rate_hz=TARGET_RATE_HZ,
        calibrate=False,
    )

    assert out.sample_rate_hz == float(golden["output_rate"])
    assert out.acc.shape[0] == int(golden["output_samples"])
    _assert_output_matches_golden(out.acc, out.gyr, golden)
    assert out.calibration.success is True
    assert out.calibration.error_code == 0
    np.testing.assert_array_equal(out.calibration.scale, np.ones(3))
    np.testing.assert_array_equal(out.calibration.offset, np.zeros(3))


def test_successful_calibration_matches_reference_oracles(
    cal_success_cwa: Path,
    golden_dir: Path,
) -> None:
    calibration_golden = json.loads(
        (golden_dir / "cal_success.golden.json").read_text(encoding="utf-8")
    )
    output_golden = _load_output_golden(golden_dir / "cal_success.golden.npz")

    out = process_cwa(
        cal_success_cwa,
        sample_rate_hz=TARGET_RATE_HZ,
        calibration_source="player",
    )

    calibration = out.calibration
    assert calibration.success is True
    assert calibration.error_code == calibration_golden["error_code"] == 0
    for field in ("scale", "offset", "temp_offset"):
        np.testing.assert_allclose(
            getattr(calibration, field),
            calibration_golden[field],
            atol=CALIBRATION_TOLERANCE,
            rtol=0.0,
        )
    assert calibration.ref_temp == pytest.approx(
        calibration_golden["reference_temperature"],
        abs=CALIBRATION_TOLERANCE,
    )
    _assert_output_matches_golden(out.acc, out.gyr, output_golden)


def test_ax6_data_calibration_stays_close_to_player(
    cal_success_cwa: Path,
) -> None:
    data = process_cwa(
        cal_success_cwa,
        sample_rate_hz=TARGET_RATE_HZ,
    )
    player = process_cwa(
        cal_success_cwa,
        sample_rate_hz=TARGET_RATE_HZ,
        calibration_source="player",
    )

    assert data.calibration.success is True
    assert (
        data.calibration.num_stationary_points
        == player.calibration.num_stationary_points
    )
    for field in ("scale", "offset", "temp_offset"):
        np.testing.assert_allclose(
            getattr(data.calibration, field),
            getattr(player.calibration, field),
            atol=CALIBRATION_TOLERANCE,
            rtol=0.0,
        )
    np.testing.assert_allclose(
        data.acc,
        player.acc,
        atol=ACCEL_LSB_G,
        rtol=0.0,
    )
    np.testing.assert_allclose(
        data.gyr,
        player.gyr,
        atol=GYRO_LSB_DPS,
        rtol=0.0,
    )


@pytest.mark.parametrize(
    ("fixture_name", "error_code"),
    [
        ("cal_failure.cwa", -1),
        ("cal_failure_no_axis.cwa", -2),
    ],
)
def test_calibration_failures_raise_by_default(
    golden_dir: Path,
    fixture_name: str,
    error_code: int,
) -> None:
    with pytest.raises(
        CalibrationError,
        match=rf"error code {error_code}",
    ) as error:
        process_cwa(
            golden_dir / fixture_name,
            sample_rate_hz=TARGET_RATE_HZ,
        )

    assert error.value.error_code == error_code


@pytest.mark.parametrize(
    ("fixture_name", "error_code"),
    [
        ("cal_failure.cwa", -1),
        ("cal_failure_no_axis.cwa", -2),
    ],
)
def test_explicit_identity_fallback_preserves_failure(
    golden_dir: Path,
    fixture_name: str,
    error_code: int,
) -> None:
    path = golden_dir / fixture_name
    fallback = process_cwa(
        path,
        sample_rate_hz=TARGET_RATE_HZ,
        on_calibration_failure="identity",
    )
    uncalibrated = process_cwa(
        path,
        sample_rate_hz=TARGET_RATE_HZ,
        calibrate=False,
    )

    assert fallback.calibration.success is False
    assert fallback.calibration.error_code == error_code
    np.testing.assert_array_equal(fallback.calibration.scale, np.ones(3))
    np.testing.assert_array_equal(fallback.calibration.offset, np.zeros(3))
    np.testing.assert_allclose(fallback.acc, uncalibrated.acc, rtol=0.0)
    np.testing.assert_allclose(fallback.gyr, uncalibrated.gyr, rtol=0.0)


def test_invalid_calibration_failure_policy_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="on_calibration_failure must be",
    ):
        process_cwa(
            "not-opened.cwa",
            on_calibration_failure="continue",  # type: ignore[arg-type]
        )


def test_file_rate_cubic_defaults_match_explicit_options(
    resample_only_cwa: Path,
) -> None:
    default = process_cwa(resample_only_cwa, calibrate=False)
    explicit = process_cwa(
        resample_only_cwa,
        sample_rate_hz=TARGET_RATE_HZ,
        calibrate=False,
        interpolate=InterpolateMode.CUBIC,
    )

    assert default.sample_rate_hz == TARGET_RATE_HZ
    np.testing.assert_array_equal(default.time, explicit.time)
    np.testing.assert_array_equal(default.acc, explicit.acc)
    np.testing.assert_array_equal(default.gyr, explicit.gyr)


def test_explicit_rate_and_interpolation_shape_output(
    resample_only_cwa: Path,
) -> None:
    out = process_cwa(
        resample_only_cwa,
        sample_rate_hz=50.0,
        calibrate=False,
        interpolate=InterpolateMode.LINEAR,
    )

    assert out.sample_rate_hz == 50.0
    assert out.acc.shape == (250, 3)
    assert out.gyr is not None
    assert out.gyr.shape == (250, 3)
    np.testing.assert_allclose(
        np.diff(out.time),
        1.0 / 50.0,
        atol=3e-7,
        rtol=0.0,
    )


def test_output_types_units_flags_and_public_metadata(
    resample_only_cwa: Path,
) -> None:
    out = process_cwa(resample_only_cwa, calibrate=False)

    assert out.time.dtype == np.float64
    assert out.acc.dtype == np.float64
    assert out.gyr is not None
    assert out.gyr.dtype == np.float64
    assert out.acc.shape == out.gyr.shape == (500, 3)
    assert np.max(np.abs(out.acc)) < 2.0
    assert np.max(np.abs(out.gyr)) < 25.0
    assert out.valid.dtype == np.bool_
    assert out.valid.shape == (500,)
    assert np.all(out.valid)
    assert out.clipped.dtype == np.bool_
    assert out.clipped.shape == (500,)
    assert not np.any(out.clipped)

    assert out.metadata["device_id"] == 0
    assert out.metadata["session_id"] == 0
    assert out.metadata["default_rate"] == TARGET_RATE_HZ
    assert out.metadata["sample_rate_hz"] == TARGET_RATE_HZ
    assert out.metadata["has_accel"] is True
    assert out.metadata["has_gyro"] is True
    assert out.metadata["start_time"] == pytest.approx(out.time[0])
    assert all(not key.startswith("_") for key in out.metadata)


def test_load_cwa_preserves_temperature_and_path(
    resample_only_cwa: Path,
) -> None:
    uniform = load_cwa(resample_only_cwa)

    assert uniform.path == str(resample_only_cwa)
    assert uniform.acc.shape == (500, 3)
    assert uniform.gyr is not None
    assert uniform.gyr.shape == (500, 3)
    assert uniform.temp.shape == (500,)
    assert uniform.temp.dtype == np.float64
    assert uniform.metadata["sample_rate_hz"] == TARGET_RATE_HZ
    assert all(not key.startswith("_") for key in uniform.metadata)


def test_load_cwa_float32_matches_float64_within_one_ulp(
    resample_only_cwa: Path,
) -> None:
    f64 = load_cwa(resample_only_cwa, dtype="float64")
    f32 = load_cwa(resample_only_cwa, dtype="float32")

    assert f64.acc.dtype == np.float64
    assert f32.acc.dtype == np.float32
    assert f32.gyr is not None
    assert f32.gyr.dtype == np.float32
    assert f32.temp.dtype == np.float64

    ulp = np.finfo(np.float32).eps
    np.testing.assert_allclose(f32.acc, f64.acc, rtol=ulp, atol=ulp)
    np.testing.assert_allclose(f32.gyr, f64.gyr, rtol=ulp, atol=ulp)
    assert f32.time.dtype == np.float64
    np.testing.assert_array_equal(f32.time, f64.time)


def test_float32_output_matches_float64_within_one_ulp(
    cal_success_cwa: Path,
) -> None:
    """See docs/performance-plan.md section 2.3: the real mobgap algorithms
    ran bit identical on float32 vs float64 input except for the two
    integrated outputs, which drifted by exactly one float32 ULP. That is
    the property this test checks at the omcwa boundary, not bit equality.
    """
    f64 = process_cwa(cal_success_cwa, dtype="float64")
    f32 = process_cwa(cal_success_cwa, dtype="float32")

    assert f64.acc.dtype == np.float64
    assert f32.acc.dtype == np.float32
    assert f32.gyr is not None
    assert f32.gyr.dtype == np.float32

    ulp = np.finfo(np.float32).eps
    np.testing.assert_allclose(
        f32.acc,
        f64.acc,
        rtol=ulp,
        atol=ulp,
    )
    np.testing.assert_allclose(
        f32.gyr,
        f64.gyr,
        rtol=ulp,
        atol=ulp,
    )
    # time is never narrowed. Unix-epoch magnitude needs float64 precision.
    assert f32.time.dtype == np.float64
    np.testing.assert_array_equal(f32.time, f64.time)


def test_time_range_is_half_open_post_processing_trim(
    cal_success_cwa: Path,
) -> None:
    full = process_cwa(cal_success_cwa)
    start = float(full.time[125])
    stop = float(full.time[375])
    mask = (full.time >= start) & (full.time < stop)

    window = process_cwa(
        cal_success_cwa,
        time_range=(start, stop),
    )

    np.testing.assert_array_equal(window.time, full.time[mask])
    np.testing.assert_array_equal(window.acc, full.acc[mask])
    np.testing.assert_array_equal(window.gyr, full.gyr[mask])
    np.testing.assert_array_equal(window.valid, full.valid[mask])
    np.testing.assert_array_equal(window.clipped, full.clipped[mask])
    np.testing.assert_array_equal(
        window.calibration.offset,
        full.calibration.offset,
    )
