"""Type-level checks on the public API. mypy is the runner.

Nothing here is called. ``assert_type`` has no runtime effect, and the
checks that matter are the calls a downstream project would write.
"""

from __future__ import annotations

from typing import assert_type

from omcwa import (
    DEFAULT_CALIBRATE,
    DEFAULT_CALIBRATION_SOURCE,
    DEFAULT_INTERPOLATE,
    DEFAULT_SAMPLE_RATE_HZ,
    DEFAULT_STATIONARY_TIME,
    CalibrationFailurePolicy,
    CalibrationSource,
    Dtype,
    ProcessedRecording,
    UniformRecording,
    process_cwa,
    slice_recording,
)


def _slicing_returns_the_recording_it_was_given(
    uniform: UniformRecording,
    processed: ProcessedRecording,
) -> None:
    assert_type(slice_recording(uniform, start=1.0), UniformRecording)
    assert_type(slice_recording(processed, stop=2.0), ProcessedRecording)


def _the_exported_defaults_fit_the_parameters_they_default(
    path: str,
) -> None:
    process_cwa(
        path,
        sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ,
        calibrate=DEFAULT_CALIBRATE,
        interpolate=DEFAULT_INTERPOLATE,
        stationary_time=DEFAULT_STATIONARY_TIME,
        calibration_source=DEFAULT_CALIBRATION_SOURCE,
    )


def _a_downstream_wrapper_can_name_the_option_types(
    path: str,
    *,
    calibration_source: CalibrationSource = DEFAULT_CALIBRATION_SOURCE,
    on_calibration_failure: CalibrationFailurePolicy = "raise",
    dtype: Dtype = "float64",
) -> ProcessedRecording:
    return process_cwa(
        path,
        calibration_source=calibration_source,
        on_calibration_failure=on_calibration_failure,
        dtype=dtype,
    )
