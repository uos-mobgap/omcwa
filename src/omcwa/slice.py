"""Time-range slicing for recordings."""

from __future__ import annotations

from math import ceil
from typing import overload

import numpy as np

from omcwa.types import ProcessedRecording, UniformRecording


@overload
def slice_recording(
    recording: UniformRecording,
    *,
    start: float | None = None,
    stop: float | None = None,
) -> UniformRecording: ...


@overload
def slice_recording(
    recording: ProcessedRecording,
    *,
    start: float | None = None,
    stop: float | None = None,
) -> ProcessedRecording: ...


# ceil((t - start_time) * sample_rate_hz) is the exact real-number formula
# for "first sample index with time >= t" on a uniform grid. In float64,
# though, start_time carries the full unix-epoch magnitude (~1.6e9), so
# reconstructing a grid-aligned t as start_time + i / rate and then
# inverting it can round-trip to i + ~1e-5 instead of i, which pushes ceil
# one index too far. Measured up to ~1.2e-5 sample-units on a week-long
# 100 Hz recording; this margin absorbs it while staying far too small to
# affect a genuinely non-aligned start/stop.
_INDEX_ROUNDING_MARGIN = 1e-4


def _index_at_or_after(t: float, *, start_time: float, rate: float) -> int:
    return ceil((t - start_time) * rate - _INDEX_ROUNDING_MARGIN)


def _sample_bounds(
    recording: UniformRecording | ProcessedRecording,
    *,
    start: float | None,
    stop: float | None,
) -> tuple[int, int]:
    """Map a half-open time window to a half-open sample index range.

    Computes indices from start_time and sample_rate_hz. Does not build
    ``recording.time``.
    """
    first = 0
    if start is not None:
        first = max(
            0,
            _index_at_or_after(
                start,
                start_time=recording.start_time,
                rate=recording.sample_rate_hz,
            ),
        )

    last = recording.n_samples
    if stop is not None:
        last = min(
            recording.n_samples,
            _index_at_or_after(
                stop,
                start_time=recording.start_time,
                rate=recording.sample_rate_hz,
            ),
        )

    return first, last


def _time_mask(
    time: np.ndarray,
    *,
    start: float | None,
    stop: float | None,
) -> np.ndarray:
    mask = np.ones(time.shape[0], dtype=bool)
    if start is not None:
        mask &= time >= start
    if stop is not None:
        mask &= time < stop
    return mask


def _slice_array(
    array: np.ndarray | None,
    key: slice | np.ndarray,
) -> np.ndarray | None:
    if array is None:
        return None
    return array[key]


def slice_recording(
    recording: UniformRecording | ProcessedRecording,
    *,
    start: float | None = None,
    stop: float | None = None,
) -> UniformRecording | ProcessedRecording:
    """Return a recording restricted to ``start <= time < stop``.

    When ``time_override`` is unset the grid has no gaps. Missing data is
    marked ``valid=False`` but still occupies a slot, so the window is
    computed from sample indices and sliced with a plain ``slice``. That
    returns a view, not a boolean mask over the full ``time`` array. A
    recording with ``time_override`` set is not on that grid, so it uses
    the boolean mask instead.
    """
    if recording.time_override is None:
        first, last = _sample_bounds(recording, start=start, stop=stop)
        key: slice | np.ndarray = slice(first, last)
        new_start_time = recording.start_time + first / recording.sample_rate_hz
        new_time_override = None
    else:
        key = _time_mask(recording.time, start=start, stop=stop)
        new_start_time = recording.start_time
        new_time_override = recording.time_override[key]

    new_acc = _slice_array(recording.acc, key)
    common = dict(
        sample_rate_hz=recording.sample_rate_hz,
        start_time=new_start_time,
        n_samples=new_acc.shape[0],
        acc=new_acc,
        gyr=_slice_array(recording.gyr, key),
        metadata=dict(recording.metadata),
        time_override=new_time_override,
    )

    if isinstance(recording, UniformRecording):
        return UniformRecording(
            **common,
            temp=_slice_array(recording.temp, key),
            path=recording.path,
        )

    return ProcessedRecording(
        **common,
        calibration=recording.calibration,
        valid=_slice_array(recording.valid, key),
        clipped=_slice_array(recording.clipped, key),
    )
