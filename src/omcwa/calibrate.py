"""Calibration backends."""

from __future__ import annotations

from omcwa import _native
from omcwa.defaults import (
    DEFAULT_INTERPOLATE,
    DEFAULT_STATIONARY_TIME,
    USE_FILE_SAMPLE_RATE,
)
from omcwa.types import (
    CalibratedRecording,
    Calibration,
    RawRecording,
    source_path,
)


class OmConvertCalibrate:
    """Auto-calibrate a recording using vendored omconvert.

    Reopens the source CWA and runs auto-calibration on the full recording.
    Corrected accel is returned in memory. Gyro is unchanged.
    """

    def __init__(
        self,
        *,
        sample_rate_hz: float = USE_FILE_SAMPLE_RATE,
        interpolate: int = int(DEFAULT_INTERPOLATE),
        stationary_time: float = DEFAULT_STATIONARY_TIME,
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
        """
        self.sample_rate_hz = sample_rate_hz
        self.interpolate = interpolate
        self.stationary_time = stationary_time

    def __call__(self, recording: RawRecording) -> CalibratedRecording:
        """Return a calibrated copy of ``recording``."""
        path = source_path(recording)
        loaded = _native.LoadedCwa.load(path)
        native_cal = loaded.auto_calibrate(
            self.sample_rate_hz,
            self.interpolate,
            self.stationary_time,
        )
        calibration = Calibration.from_native(native_cal)

        if recording.temp is not None:
            temp: float | object = recording.temp
        else:
            temp = 0.0

        acc_calibrated = loaded.apply_calibration(
            recording.acc, temp, native_cal
        )

        metadata = dict(recording.metadata)
        metadata["source_path"] = path
        metadata["_native_calibration"] = native_cal

        return CalibratedRecording(
            time=recording.time,
            acc=acc_calibrated,
            gyr=recording.gyr,
            temp=recording.temp,
            calibration=calibration,
            metadata=metadata,
            path=path,
        )


def raw_to_calibrated_identity(recording: RawRecording) -> CalibratedRecording:
    """Wrap a raw recording with identity calibration (skip auto-calibrate)."""
    path = source_path(recording)
    native_cal = _native.identity_calibration()
    metadata = dict(recording.metadata)
    metadata["source_path"] = path
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
