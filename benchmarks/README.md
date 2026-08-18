# Benchmarks

Reproducible performance measurements for the omcwa pipeline on macOS, Linux, and Windows.

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

The benchmark suite consists of two core components:

1. **Synthetic CWA generator (**`synthetic_cwa.py`**)**:
  Generates deterministic CWA recordings directly in Python and NumPy at ~350 MB/s. It requires no external binaries (such as `omsynth`) and avoids relying on private participant data. The binary sector layout matches `native/vendored/omconvert/omdata.c` and is validated against real AX6 recordings.
2. **Pipeline timing benchmarks (**`test_pipeline.py`**)**:
  Measures processing performance using `pytest-benchmark` for warmup rounds, outlier filtering, statistical summaries, and comparing results across Git branches.

> This suite tests for performance regressions (answering: *did a change make the pipeline slower?*). It is not an exploratory profiler. If benchmark results regress and you need granular function profiling, use tools like `perf`, Xcode Instruments, or `py-spy`.



## Layout


| File                    | Purpose                                                                  |
| ----------------------- | ------------------------------------------------------------------------ |
| `synthetic_cwa.py`      | Generates deterministic synthetic CWA files of arbitrary duration        |
| `conftest.py`           | Pytest CLI flags, shared fixtures, and memory summary reporter           |
| `test_pipeline.py`      | Pipeline timing benchmarks                                               |
| `memory.py`             | Subprocess harness for peak RSS and output array allocation measurements |
| `test_memory.py`        | Memory regression assertions per pipeline stage                          |
| `test_synthetic_cwa.py` | Correctness and format validation tests for the synthetic generator      |
| `.cache/`               | Local cache for generated CWA files (ignored by Git)                     |


`test_synthetic_cwa.py` is a standard test module (not a benchmark) that verifies the synthetic generator produces valid CWA files before benchmarking starts.

## Running

The benchmark suite is located in `benchmarks/` and is excluded from the default test run (which targets `tests/`). Specify the directory explicitly:

```bash
uv run pytest benchmarks
```



### CLI Options


| Option         | Default | Description                                                       |
| -------------- | ------- | ----------------------------------------------------------------- |
| `--cwa-hours`  | `1.0`   | Duration of the generated CWA recording in hours                  |
| `--cwa-device` | `AX6`   | Device type: `AX6` (6-axis acc + gyro) or `AX3` (3-axis acc only) |


Examples:

```bash
uv run pytest benchmarks --cwa-hours 10
uv run pytest benchmarks --cwa-hours 10 --cwa-device AX3
```



### Choosing a Duration


| `--cwa-hours` | File Size (AX6) | Peak Output Memory | `test_process_cwa` Time | Recommended Use                                 |
| ------------- | --------------- | ------------------ | ----------------------- | ----------------------------------------------- |
| `1`           | 4.6 MB          | 24 MB              | ~0.2 s                  | Quick check for large regressions               |
| `10`          | 46 MB           | 238 MB             | ~2.0 s                  | Standard comparison between branches            |
| `100`         | 461 MB          | 2.4 GB             | ~17 s                   | Deep performance check                          |
| `200`         | 922 MB          | 4.8 GB             | ~33 s                   | Pre-release validation (max expected file size) |


> Peak output memory requires ~66 bytes per sample. Ensure your machine has enough free RAM for the chosen duration. System swapping will distort timing measurements.



## What is Measured


| Benchmark             | Pipeline Stage Tested                                             |
| --------------------- | ----------------------------------------------------------------- |
| `test_load`           | `OmDataLoad`: Decodes the raw CWA binary into memory              |
| `test_auto_calibrate` | Stationary point detection and calibration fitting                |
| `test_resample`       | Uniform time interpolation and output array allocation            |
| `test_process_cwa`    | Full pipeline end-to-end (`load` + `auto_calibrate` + `resample`) |


- The first three tests use a pre-loaded recording fixture so file loading time is not double-counted.
- `test_process_cwa` execution time should roughly equal the sum of the other three stages.
- `test_load` reads via a memory-mapped file (`mmap`). After the first run, data resides in the OS page cache, measuring decode speed rather than disk read speed.



## Memory Measurement

Memory benchmarks run alongside timing benchmarks using the same synthetic recording and print a summary table:

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



### Metrics Explained

- **Peak RSS (Resident Set Size)**:
Measures the maximum process memory used during the stage. Each stage runs in an isolated subprocess to ensure an accurate, independent reading. This includes memory-mapped file pages.
- **Output Arrays**:
Measures memory allocated for output NumPy arrays via `tracemalloc`. It excludes C-level structures allocated directly by `omconvert` with `malloc`.
- **Bytes per Sample (Primary Regression Metric)**:
Calculated as `Output Arrays / Sample Count`. Because array dtypes and sample counts are deterministic across platforms and file sizes, `test_memory.py` asserts this exact expected value to prevent unintended memory growth.

