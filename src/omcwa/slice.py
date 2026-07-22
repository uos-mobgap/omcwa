"""Time-range slicing for recordings."""

from __future__ import annotations

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
    mask: np.ndarray,
) -> np.ndarray | None:
    if array is None:
        return None
    return array[mask]


def slice_recording(
    recording: UniformRecording | ProcessedRecording,
    *,
    start: float | None = None,
    stop: float | None = None,
) -> UniformRecording | ProcessedRecording:
    """Return a recording restricted to ``start <= time < stop``."""
    mask = _time_mask(recording.time, start=start, stop=stop)

    if isinstance(recording, UniformRecording):
        return UniformRecording(
            time=recording.time[mask],
            acc=recording.acc[mask],
            gyr=_slice_array(recording.gyr, mask),
            temp=_slice_array(recording.temp, mask),
            metadata=dict(recording.metadata),
            path=recording.path,
        )

    return ProcessedRecording(
        sample_rate_hz=recording.sample_rate_hz,
        time=recording.time[mask],
        acc=recording.acc[mask],
        gyr=_slice_array(recording.gyr, mask),
        calibration=recording.calibration,
        metadata=dict(recording.metadata),
        valid=_slice_array(recording.valid, mask),
        clipped=_slice_array(recording.clipped, mask),
    )
