"""Calibration backends."""

from __future__ import annotations

from typing import Any

from omcwa import _native
from omcwa.defaults import (
    DEFAULT_INTERPOLATE,
    DEFAULT_STATIONARY_TIME,
    USE_FILE_SAMPLE_RATE,
)
from omcwa.handle import CwaHandle
from omcwa.types import (
    CalibratedRecording,
    Calibration,
    UniformRecording,
    source_path,
)


def _loaded_from_recording(recording: UniformRecording) -> Any:
    """Return native LoadedCwa for ``recording``, reusing handle when set."""
    handle = recording.metadata.get("_cwa_handle")
    if isinstance(handle, CwaHandle):
        return handle._loaded
        
    return _native.LoadedCwa.load(source_path(recording))


class OmConvertCalibrate:
    """Auto-calibrate a recording using vendored omconvert.

    Uses the shared ``_cwa_handle`` when present instead of reloading the file.
    Corrected accel is returned in memory unless ``apply_to_arrays`` is
    ``False``. Gyro is unchanged.
    """

    def __init__(
        self,
        *,
        sample_rate_hz: float = USE_FILE_SAMPLE_RATE,
        interpolate: int = int(DEFAULT_INTERPOLATE),
        stationary_time: float = DEFAULT_STATIONARY_TIME,
        apply_to_arrays: bool = True,
    ) -> None:
        """Configure auto-calibration parameters.

        Parameters
        ----------
        sample_rate_hz :
            Rate for player-based stationary detection. ``0`` uses the file
            default rate.
        interpolate :
            ``1`` nearest, ``2`` linear, ``3`` cubic.
        stationary_time :
            Minimum stationary period in seconds.
        apply_to_arrays :
            When ``False``, run auto-calibration and store
            ``_native_calibration`` but leave accel arrays uncalibrated.
        """
        self.sample_rate_hz = sample_rate_hz
        self.interpolate = interpolate
        self.stationary_time = stationary_time
        self.apply_to_arrays = apply_to_arrays

    def __call__(self, recording: UniformRecording) -> CalibratedRecording:
        """Return a calibrated copy of ``recording``."""
        path = source_path(recording)
        loaded = _loaded_from_recording(recording)
        native_cal = loaded.auto_calibrate(
            self.sample_rate_hz,
            self.interpolate,
            self.stationary_time,
        )
        calibration = Calibration.from_native(native_cal)

        if self.apply_to_arrays:
            if recording.temp is not None:
                temp: float | object = recording.temp
            else:
                temp = 0.0
            acc = loaded.apply_calibration(recording.acc, temp, native_cal)
        else:
            acc = recording.acc

        metadata = dict(recording.metadata)
        metadata["_native_calibration"] = native_cal

        return CalibratedRecording(
            time=recording.time,
            acc=acc,
            gyr=recording.gyr,
            temp=recording.temp,
            calibration=calibration,
            metadata=metadata,
            path=path,
        )


def uniform_to_calibrated_identity(
    recording: UniformRecording,
) -> CalibratedRecording:
    """Wrap uniform recording with identity calibration (no auto-cal)."""
    path = source_path(recording)
    native_cal = _native.identity_calibration()
    metadata = dict(recording.metadata)
    metadata["_native_calibration"] = native_cal

    return CalibratedRecording(
        time=recording.time,
        acc=recording.acc,
        gyr=recording.gyr,
        temp=recording.temp,
        calibration=Calibration.from_native(native_cal),
        metadata=metadata,
        path=path,
    )
