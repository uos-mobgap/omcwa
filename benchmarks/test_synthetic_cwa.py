"""Tests for the synthetic CWA writer.

The benchmarks are only meaningful if the generated file really is a CWA
recording with the contents the writer claims. These tests check the container,
the signal, and the calibration behaviour that the benchmarks rely on.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from omcwa import load_cwa, process_cwa
from synthetic_cwa import (
    CYCLE_SECONDS,
    HOLD_SECONDS,
    OFFSET_ERROR,
    ORIENTATIONS,
    SAMPLE_RATE_HZ,
    SCALE_ERROR,
    START_EPOCH,
    TEMPERATURE_CENTRE_C,
    TEMPERATURE_SWING_C,
    RecordingSpec,
    write_cwa,
)

# two full signal cycles, which is every orientation held twice
TEST_HOURS = 2 * CYCLE_SECONDS / 3600

# omconvert stores one temperature reading per sector and cannot interpolate it
# past the final sector, so the last fraction of a second has no temperature.
# See the known limitations section of benchmarks/README.md
TEMPERATURE_TAIL_SAMPLES = SAMPLE_RATE_HZ


@pytest.fixture(scope="module", params=("AX3", "AX6"))
def written(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> tuple[RecordingSpec, Path]:
    """A written recording for each supported device."""
    spec = RecordingSpec(hours=TEST_HOURS, device=request.param)
    path = tmp_path_factory.mktemp("synthetic") / spec.filename
    write_cwa(spec, path)

    return spec, path


def test_file_size_matches_the_spec(
    written: tuple[RecordingSpec, Path],
) -> None:
    spec, path = written
    assert path.stat().st_size == spec.byte_count


@pytest.mark.parametrize("device", ("AX3", "AX6"))
def test_writing_is_deterministic(device: str, tmp_path: Path) -> None:
    """The same spec must produce the same bytes, so files can be cached."""
    spec = RecordingSpec(hours=TEST_HOURS, device=device)
    digests = [
        hashlib.sha256(write_cwa(spec, tmp_path / name).read_bytes()).digest()
        for name in ("first.cwa", "second.cwa")
    ]
    assert digests[0] == digests[1]


def test_recording_loads_with_the_expected_shape(
    written: tuple[RecordingSpec, Path],
) -> None:
    spec, path = written
    recording = load_cwa(path)

    assert recording.metadata["sample_rate_hz"] == float(SAMPLE_RATE_HZ)
    assert recording.time.shape == (spec.sample_count,)
    assert recording.acc.shape == (spec.sample_count, 3)

    if spec.device == "AX6":
        assert recording.gyr is not None
        assert recording.gyr.shape == (spec.sample_count, 3)
    else:
        assert recording.gyr is None


def test_samples_are_evenly_spaced_from_a_known_start(
    written: tuple[RecordingSpec, Path],
) -> None:
    spec, path = written
    recording = load_cwa(path)
    step = 1.0 / SAMPLE_RATE_HZ

    assert recording.time[0] == pytest.approx(START_EPOCH, abs=1e-6)
    assert recording.time[-1] == pytest.approx(
        START_EPOCH + spec.duration_s - step, abs=1e-3
    )
    assert np.diff(recording.time) == pytest.approx(step, abs=1e-6)


def test_values_stay_inside_the_sensor_ranges(
    written: tuple[RecordingSpec, Path],
) -> None:
    """Values must not saturate, or the 16 bit payload would wrap around."""
    _, path = written
    recording = load_cwa(path)

    assert np.abs(recording.acc).max() < 8.0

    if recording.gyr is not None:
        assert np.abs(recording.gyr).max() < 2000.0


def test_stationary_holds_are_still_and_upright(
    written: tuple[RecordingSpec, Path],
) -> None:
    """Each hold must read as one g of gravity once calibration is applied."""
    _, path = written
    recording = process_cwa(path)

    for hold in range(len(ORIENTATIONS)):
        # take the middle of the hold, clear of the transitions at either end
        start = (hold * HOLD_SECONDS + 5) * SAMPLE_RATE_HZ
        window = recording.acc[start : start + 10 * SAMPLE_RATE_HZ]
        assert np.linalg.norm(window, axis=1) == pytest.approx(1.0, abs=0.01)


def test_auto_calibration_recovers_the_injected_error(
    written: tuple[RecordingSpec, Path],
) -> None:
    """The writer stores a known error, so the fit has a known answer.

    omconvert applies calibration as ``(value + offset) * scale``, so the
    recovered scale is the inverse of the written one.
    """
    _, path = written
    recording = process_cwa(path)

    assert recording.calibration.success
    assert recording.calibration.error_code == 0
    assert recording.calibration.scale == pytest.approx(
        1.0 / SCALE_ERROR, abs=0.005
    )
    assert recording.calibration.offset == pytest.approx(
        -OFFSET_ERROR, abs=0.005
    )


def test_temperature_follows_the_written_sweep(
    written: tuple[RecordingSpec, Path],
) -> None:
    _, path = written
    body = load_cwa(path).temp[:-TEMPERATURE_TAIL_SAMPLES]

    assert body.min() == pytest.approx(
        TEMPERATURE_CENTRE_C - TEMPERATURE_SWING_C, abs=0.2
    )
    assert body.max() == pytest.approx(
        TEMPERATURE_CENTRE_C + TEMPERATURE_SWING_C, abs=0.2
    )
