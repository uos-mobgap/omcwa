# Benchmarks

Times and peak memory for the omcwa pipeline, on macOS, Linux, and Windows.

```bash
uv sync --group bench
uv run pytest benchmarks
```

or

```bash
pip install -e ".[bench]"
python -m pytest benchmarks
```

## Design

Two pieces.

`synthetic_cwa.py` writes deterministic CWA files in Python and NumPy at about
350 MB/s. No `omsynth`, no participant recordings. Sector layout matches
`native/vendored/omconvert/omdata.c` and was checked against real AX6 files.

`test_pipeline.py` times the pipeline with `pytest-benchmark`. It handles
warmup, outlier filtering, stats, and branch comparison.

The question this suite answers is "did this change make the pipeline slower?"
It is not a profiler. If a run regresses and you need per-function detail, use
`perf`, Instruments, or `py-spy`.

## Layout

| File                    | Purpose                                                                  |
| ----------------------- | ------------------------------------------------------------------------ |
| `synthetic_cwa.py`      | Deterministic synthetic CWA files of arbitrary duration                  |
| `conftest.py`           | Pytest CLI flags, shared fixtures, and memory summary reporter           |
| `test_pipeline.py`      | Pipeline timing                                                          |
| `memory.py`             | Subprocess harness for peak RSS and output array allocation              |
| `test_memory.py`        | Memory regression assertions per pipeline stage                          |
| `test_synthetic_cwa.py` | Correctness and format checks for the synthetic generator                |
| `.cache/`               | Local cache for generated CWA files, ignored by Git                      |

`test_synthetic_cwa.py` is a normal test, not a benchmark. It checks that the
generator writes valid CWA before anything is timed.

## Running

Default `pytest` only runs `tests/`. Point it at `benchmarks/` yourself:

```bash
uv run pytest benchmarks
```

### CLI options

| Option         | Default | Description                                                       |
| -------------- | ------- | ----------------------------------------------------------------- |
| `--cwa-hours`  | `1.0`   | Generated recording length in hours                               |
| `--cwa-device` | `AX6`   | `AX6` (accel + gyro) or `AX3` (accel only)                        |

```bash
uv run pytest benchmarks --cwa-hours 10
uv run pytest benchmarks --cwa-hours 10 --cwa-device AX3
```

### Choosing a duration

| `--cwa-hours` | File size (AX6) | Peak output memory | `test_process_cwa` time | Use                                             |
| ------------- | --------------- | ------------------ | ----------------------- | ----------------------------------------------- |
| `1`           | 4.6 MB          | 24 MB              | ~0.2 s                  | Catch large regressions                         |
| `10`          | 46 MB           | 238 MB             | ~2.0 s                  | Compare branches                                |
| `100`         | 461 MB          | 2.4 GB             | ~17 s                   | Longer look                                     |
| `200`         | 922 MB          | 4.8 GB             | ~33 s                   | Pre-release, max expected file                  |

Peak output memory is about 66 bytes per sample. If the machine starts
swapping, the timings are junk.

## What is measured

| Benchmark             | Stage                                                             |
| --------------------- | ----------------------------------------------------------------- |
| `test_load`           | `OmDataLoad`, CWA decode                                          |
| `test_auto_calibrate` | Stationary points and calibration fit                             |
| `test_resample`       | Uniform interpolation and output arrays                           |
| `test_process_cwa`    | Full pipeline: load, auto_calibrate, resample                     |

The first three share a pre-loaded recording, so load time is not counted
twice. `test_process_cwa` should land near the sum of the other three.

`test_load` reads through `mmap`. After the first run the file is in the OS
page cache, so you are timing decode, not disk.

## Memory

Memory tests use the same synthetic recording as the timing tests and print:

```
---------------- memory: ax6-1h.cwa, 360,000 samples -----------------
Stage                   Peak RSS     Output arrays    Bytes per sample
load                     34.2 MB            0.0 MB                 0.0
auto_calibrate           33.5 MB            0.0 MB                 0.0
resample                 56.3 MB           22.7 MB                66.0
load_cwa                 55.8 MB           22.7 MB                66.0
process_cwa              56.5 MB           22.7 MB                66.0
----------------------------------------------------------------------
```

Peak RSS is the high-water mark for the process during that stage. Each stage
runs in its own subprocess so the numbers do not leak across stages. mmap
pages count.

Output arrays are NumPy allocations via `tracemalloc`. They do not include
`omconvert` `malloc` structures.

