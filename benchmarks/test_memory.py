"""Memory measurements for the omcwa pipeline.

These use the same generated recording as the timing benchmarks, so both sets
of numbers describe the same workload. The figures are printed as a
table at the end of the run.

Every stage also asserts how much output it should allocate, which is exactly
known from the sample count and the dtypes. That is what makes this a test
rather than a report.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from memory import STAGES, measure_isolated
from synthetic_cwa import RecordingSpec

# output bytes per sample: time 8, acc 24, temp 8, valid 1, clipped 1, plus
# gyro 24 when the device has a gyroscope

# every stage that produces output currently allocates all of them, including
# process_cwa, which asks omconvert for a temperature array and then drops it
# because ProcessedRecording has no temperature field. Should a stage stop
# allocating one of these, this becomes a per-stage table
OUTPUT_BYTES_PER_SAMPLE = {"AX3": 42, "AX6": 66}

# stages that materialise output arrays. The rest run entirely inside
# omconvert, which allocates with plain malloc that tracemalloc cannot see, so
# they should register as nothing
STAGES_WITH_OUTPUT = frozenset({"resample", "load_cwa", "process_cwa"})

# tracemalloc also sees the handful of ordinary Python allocations made along
# the way. Measured at about four kilobytes, and it does not grow with the
# recording, so this is a fixed budget rather than a per-sample one. Adding an
# output array costs at least one byte per sample, which clears this at every
# recording length the suite is run at
PYTHON_ALLOCATION_SLACK = 32 * 1024


@pytest.mark.parametrize("stage", list(STAGES))
def test_stage_memory(
    stage: str,
    cwa_path: Path,
    recording_spec: RecordingSpec,
    memory_report: list[dict],
) -> None:
    """Measure one stage and check that it allocates what it should."""
    measured = measure_isolated(stage, cwa_path)
    memory_report.append(
        {
            "stage": stage,
            "file": cwa_path.name,
            "file_bytes": cwa_path.stat().st_size,
            **measured,
        }
    )

    if stage not in STAGES_WITH_OUTPUT:
        assert measured["samples"] == 0
        assert measured["peak_array_bytes"] < PYTHON_ALLOCATION_SLACK
        return

    # a stage that quietly resampled half the recording would allocate half the
    # memory and read as an improvement, so check that the work was done.
    assert measured["samples"] == recording_spec.sample_count

    expected = OUTPUT_BYTES_PER_SAMPLE[recording_spec.device]
    per_sample = measured["peak_array_bytes"] / measured["samples"]
    assert measured["peak_array_bytes"] == pytest.approx(
        expected * measured["samples"], abs=PYTHON_ALLOCATION_SLACK
    ), (
        f"{stage} allocated {per_sample:.1f} bytes per output sample on "
        f"{recording_spec.device}, expected {expected}. If that is a "
        f"deliberate change, update OUTPUT_BYTES_PER_SAMPLE."
    )
