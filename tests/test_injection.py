"""Tests for injectable calibration and resampling backends."""

from __future__ import annotations

from pathlib import Path

from omcwa import OmConvertCalibrate, OmConvertResample, process_cwa
from omcwa.types import CalibratedRecording, ProcessedRecording, RawRecording

EXPLICIT_SAMPLE_RATE_HZ = 100.0


def test_custom_calibrate_and_resample_invoked(omgui_cwa: Path) -> None:
    """Custom calibrate_fn and resample_fn hooks are called by process_cwa."""
    calls: list[str] = []

    def calibrate_fn(raw: RawRecording) -> CalibratedRecording:
        calls.append("calibrate")
        return OmConvertCalibrate()(raw)

    def resample_fn(calibrated: CalibratedRecording) -> ProcessedRecording:
        calls.append("resample")
        return OmConvertResample(sample_rate_hz=EXPLICIT_SAMPLE_RATE_HZ)(
            calibrated
        )

    process_cwa(
        omgui_cwa,
        sample_rate_hz=EXPLICIT_SAMPLE_RATE_HZ,
        calibrate_fn=calibrate_fn,
        resample_fn=resample_fn,
    )

    assert calls == ["calibrate", "resample"]
