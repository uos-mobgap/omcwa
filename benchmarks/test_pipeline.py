"""Benchmarks for the omcwa pipeline.

Four measurements, one per stage plus the public entry point that composes
them. Every stage is measured on the same recording so the numbers add up and
can be compared against each other.

Run them with ``uv run pytest benchmarks``. See ``benchmarks/README.md`` for
what the numbers mean and how to compare two runs.
"""

from __future__ import annotations

from pathlib import Path

from omcwa import _native, process_cwa
from omcwa.defaults import (
    DEFAULT_INTERPOLATE,
    DEFAULT_STATIONARY_TIME,
    USE_FILE_SAMPLE_RATE,
)
from synthetic_cwa import RecordingSpec


def test_load(benchmark, cwa_path: Path) -> None:
    """Decode a whole CWA file into memory.

    The file is read through a memory mapping, so every round after the first
    reads from the operating system page cache. This measures decode cost, not
    disk throughput.
    """
    loaded = benchmark(_native.LoadedCwa.load, str(cwa_path))
    assert loaded.metadata()["num_channels"] > 0


def test_auto_calibrate(benchmark, loaded_cwa: _native.LoadedCwa) -> None:
    """Scan a decoded recording for stationary points and fit a calibration.

    The generated recording always calibrates successfully, so this measures a
    complete fit rather than an early exit.
    """
    calibration = benchmark(
        loaded_cwa.auto_calibrate,
        sample_rate_hz=USE_FILE_SAMPLE_RATE,
        interpolate=int(DEFAULT_INTERPOLATE),
        stationary_time=DEFAULT_STATIONARY_TIME,
    )
    assert calibration.success


def test_resample(benchmark, loaded_cwa: _native.LoadedCwa) -> None:
    """Interpolate a decoded recording onto a uniform grid.

    Identity calibration is used so that the measurement covers interpolation
    and output allocation only, without a calibration fit in front of it.
    """
    result = benchmark(
        loaded_cwa.resample,
        _native.identity_calibration(),
        sample_rate_hz=USE_FILE_SAMPLE_RATE,
        interpolate=int(DEFAULT_INTERPOLATE),
    )
    assert result["time"].shape[0] > 0


def test_process_cwa(
    benchmark, cwa_path: Path, recording_spec: RecordingSpec
) -> None:
    """Load, calibrate, and resample through the public entry point.

    This is the number a user of the package actually experiences. It should
    be close to the sum of the three stage benchmarks above.
    """
    recording = benchmark(process_cwa, cwa_path)
    assert recording.time.shape[0] == recording_spec.sample_count
