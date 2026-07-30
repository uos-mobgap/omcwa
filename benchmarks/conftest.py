"""Fixtures shared by the benchmark suite.

The recording used by the benchmarks is chosen on the command line and written
on first use into ``benchmarks/.cache``. Generated files are reused across
runs, so only the first run of a given size pays the generation cost.

This module also collects the memory figures and prints them as a table once
the run finishes, in the same place `pytest-benchmark` prints its own.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omcwa import _native
from synthetic_cwa import RecordingSpec, write_cwa

CACHE_DIR = Path(__file__).resolve().parent / ".cache"

DEVICES = ("AX3", "AX6")

MEGABYTE = 1024 * 1024

# width of the memory summary table, which is the sum of its column widths
TABLE_WIDTH = 18 + 14 + 18 + 20

# memory rows are collected during the run and read back by the terminal
# summary hook, which has no access to fixtures
MEMORY_REPORT = pytest.StashKey[list[dict]]()


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the options that select the benchmark recording."""
    group = parser.getgroup("omcwa", "omcwa benchmarks")
    group.addoption(
        "--cwa-hours",
        type=float,
        default=1.0,
        help="length of the generated benchmark recording (default: 1.0)",
    )
    group.addoption(
        "--cwa-device",
        choices=DEVICES,
        default="AX6",
        help="device to emulate, AX3 has no gyroscope (default: AX6)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Prepare the collector that the memory tests append to."""
    config.stash[MEMORY_REPORT] = []


@pytest.fixture(scope="session")
def memory_report(request: pytest.FixtureRequest) -> list[dict]:
    """Rows collected by the memory tests, printed in the run summary."""
    return request.config.stash[MEMORY_REPORT]


@pytest.fixture(scope="session")
def recording_spec(request: pytest.FixtureRequest) -> RecordingSpec:
    """The recording every benchmark in this run measures."""
    return RecordingSpec(
        hours=request.config.getoption("--cwa-hours"),
        device=request.config.getoption("--cwa-device"),
    )


@pytest.fixture(scope="session")
def cwa_path(recording_spec: RecordingSpec) -> Path:
    """Path to the cached recording, written on first use."""
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / recording_spec.filename
    if not path.exists():
        # write under a temporary name and rename, so that an interrupted run
        # cannot leave a truncated file that a later run would trust
        partial = path.with_name(path.name + ".partial")
        write_cwa(recording_spec, partial)
        partial.replace(path)

    return path


@pytest.fixture(scope="session")
def loaded_cwa(cwa_path: Path) -> _native.LoadedCwa:
    """A decoded recording, loaded once and shared by the stage benchmarks.

    Calibrating and resampling both need a loaded file. Loading it here keeps
    that cost out of the measurements for those two stages.
    """
    return _native.LoadedCwa.load(str(cwa_path))


def pytest_terminal_summary(terminalreporter) -> None:
    """Print the memory figures."""
    rows = terminalreporter.config.stash[MEMORY_REPORT]
    if not rows:
        return

    first = rows[0]
    header = (
        f" memory: {first['file']},"
        f" {max(row['samples'] for row in rows):,} samples "
    )
    terminalreporter.write_line("")
    terminalreporter.write_line(header.center(TABLE_WIDTH, "-"))
    terminalreporter.write_line(
        f"{'Stage':<18}{'Peak RSS':>14}{'Output arrays':>18}"
        f"{'Bytes per sample':>20}"
    )

    for row in rows:
        samples = row["samples"]
        per_sample = row["peak_array_bytes"] / samples if samples else 0.0
        terminalreporter.write_line(
            f"{row['stage']:<18}"
            f"{row['peak_rss_bytes'] / MEGABYTE:>11,.1f} MB"
            f"{row['peak_array_bytes'] / MEGABYTE:>15,.1f} MB"
            f"{per_sample:>20.1f}"
        )

    terminalreporter.write_line("-" * TABLE_WIDTH)
    terminalreporter.write_line(
        f"Peak RSS includes {first['file_bytes'] / MEGABYTE:,.1f} MB of "
        "memory-mapped recording, which is clean and evictable."
    )
