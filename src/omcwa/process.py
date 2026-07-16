"""High-level CWA processing entry points."""

from __future__ import annotations

from pathlib import Path

from omcwa import _native
from omcwa.calibrate import OmConvertCalibrate, raw_to_calibrated_identity
from omcwa.defaults import (
    DEFAULT_CALIBRATE,
    DEFAULT_INTERPOLATE,
    DEFAULT_SAMPLE_RATE_HZ,
    DEFAULT_STATIONARY_TIME,
    USE_FILE_SAMPLE_RATE,
)
from omcwa.resample import (
    OmConvertResample,
    calibrated_to_processed_identity_rate,
    processed_from_native,
)
from omcwa.slice import slice_recording
from omcwa.types import (
    CalibrateFn,
    ProcessedRecording,
    RawRecording,
    ResampleFn,
    ensure_path_str,
)

_UNSET = object()


def _is_default_calibrate(fn: OmConvertCalibrate) -> bool:
    return (
        fn.sample_rate_hz == USE_FILE_SAMPLE_RATE
        and fn.interpolate == int(DEFAULT_INTERPOLATE)
        and fn.stationary_time == DEFAULT_STATIONARY_TIME
    )


def _is_default_resample(fn: OmConvertResample, sample_rate_hz: float) -> bool:
    return fn.sample_rate_hz == sample_rate_hz and fn.interpolate == int(
        DEFAULT_INTERPOLATE
    )


def load_cwa(path: str | Path) -> RawRecording:
    """Load a CWA file at the file default sample rate.

    Samples are uniformly resampled with identity calibration. Passing
    ``sample_rate_hz=0`` to the native player selects
    ``arrangement.defaultRate`` (omconvert convention).
    """
    path_str = ensure_path_str(path)
    loaded = _native.LoadedCwa.load(path_str)
    metadata = dict(loaded.metadata())
    metadata["source_path"] = path_str

    identity = _native.identity_calibration()
    result = loaded.resample(
        identity,
        sample_rate_hz=USE_FILE_SAMPLE_RATE,
        interpolate=int(DEFAULT_INTERPOLATE),
    )
    metadata["sample_rate_hz"] = float(result["sample_rate_hz"])

    gyr = result.get("gyr")
    return RawRecording(
        time=result["time"],
        acc=result["acc"],
        gyr=None if gyr is None else gyr,
        temp=result["temp"],
        metadata=metadata,
        path=path_str,
    )


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
    When both default omconvert backends are used with matching parameters,
    processing uses a single native ``process`` call (fast path).
    """
    path_str = ensure_path_str(path)

    if calibrate_fn is _UNSET:
        calibrate_fn = OmConvertCalibrate()
    if resample_fn is _UNSET:
        resample_fn = OmConvertResample(sample_rate_hz=sample_rate_hz)

    use_fast_path = (
        calibrate_fn is not None
        and resample_fn is not None
        and isinstance(calibrate_fn, OmConvertCalibrate)
        and isinstance(resample_fn, OmConvertResample)
        and _is_default_calibrate(calibrate_fn)
        and _is_default_resample(resample_fn, sample_rate_hz)
    )

    if use_fast_path:
        result = _native.process(
            path_str,
            sample_rate_hz=sample_rate_hz,
            calibrate=DEFAULT_CALIBRATE,
            interpolate=int(DEFAULT_INTERPOLATE),
            stationary_time=DEFAULT_STATIONARY_TIME,
        )
        out = processed_from_native(
            result,
            metadata={"source_path": path_str},
        )
    else:
        raw = load_cwa(path_str)

        if calibrate_fn is None:
            calibrated = raw_to_calibrated_identity(raw)
        else:
            calibrated = calibrate_fn(raw)

        if resample_fn is None:
            out = calibrated_to_processed_identity_rate(calibrated)
        else:
            out = resample_fn(calibrated)

    if time_range is not None:
        start, stop = time_range
        sliced = slice_recording(out, start=start, stop=stop)
        if not isinstance(sliced, ProcessedRecording):
            msg = (
                "slice_recording returned unexpected type "
                "for ProcessedRecording"
            )
            raise TypeError(msg)
        out = sliced

    return out
