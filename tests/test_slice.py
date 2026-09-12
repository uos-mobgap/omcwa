"""Branch coverage for time-range slicing.

Follows the model of the time-range test in test_process_parity.py: take a
full recording, compute the expected window with a boolean mask over the
full arrays, and compare every array on the result. Uses the same committed
synthetic CWAs under tests/fixtures/golden/, so it needs no new oracle.
"""

from __future__ import annotations

import math
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


@pytest.mark.parametrize(
    "offset_samples",
    [0.5, 1.5, 2.5, 100.5],
    ids=["half", "one_and_a_half", "two_and_a_half", "hundred_and_a_half"],
)
def test_a_window_entirely_before_the_recording_is_empty(
    processed: ProcessedRecording,
    offset_samples: float,
) -> None:
    """A negative index must clamp to 0, not count back from the end.

    ``slice(0, -1)`` keeps all but the last sample. So a stop bound placed
    more than one sample interval before ``start_time`` used to return almost
    the whole recording. The parametrisation walks the bound further back
    because the old behaviour shed one sample per interval.
    """
    stop = processed.start_time - offset_samples / processed.sample_rate_hz

    window = slice_recording(processed, stop=stop)

    assert window.n_samples == 0
    assert window.acc.shape == (0, 3)
    assert window.valid.shape == (0,)


def test_a_window_entirely_after_the_recording_is_empty(
    processed: ProcessedRecording,
) -> None:
    after = float(processed.time[-1]) + 3600.0

    window = slice_recording(processed, start=after, stop=after + 3600.0)

    assert window.n_samples == 0
    assert window.acc.shape == (0, 3)


def test_a_stop_before_the_start_gives_an_empty_window(
    processed: ProcessedRecording,
) -> None:
    start = float(processed.time[2000])
    stop = float(processed.time[1000])

    window = slice_recording(processed, start=start, stop=stop)

    assert window.n_samples == 0
    assert window.start_time == start


def test_empty_windows_agree_across_both_code_paths(
    processed: ProcessedRecording,
) -> None:
    """The mask path cannot produce a negative index, so it is the oracle."""
    stop = processed.start_time - 100.5 / processed.sample_rate_hz
    off_the_grid = _off_the_grid(processed)

    assert slice_recording(processed, stop=stop).n_samples == 0
    assert slice_recording(off_the_grid, stop=stop).n_samples == 0


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


@pytest.mark.parametrize("fixture", ["uniform", "processed"])
@pytest.mark.parametrize(
    "off_the_grid",
    [False, True],
    ids=["grid", "non_uniform"],
)
def test_an_empty_window_has_no_first_sample_time(
    request: pytest.FixtureRequest,
    fixture: str,
    off_the_grid: bool,
) -> None:
    """Neither path invents a timestamp for a sample that is not there.

    The grid path used to return start_time, which is the clamp point and
    not a sample, while the mask path raised IndexError off an empty
    time_override. Both recording types carry the property, so both are
    parametrised here.
    """
    recording = request.getfixturevalue(fixture)
    full = _off_the_grid(recording) if off_the_grid else recording
    stop = full.start_time - 100.5 / full.sample_rate_hz

    window = slice_recording(full, stop=stop)

    assert window.n_samples == 0
    with pytest.raises(IndexError, match="empty recording"):
        _ = window.first_sample_time


@pytest.mark.parametrize(
    "off_the_grid",
    [False, True],
    ids=["grid", "non_uniform"],
)
def test_an_infinite_stop_keeps_every_later_sample(
    processed: ProcessedRecording,
    off_the_grid: bool,
) -> None:
    """``(t, inf)`` is how a caller writes "from t to the end".

    The grid path turns bounds into indices, so an infinite bound used to
    raise OverflowError in ceil() while the mask path kept the tail.
    """
    full = _off_the_grid(processed) if off_the_grid else processed
    start = float(full.time[1000])

    window = slice_recording(full, start=start, stop=math.inf)

    _assert_shared_arrays_match_mask(window, full, full.time >= start)


@pytest.mark.parametrize(
    "off_the_grid",
    [False, True],
    ids=["grid", "non_uniform"],
)
def test_an_infinite_start_keeps_every_earlier_sample(
    processed: ProcessedRecording,
    off_the_grid: bool,
) -> None:
    full = _off_the_grid(processed) if off_the_grid else processed
    stop = float(full.time[1000])

    window = slice_recording(full, start=-math.inf, stop=stop)

    _assert_shared_arrays_match_mask(window, full, full.time < stop)


@pytest.mark.parametrize("bound", ["start", "stop"])
@pytest.mark.parametrize(
    "off_the_grid",
    [False, True],
    ids=["grid", "non_uniform"],
)
def test_a_nan_bound_is_rejected(
    processed: ProcessedRecording,
    bound: str,
    off_the_grid: bool,
) -> None:
    """Both paths reject NaN rather than returning an empty window.

    Nothing compares true against NaN, so the mask path would hand back
    nothing and the caller would read that as a gap in the recording. The
    match is on the guard's own wording. ceil() raises ValueError on NaN
    too, so a looser pattern would pass without the guard.
    """
    full = _off_the_grid(processed) if off_the_grid else processed

    with pytest.raises(ValueError, match=f"{bound} must be a unix time"):
        slice_recording(full, **{bound: math.nan})
