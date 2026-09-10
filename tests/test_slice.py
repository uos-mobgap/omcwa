"""Branch coverage for time-range slicing.

Follows the model of the time-range test in test_process_parity.py: take a
full recording, compute the expected window with a boolean mask over the
full arrays, and compare every array on the result. Uses the same committed
synthetic CWAs under tests/fixtures/golden/, so it needs no new oracle.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TypeVar

import numpy as np
import pytest

from omcwa import load_cwa, process_cwa
from omcwa.slice import slice_recording
from omcwa.types import ProcessedRecording, UniformRecording

RecordingT = TypeVar("RecordingT", UniformRecording, ProcessedRecording)


@pytest.fixture(scope="module")
def uniform(resample_only_cwa: Path) -> UniformRecording:
    """A uniform recording, which the time_range parameter never produces."""
    return load_cwa(resample_only_cwa)


@pytest.fixture(scope="module")
def processed(cal_success_cwa: Path) -> ProcessedRecording:
    """A processed recording on the start_time/sample_rate_hz grid."""
    return process_cwa(cal_success_cwa)


def _off_the_grid(recording: RecordingT) -> RecordingT:
    """Return the same recording carrying a non-uniform timeline.

    Nothing in the library sets ``time_override`` yet, so this fixture
    reaches the mask path by dropping samples off the grid the way a caller
    would.
    """
    keep = np.arange(recording.n_samples) % 3 != 2
    fields = {
        "n_samples": int(keep.sum()),
        "acc": recording.acc[keep],
        "gyr": None if recording.gyr is None else recording.gyr[keep],
        "time_override": recording.time[keep],
    }
    if isinstance(recording, UniformRecording):
        fields["temp"] = recording.temp[keep]
    else:
        fields["valid"] = recording.valid[keep]
        fields["clipped"] = recording.clipped[keep]

    return replace(recording, **fields)


def _window_bounds(
    recording: UniformRecording | ProcessedRecording,
    first: int,
    last: int,
) -> tuple[float, float, np.ndarray]:
    """Return a half-open bound pair and the mask it selects."""
    start = float(recording.time[first])
    stop = float(recording.time[last])
    return start, stop, (recording.time >= start) & (recording.time < stop)


def _assert_shared_arrays_match_mask(
    window: UniformRecording | ProcessedRecording,
    full: UniformRecording | ProcessedRecording,
    mask: np.ndarray,
) -> None:
    """Compare the arrays both recording types carry."""
    assert window.n_samples == int(mask.sum())
    assert window.sample_rate_hz == full.sample_rate_hz
    np.testing.assert_array_equal(window.time, full.time[mask])
    np.testing.assert_array_equal(window.acc, full.acc[mask])
    if full.gyr is None:
        assert window.gyr is None
    else:
        np.testing.assert_array_equal(window.gyr, full.gyr[mask])


def test_slicing_a_uniform_recording_trims_temperature_and_keeps_path(
    uniform: UniformRecording,
) -> None:
    start, stop, mask = _window_bounds(uniform, 100, 300)

    window = slice_recording(uniform, start=start, stop=stop)

    assert isinstance(window, UniformRecording)
    _assert_shared_arrays_match_mask(window, uniform, mask)
    np.testing.assert_array_equal(window.temp, uniform.temp[mask])
    assert window.path == uniform.path
    assert window.metadata == uniform.metadata
    # the window is still on a grid, so time stays derived from start_time.
    assert window.time_override is None
    assert window.start_time == start
    assert window.first_sample_time == start


def test_slicing_a_processed_recording_trims_the_sample_flags(
    processed: ProcessedRecording,
) -> None:
    start, stop, mask = _window_bounds(processed, 1000, 3000)

    window = slice_recording(processed, start=start, stop=stop)

    assert isinstance(window, ProcessedRecording)
    _assert_shared_arrays_match_mask(window, processed, mask)
    np.testing.assert_array_equal(window.valid, processed.valid[mask])
    np.testing.assert_array_equal(window.clipped, processed.clipped[mask])
    assert window.calibration is processed.calibration
    assert window.time_override is None


def test_slicing_a_uniform_recording_with_a_non_uniform_timeline(
    uniform: UniformRecording,
) -> None:
    full = _off_the_grid(uniform)
    start, stop, mask = _window_bounds(full, 100, 200)

    window = slice_recording(full, start=start, stop=stop)

    assert isinstance(window, UniformRecording)
    _assert_shared_arrays_match_mask(window, full, mask)
    np.testing.assert_array_equal(window.temp, full.temp[mask])
    assert window.path == full.path
    # off the grid, so the timeline is carried rather than derived, and
    # start_time keeps naming the grid origin instead of the first sample.
    assert window.time_override is not None
    np.testing.assert_array_equal(window.time_override, full.time[mask])
    assert window.start_time == full.start_time
    assert window.first_sample_time == start


def test_slicing_a_processed_recording_with_a_non_uniform_timeline(
    processed: ProcessedRecording,
) -> None:
    full = _off_the_grid(processed)
    start, stop, mask = _window_bounds(full, 1000, 2000)

    window = slice_recording(full, start=start, stop=stop)

    assert isinstance(window, ProcessedRecording)
    _assert_shared_arrays_match_mask(window, full, mask)
    np.testing.assert_array_equal(window.valid, full.valid[mask])
    np.testing.assert_array_equal(window.clipped, full.clipped[mask])
    assert window.time_override is not None
    assert window.start_time == full.start_time


@pytest.mark.parametrize(
    "off_the_grid",
    [False, True],
    ids=["grid", "non_uniform"],
)
def test_omitting_the_start_bound_keeps_every_earlier_sample(
    processed: ProcessedRecording,
    off_the_grid: bool,
) -> None:
    full = _off_the_grid(processed) if off_the_grid else processed
    stop = float(full.time[2000])
    mask = full.time < stop

    window = slice_recording(full, stop=stop)

    _assert_shared_arrays_match_mask(window, full, mask)
    assert window.first_sample_time == full.first_sample_time


@pytest.mark.parametrize(
    "off_the_grid",
    [False, True],
    ids=["grid", "non_uniform"],
)
def test_omitting_the_stop_bound_keeps_every_later_sample(
    processed: ProcessedRecording,
    off_the_grid: bool,
) -> None:
    full = _off_the_grid(processed) if off_the_grid else processed
    start = float(full.time[2000])
    mask = full.time >= start

    window = slice_recording(full, start=start)

    _assert_shared_arrays_match_mask(window, full, mask)
    assert window.n_samples == full.n_samples - 2000
    assert window.first_sample_time == start


def test_slicing_an_accelerometer_only_recording_keeps_gyroscope_absent(
    uniform: UniformRecording,
) -> None:
    full = replace(uniform, gyr=None)
    start = float(full.time[100])
    mask = full.time >= start

    window = slice_recording(full, start=start)

    _assert_shared_arrays_match_mask(window, full, mask)
    assert window.gyr is None
    np.testing.assert_array_equal(window.temp, full.temp[mask])


def test_bounds_outside_the_recording_clamp_to_it(
    processed: ProcessedRecording,
) -> None:
    before = processed.start_time - 3600.0
    after = float(processed.time[-1]) + 3600.0

    window = slice_recording(processed, start=before, stop=after)

    _assert_shared_arrays_match_mask(
        window,
        processed,
        np.ones(processed.n_samples, dtype=bool),
    )
    assert window.start_time == processed.start_time


def test_index_rounding_margin_absorbs_epoch_scale_float_error(
    uniform: UniformRecording,
) -> None:
    """A start on the grid must keep its own sample, not the next one.

    ``start_time`` carries the full unix-epoch magnitude, so rebuilding a
    grid-aligned time and inverting it can land just above the integer
    index. Without the margin in slice_recording, ceil() rounds those
    samples away.
    """
    # index 13 of this fixture is one of the samples that overshoots. The
    # bound below is a literal. The error is a fact of float64 at this
    # magnitude, and comparing against slice_recording's own margin would
    # abort here instead of on behaviour.
    overshoot = (
        float(uniform.time[13]) - uniform.start_time
    ) * uniform.sample_rate_hz - 13
    assert 0.0 < overshoot < 1e-4

    for index in range(uniform.n_samples):
        window = slice_recording(uniform, start=float(uniform.time[index]))
        assert window.n_samples == uniform.n_samples - index