> `process_cwa` temporarily allocates a temperature array during resampling before discarding it (since `ProcessedRecording` does not store temperature). Its peak allocation therefore matches `resample` (66 B/sample).



### Running Memory Measurement Manually

You can test a single stage directly without pytest:

```bash
uv run python benchmarks/memory.py process_cwa benchmarks/.cache/ax6-10h.cwa
```



## Comparing Two Runs

To test for performance regressions between branches:

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

`--benchmark-compare-fail=mean:5%` causes pytest to fail if performance regresses by more than 5%. Saved benchmark runs are stored in `.benchmarks/`.

> 1. Always reinstall the package (`uv pip install -e . --no-deps` or `pip install -e . --no-deps`) after switching branches so the compiled C++ extension updates.
> 2. Virtual machines and shared CI runners have high timing jitter (often ±10%). Run comparisons on dedicated hardware when verifying small performance deltas.



### Example Comparison

Example results comparing an optimised branch against a baseline (10-hour AX6 recording on an Apple M1 Pro):


| Benchmark             | Baseline | Optimised | Difference      |
| --------------------- | -------- | --------- | --------------- |
| `test_load`           | 820 ms   | 9.9 ms    | **83x faster**  |
| `test_auto_calibrate` | 389 ms   | 308 ms    | **21% faster**  |
| `test_resample`       | 421 ms   | 324 ms    | **23% faster**  |
| `test_process_cwa`    | 1620 ms  | 659 ms    | **2.5x faster** |




## Synthetic Recording Specification

Each synthetic recording uses the following standard parameters:

- **Sampling Rate**: 100 Hz
- **Ranges**: $\pm 8\text{ g}$ (accelerometer) and $\pm 2000^\circ/\text{s}$ (gyroscope)
- **Start Time**: `2020-01-01 00:00:00 UTC`
- **Channels**: `AX3` has 3 acceleration channels, `AX6` has 6 interleaved channels (gyroscope first, then acceleration).



### Signal Pattern

The signal repeats a deterministic 200-second cycle:

- **Stationary Holds (8 × 20 s)**: Eight orientations provide the sphere coverage needed for auto-calibration. Each hold is 20 s (twice the 10 s calibration window requirement) to ensure at least one full window is captured regardless of sample boundary alignments.
- **Movement Phase (40 s)**: Multi-frequency sinusoids simulate dynamic motion for both accelerometer and gyroscope channels.
- **Injected Error**: The accelerometer signal contains synthetic scale, offset, and temperature errors so auto-calibration performs a realistic optimisation fit (validated in `test_auto_calibration_recovers_the_injected_error`).
- **Determinism**: Signals are generated from mathematical formulae without random numbers. Identical CLI parameters produce byte-identical CWA files, allowing `.cache/` to cache files by filename.



## Cross-Platform Notes

- **Portability**: The synthetic writer uses only pure Python, NumPy, and explicit little-endian dtypes (`<i2`, `<i4`, `<f8`), producing identical binary files across all architectures and operating systems.
- **Memory Tracking**: Peak RSS is measured using standard library `resource.getrusage` on macOS and Linux, and `psutil` on Windows.
- **Disk Cache**: Cached CWA files are stored in `benchmarks/.cache/`. To free disk space:
  ```bash
  rm -rf benchmarks/.cache
  ```



## Known Limitations

- **Trailing Temperature**: The final fraction of a second of a recording lacks temperature data because `omconvert` cannot interpolate past the last sector. These trailing samples read as the raw zero value (~ -20.5 °C), matching the behaviour on real CWA files.
- **Sector Alignment**: Requested durations are rounded up to the nearest whole sector. Exact durations and sample counts are exposed via `RecordingSpec.duration_s` and `RecordingSpec.sample_count`.
- **Idealised Signal**: Synthetic recordings contain continuous sessions without clock drift, packet loss, or corrupt sectors.



## Adding a New Measurement



### 1. Adding a Timing Benchmark

Add a test function in `test_pipeline.py` using the `benchmark` fixture and a recording fixture from `conftest.py`:

```python
def test_new_feature(benchmark, loaded_cwa):
    """Measures runtime for the new processing feature."""
    result = benchmark(loaded_cwa.some_method, arg=value)
    assert result is not None  # Always assert return value to verify execution
```



### 2. Adding a Memory Measurement

1. Define the stage function in `STAGES` within `memory.py`. Return the number of generated output samples (or `0` if no NumPy arrays are produced).
2. If the stage allocates output arrays, add its name to `STAGES_WITH_OUTPUT`.
3. `test_memory.py` will automatically test the stage across parameterised runs.



## References

Binary layout and conversion logic reference vendored OpenMovement source files:

- `native/vendored/omconvert/omdata.c`: Sector format, packed timestamps, checksums, and channel packing.
- `native/vendored/omconvert/omcalibrate.c`: Stationary window detection and calibration algorithms.
- `native/vendored/omconvert/omconvert.c`: Temperature sensor scale conversions.

