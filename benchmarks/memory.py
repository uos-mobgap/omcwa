"""Measure the memory a pipeline stage needs.

Each stage reports two figures.

Peak resident memory is the process high-water mark since start. No platform
lets us reset that portably, so each stage runs in a fresh subprocess. That
also keeps the timing benchmarks from sharing the process. Resident pages of
the memory-mapped recording count toward the mark even though they are clean
and the OS can drop them. Subtract the file size when you compare against a
memory budget.

Peak array bytes is what this package allocated for output arrays. NumPy
registers those with :mod:`tracemalloc`, so the number is the same on every
platform and scales with the output sample count. Assert on this one, and
compare it between branches. It does not include the memory-mapped file, or
the decoded structures omconvert allocates with plain ``malloc``.
tracemalloc cannot see those.

Run one stage directly to print the figures as JSON::

    python benchmarks/memory.py resample path/to/recording.cwa
"""

from __future__ import annotations

import json
import subprocess
import sys
import tracemalloc
from collections.abc import Callable
from pathlib import Path

from omcwa import _native, load_cwa, process_cwa
from omcwa.defaults import (
    DEFAULT_INTERPOLATE,
    DEFAULT_STATIONARY_TIME,
    USE_FILE_SAMPLE_RATE,
)


def peak_rss_bytes() -> int:
    """Peak resident set size of this process since it started."""
    if sys.platform == "win32":
        import psutil  # noqa: PLC0415

        return psutil.Process().memory_info().peak_wset

    import resource  # noqa: PLC0415

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    # macOS reports bytes, Linux reports kilobytes.
    return peak if sys.platform == "darwin" else peak * 1024


def _load(path: str) -> int:
    _native.LoadedCwa.load(path)
    return 0


def _auto_calibrate(path: str) -> int:
    loaded = _native.LoadedCwa.load(path)
    loaded.auto_calibrate(
        sample_rate_hz=USE_FILE_SAMPLE_RATE,
        interpolate=int(DEFAULT_INTERPOLATE),
        stationary_time=DEFAULT_STATIONARY_TIME,
    )
    return 0


def _resample(path: str) -> int:
    loaded = _native.LoadedCwa.load(path)
    result = loaded.resample(
        _native.identity_calibration(),
        sample_rate_hz=USE_FILE_SAMPLE_RATE,
        interpolate=int(DEFAULT_INTERPOLATE),
    )
    return int(result["time"].shape[0])


def _load_cwa(path: str) -> int:
    return load_cwa(path).n_samples


def _process_cwa(path: str) -> int:
    return process_cwa(path).n_samples


# Each stage runs the work a caller would run, including whatever has to happen
# first. Calibrating needs a loaded recording, so the calibrate figures include
# loading, which is what a caller actually pays.
STAGES: dict[str, Callable[[str], int]] = {
    "load": _load,
    "auto_calibrate": _auto_calibrate,
    "resample": _resample,
    "load_cwa": _load_cwa,
    "process_cwa": _process_cwa,
}


def measure(stage: str, path: str) -> dict[str, int]:
    """Run one stage in this process and return its memory figures."""
    tracemalloc.start()
    samples = STAGES[stage](path)
    _, array_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "peak_rss_bytes": peak_rss_bytes(),
        "peak_array_bytes": array_bytes,
        "samples": samples,
    }


def measure_isolated(stage: str, path: Path) -> dict[str, int]:
    """Run one stage in a fresh interpreter and return its memory figures.

    A peak is a high water mark that lasts as long as the process does, so the
    only portable way to attribute one to a single stage is to give that stage
    a process of its own.
    """
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), stage, str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


def main() -> None:
    """Worker entry point. See :func:`measure_isolated`."""
    stage, path = sys.argv[1], sys.argv[2]
    print(json.dumps(measure(stage, path)))


if __name__ == "__main__":
    main()