Bytes per sample is `output arrays / sample count`. Dtypes and counts are
fixed across platforms and file sizes, so `test_memory.py` asserts the exact
value. That is the regression check.

`process_cwa` builds a temperature array during resample and then drops it,
because `ProcessedRecording` does not keep temperature. Peak allocation
matches `resample` at 66 B/sample.

### Running a stage by hand

```bash
uv run python benchmarks/memory.py process_cwa benchmarks/.cache/ax6-10h.cwa
```

## Comparing two runs

```bash
# 1. Save baseline from main
git switch main
uv pip install -e . --no-deps
uv run pytest benchmarks --cwa-hours 10 --benchmark-save=baseline

# 2. Benchmark changes and compare against baseline
git switch my-branch
uv pip install -e . --no-deps
uv run pytest benchmarks --cwa-hours 10 --benchmark-compare=0001 --benchmark-compare-fail=mean:5%
```

`--benchmark-compare-fail=mean:5%` fails the run if mean time gets more than
5% worse. Saved runs live in `.benchmarks/`.

Reinstall after every branch switch (`uv pip install -e . --no-deps` or
`pip install -e . --no-deps`) or you are still timing the old C++ extension.

VMs and shared CI runners jitter by around ±10%. Small deltas need a quiet
machine.

### Example comparison

10-hour AX6 recording, Apple M1 Pro, optimised branch vs baseline:

| Benchmark             | Baseline | Optimised | Difference |
| --------------------- | -------- | --------- | ---------- |
| `test_load`           | 820 ms   | 9.9 ms    | 83x faster |
| `test_auto_calibrate` | 389 ms   | 308 ms    | 21% faster |
| `test_resample`       | 421 ms   | 324 ms    | 23% faster |
| `test_process_cwa`    | 1620 ms  | 659 ms    | 2.5x faster |

## Synthetic recording

- Sampling rate: 100 Hz
- Ranges: ±8 g accelerometer, ±2000 °/s gyroscope
- Start: `2020-01-01 00:00:00 UTC`
- Channels: AX3 has 3 accel channels. AX6 has 6, gyro then accel.

### Signal pattern

A 200-second cycle, repeated.

Eight 20 s stationary holds, one per orientation, so auto-calibration gets
sphere coverage. 20 s is twice the 10 s calibration window, so a full window
still lands even if sample boundaries are unlucky.

Then 40 s of multi-frequency sinusoids on accel and gyro.

The accelerometer also gets synthetic scale, offset, and temperature error so
the fit has something real to do.
`test_auto_calibration_recovers_the_injected_error` checks that.

No RNG. Same CLI flags produce byte-identical CWA files, which is why
`.cache/` can key on the filename.

## Cross-platform notes

The writer is Python, NumPy, and little-endian dtypes (`<i2`, `<i4`, `<f8`).
Files match across architectures and OSes.

Peak RSS uses `resource.getrusage` on macOS and Linux, `psutil` on Windows.

Cached files sit in `benchmarks/.cache/`:

```bash
rm -rf benchmarks/.cache
```

## Known limitations

The last fraction of a second has no temperature. `omconvert` will not
interpolate past the last sector, so those samples read as the raw zero, about
-20.5 °C. Real CWA files do the same.

Requested durations round up to a whole sector. Exact duration and sample
count are on `RecordingSpec.duration_s` and `RecordingSpec.sample_count`.

The signal is continuous. No clock drift, packet loss, or corrupt sectors.

## Adding a measurement

### Timing

Put a test in `test_pipeline.py` that takes the `benchmark` fixture and a
recording fixture from `conftest.py`:

```python
def test_new_feature(benchmark, loaded_cwa):
    """Measures runtime for the new processing feature."""
    result = benchmark(loaded_cwa.some_method, arg=value)
    assert result is not None
```

Assert the return value so a silent no-op does not look fast.

### Memory stage

1. Add the stage to `STAGES` in `memory.py`. Return the number of output
samples, or `0` if it allocates no NumPy arrays.
2. If it allocates output arrays, add the name to `STAGES_WITH_OUTPUT`.
3. `test_memory.py` picks it up across the parameterised runs.

## References

- `native/vendored/omconvert/omdata.c`: sector format, packed timestamps, checksums, channel packing
- `native/vendored/omconvert/omcalibrate.c`: stationary windows and calibration
- `native/vendored/omconvert/omconvert.c`: temperature scale conversions
