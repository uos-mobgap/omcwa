"""Deterministic CSV inputs for regenerating the synthetic CWA fixtures."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

CSV_HEADER = (
    "Time,Accel-X (g),Accel-Y (g),Accel-Z (g),"
    "Gyro-X (d/s),Gyro-Y (d/s),Gyro-Z (d/s)"
)


@dataclass(frozen=True)
class FixtureSpec:
    """Sampling parameters for one omsynth input."""

    duration_s: float
    sample_rate_hz: int


def _timestamp(sample_index: int, sample_rate_hz: int) -> str:
    """Format a sample index as an omsynth CSV timestamp."""
    total_ms = round(sample_index * 1000 / sample_rate_hz)
    seconds, milliseconds = divmod(total_ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return (
        f"2020-01-01 {hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
    )


def _resample_only(spec: FixtureSpec) -> list[str]:
    """Build sinusoidal accel and gyro rows for the resample-only fixture."""
    rows = [CSV_HEADER]
    for index in range(int(spec.duration_s * spec.sample_rate_hz)):
        time_s = index / spec.sample_rate_hz
        timestamp = _timestamp(index, spec.sample_rate_hz)
        accel_x = 0.15 * math.sin(2 * math.pi * 0.7 * time_s)
        accel_y = 0.10 * math.cos(2 * math.pi * 1.3 * time_s)
        accel_z = 1.0 + 0.05 * math.sin(2 * math.pi * 0.3 * time_s)
        gyro_x = 5.0 * math.sin(2 * math.pi * 2.0 * time_s)
        gyro_z = 10.0 * math.cos(2 * math.pi * 0.5 * time_s)
        rows.append(
            f"{timestamp},{accel_x:.6f},{accel_y:.6f},{accel_z:.6f},"
            f"{gyro_x:.3f},0.000,{gyro_z:.3f}"
        )
    return rows


def _cal_success(spec: FixtureSpec) -> list[str]:
    """Build stationary-orientation rows for a successful calibration fit."""
    # Eight 10-second windows, each held at a distinct gravity vector.
    orientations: Sequence[tuple[float, float, float]] = (
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, -1.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.0, 0.0, -1.0),
        (0.577, 0.577, 0.577),
        (-0.577, 0.577, 0.577),
    )
    rows = [CSV_HEADER]
    for index in range(int(spec.duration_s * spec.sample_rate_hz)):
        time_s = index / spec.sample_rate_hz
        timestamp = _timestamp(index, spec.sample_rate_hz)
        orientation = orientations[int(time_s // 10.0) % len(orientations)]
        noise = 0.002 * math.sin(2 * math.pi * 17.0 * time_s)
        accel = tuple(value + noise for value in orientation)
        rows.append(
            f"{timestamp},{accel[0]:.6f},{accel[1]:.6f},"
            f"{accel[2]:.6f},0.000,0.000,0.000"
        )
    return rows


def _cal_failure(spec: FixtureSpec) -> list[str]:
    """Build near-stationary rows with too little axis diversity."""
    rows = [CSV_HEADER]
    for index in range(int(spec.duration_s * spec.sample_rate_hz)):
        time_s = index / spec.sample_rate_hz
        timestamp = _timestamp(index, spec.sample_rate_hz)
        noise = 0.001 * math.sin(2 * math.pi * 3.0 * time_s)
        rows.append(
            f"{timestamp},{noise:.6f},{noise:.6f},"
            f"{1.0 + noise:.6f},0.000,0.000,0.000"
        )
    return rows


_GENERATORS: dict[
    str, tuple[Callable[[FixtureSpec], list[str]], FixtureSpec]
] = {
    "resample_only": (_resample_only, FixtureSpec(5.0, 100)),
    "cal_success": (_cal_success, FixtureSpec(80.0, 100)),
    "cal_failure": (_cal_failure, FixtureSpec(30.0, 100)),
    # Same generator as cal_failure. Longer duration yields error -2.
    "cal_failure_no_axis": (_cal_failure, FixtureSpec(50.0, 100)),
}


def fixture_names() -> tuple[str, ...]:
    """Return fixture names in regeneration order."""
    return tuple(_GENERATORS)


def fixture_sample_rate_hz(name: str) -> int:
    """Return the omsynth sample rate for ``name``."""
    try:
        return _GENERATORS[name][1].sample_rate_hz
    except KeyError as error:
        raise ValueError(f"unknown fixture: {name}") from error


def write_fixture_csv(path: str, name: str) -> None:
    """Write one deterministic omsynth CSV input."""
    try:
        generator, spec = _GENERATORS[name]
    except KeyError as error:
        raise ValueError(f"unknown fixture: {name}") from error
    with open(path, "w", encoding="utf-8") as csv_file:
        csv_file.write("\n".join(generator(spec)) + "\n")
