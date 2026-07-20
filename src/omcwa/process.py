"""High-level CWA processing entry points."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from omcwa import _native
from omcwa.calibrate import OmConvertCalibrate, uniform_to_calibrated_identity
from omcwa.defaults import (
    DEFAULT_INTERPOLATE,
    DEFAULT_SAMPLE_RATE_HZ,
    DEFAULT_STATIONARY_TIME,
    USE_FILE_SAMPLE_RATE,
)
from omcwa.handle import CwaHandle, open_cwa
from omcwa.resample import (
    OmConvertResample,
    calibrated_to_processed_identity_rate,
    processed_from_native,
)
from omcwa.slice import slice_recording
from omcwa.types import (
    CalibrateFn,
    ProcessedRecording,
    ResampleFn,
    UniformRecording,
    ensure_path_str,
)

_UNSET = object()


def _resolve_fast_interpolate(
    calibrate_fn: OmConvertCalibrate | None,
    resample_fn: OmConvertResample | None,
) -> int | None:
    """Return interpolate for one-shot path, or None for slow path."""
    if calibrate_fn is not None and resample_fn is not None:
        if calibrate_fn.interpolate != resample_fn.interpolate:
            return None

        return calibrate_fn.interpolate

    if calibrate_fn is not None:
        return calibrate_fn.interpolate

    if resample_fn is not None:
        return resample_fn.interpolate

    return int(DEFAULT_INTERPOLATE)


def _try_fast_path(
    path_str: str,
    calibrate_fn: CalibrateFn | None,
    resample_fn: ResampleFn | None,
) -> ProcessedRecording | None:
    """Run the one-shot native path when backends are OmConvert or None."""
    cal_is_omc = calibrate_fn is None or isinstance(
        calibrate_fn, OmConvertCalibrate
    )
    res_is_omr = resample_fn is None or isinstance(
        resample_fn, OmConvertResample
    )
    
    if not (cal_is_omc and res_is_omr):
        return None

    omc_cal = (
        calibrate_fn if isinstance(calibrate_fn, OmConvertCalibrate) else None
    )
    omc_res = (
        resample_fn if isinstance(resample_fn, OmConvertResample) else None
    )

    interpolate = _resolve_fast_interpolate(omc_cal, omc_res)
    if interpolate is None:
        return None

    if omc_cal is None and omc_res is None:
        handle = open_cwa(path_str)
        uniform = handle.materialize(interpolate=interpolate)
        calibrated = uniform_to_calibrated_identity(uniform)
        return calibrated_to_processed_identity_rate(calibrated)

    calibrate = omc_cal is not None
    if omc_res is not None:
        rate = omc_res.sample_rate_hz
    else:
        rate = USE_FILE_SAMPLE_RATE

    stationary_time = (
        omc_cal.stationary_time
        if omc_cal is not None
        else DEFAULT_STATIONARY_TIME
    )

    result = _native.process(
        path_str,
        sample_rate_hz=rate,
        calibrate=calibrate,
        interpolate=int(interpolate),
        stationary_time=stationary_time,
    )

    return processed_from_native(result)


def _needs_materialize(
    calibrate_fn: CalibrateFn | None,
    resample_fn: ResampleFn | None,
) -> bool:
    """Return whether the slow path must materialize uniform arrays."""
    if calibrate_fn is not None and not isinstance(
        calibrate_fn, OmConvertCalibrate
    ):
        return True

    if resample_fn is not None and not isinstance(
        resample_fn, OmConvertResample
    ):
        return True

    return False


def _shell_uniform(handle: CwaHandle) -> UniformRecording:
    """Build a handle-backed uniform shell without resampling arrays."""
    metadata = handle.metadata()
    metadata["_cwa_handle"] = handle

    return UniformRecording(
        time=np.empty(0, dtype=np.float64),
        acc=np.empty((0, 3), dtype=np.float64),
        gyr=None,
        temp=None,
        metadata=metadata,
        path=handle.path,
    )


def load_cwa(path: str | Path) -> UniformRecording:
    """Load a CWA file at the file default sample rate.

    Convenience wrapper around ``open_cwa(path).materialize()``. Samples are
    uniformly resampled with identity calibration at the file default rate.
    """
    return open_cwa(path).materialize()


def process_cwa(
    path: str | Path,
    *,
    sample_rate_hz: float = DEFAULT_SAMPLE_RATE_HZ,
    calibrate_fn: CalibrateFn | None | object = _UNSET,
    resample_fn: ResampleFn | None | object = _UNSET,
    time_range: tuple[float, float] | None = None,
) -> ProcessedRecording:
    """Process a CWA file with optional calibration and resampling.

    By default this matches omgui: auto-calibrate the full on-disk recording,
    then resample at the file default rate (``sample_rate_hz=0``) with cubic
    interpolation. Pass an explicit rate to resample to a different Hz.

    Parameters
    ----------
    path :
        Path to a ``.cwa`` file.
    sample_rate_hz :
        Target uniform sample rate in Hz. ``0`` uses the file default rate
        (omgui "auto").
    calibrate_fn :
        ``CalibrateFn`` backend. Default is ``OmConvertCalibrate``. Pass
        ``None`` to skip auto-calibration (identity).
    resample_fn :
        ``ResampleFn`` backend. Default is ``OmConvertResample``. Pass
        ``None`` to skip resampling.
    time_range :
        Optional ``(start, stop)`` window applied after processing. Auto-
        calibration always uses the full file. The window only trims output.

    Notes
    -----
    When ``calibrate_fn`` and ``resample_fn`` are ``OmConvertCalibrate``,
    ``OmConvertResample``, or ``None``, processing uses a single native
    ``process`` call or one materialize (fast path).
    """
    path_str = ensure_path_str(path)

    if calibrate_fn is _UNSET:
        calibrate_fn = OmConvertCalibrate()

    if resample_fn is _UNSET:
        resample_fn = OmConvertResample(sample_rate_hz=sample_rate_hz)

    out = _try_fast_path(path_str, calibrate_fn, resample_fn)
    if out is None:
        handle = open_cwa(path_str)
        
        if _needs_materialize(calibrate_fn, resample_fn):
            uniform = handle.materialize()
        else:
            uniform = _shell_uniform(handle)

        if calibrate_fn is None:
            calibrated = uniform_to_calibrated_identity(uniform)
        elif isinstance(calibrate_fn, OmConvertCalibrate) and isinstance(
            resample_fn, OmConvertResample
        ):
            calibrate_with_arrays = OmConvertCalibrate(
                sample_rate_hz=calibrate_fn.sample_rate_hz,
                interpolate=calibrate_fn.interpolate,
                stationary_time=calibrate_fn.stationary_time,
                apply_to_arrays=False,
            )
            calibrated = calibrate_with_arrays(uniform)
        else:
            calibrated = calibrate_fn(uniform)

        if resample_fn is None:
            out = calibrated_to_processed_identity_rate(calibrated)
        else:
            out = resample_fn(calibrated)

    if time_range is not None:
        start, stop = time_range
        out = slice_recording(out, start=start, stop=stop)

    return out
