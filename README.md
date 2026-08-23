# omcwa

omcwa loads OpenMovement `.cwa` recordings from AX3 and AX6 devices.
It runs omconvert-compatible accelerometer auto-calibration, then resamples
to uniform NumPy arrays.

Version 0.1 has one CWA-to-NumPy pipeline. The vendored OpenMovement C code
runs behind pybind11.

## Install

Install with [uv](https://docs.astral.sh/uv/).

From a checkout:

```bash
git clone https://github.com/uos-mobgap/omcwa.git
cd omcwa
uv sync
```

omcwa is not on PyPI yet. Prebuilt wheels for Linux (x86_64, aarch64), macOS
(arm64), and Windows (amd64, arm64), Python 3.11-3.14, are attached to each
[GitHub release](https://github.com/uos-mobgap/omcwa/releases). Download the
wheel matching your platform and interpreter, then:

```bash
uv add ./omcwa-<version>-<tag>.whl
```

or

```bash
pip install omcwa-<version>-<tag>.whl
```


Editable builds from a checkout need Python 3.11-3.14 and a C++17 toolchain.

## Quickstart

```python
from omcwa import CalibrationError, process_cwa

try:
    recording = process_cwa("recording.cwa")
except CalibrationError as error:
    print(f"Auto-calibration failed with code {error.error_code}")
    raise

print(recording.sample_rate_hz)
print(recording.time.shape)
print(recording.acc.shape)
print(recording.gyr is not None)
```

The default call loads the CWA once and fits omconvert auto-calibration on the
complete first session. If that fit fails, it raises before allocating
resampled output. Then it resamples with cubic interpolation at the file
default rate.

Options:

```python
from omcwa import InterpolateMode, process_cwa

recording = process_cwa(
    "recording.cwa",
    sample_rate_hz=100.0,             # 0 selects the file rate
    calibrate=True,
    interpolate=InterpolateMode.CUBIC,
    stationary_time=10.0,             # window length auto-calibration scans for stillness
    calibration_source="data",        # "player" reproduces omconvert's original AX6 path
    on_calibration_failure="raise",   # "identity" keeps omconvert's original behaviour
    time_range=None,
    dtype="float64",                  # "float32" halves acc/gyr memory
)
```

## Relationship to omconvert

omcwa vendors OpenMovement's `omconvert` C code rather than reimplementing
it, and it patches that code where the patches earn their keep.
`native/VENDORING.md` tracks every local change against the pinned upstream
commit. Two are performance-only and leave output byte-identical. The third
is a correctness fix: AX6 sectors put gyroscope axes before the
accelerometer, which broke `omconvert`'s own proxy for locating calibration
temperature and forced AX6 through a slower interpolating "player" pass to
get a usable fit.

The default `calibration_source="data"` reads temperature from its actual
fixed sector offset and calibrates straight from CWA sectors, for both AX3
and AX6. It avoids the interpolating-player pass entirely. Pass
`calibration_source="player"` to reproduce `omconvert`'s original path, or
`on_calibration_failure="identity"` to reproduce its identity fallback,
when a downstream pipeline needs `omconvert`'s exact original numbers.

`time_range=(start, stop)` is a half-open interval in Unix seconds,
`start <= time < stop`. Calibration and resampling still run on the full
session. The range trims the finished output.

## Calibration failures

Strict failure is the default. `CalibrationError` is a `RuntimeError`. The
native omconvert code is on `error.error_code`. The synthetic fixtures cover
the common `-1` (too few stationary points) and `-2` (no usable axis fit)
outcomes.

If you are going to keep uncalibrated acceleration, pass identity fallback:

```python
fallback = process_cwa(
    "recording.cwa",
    on_calibration_failure="identity",
)

if not fallback.calibration.success:
    print(fallback.calibration.error_code)
```

That is the omconvert/OMGUI numerical fallback. Identity coefficients go on,
`Calibration.success` stays `False`, and the failure code is kept.

To skip fitting, pass `calibrate=False`. The returned `Calibration` is a
successful identity calibration with error code `0`.

## Returned data and units

`process_cwa` returns a `ProcessedRecording`:

- `time`: `float64` Unix timestamps in seconds
- `acc`: `float64` acceleration in g, shape `(samples, 3)`
- `gyr`: `float64` angular velocity in degrees per second, or `None`
- `sample_rate_hz`: the resolved uniform output rate
- `calibration`: scale, offset, temperature coefficients, reference
temperature, success flag, error code, and auto-calibration diagnostics
(stationary-point count, axis coverage, mean SVM fit error)
- `valid` and `clipped`: per-sample boolean flags
- `metadata`: public device and first-session metadata

`acc` and `gyr` are `float64` unless `dtype="float32"` was passed to
`process_cwa`; `time` stays `float64` regardless, since it carries the full
Unix-epoch magnitude.

AX3 recordings usually have acceleration only. AX6 recordings usually have
acceleration and gyroscope. Auto-calibration corrects the accelerometer.
Gyroscope values are scaled to physical units.

`load_cwa` returns a `UniformRecording` at the file rate with identity
calibration:

```python
from omcwa import load_cwa

uniform = load_cwa("recording.cwa")
print(uniform.acc.shape)
print(uniform.temp.shape)
```

`acc` and `gyr` units match `ProcessedRecording`, including the `dtype`
argument. `temp` is `float64` degrees Celsius. `slice_recording` in
`omcwa.slice` cuts half-open time slices of either public recording type.

## Current limits

- The whole CWA and the whole resampled output sit in memory.
- `time_range` trims after processing. Decode, calibration, resampling, and
peak memory still cover the full session.
- Native processing takes the first session in a CWA file.
- Do not point 0.1 at 1 GB recordings or a fleet. Native windowing and
chunked output need their own design and PR.

## Reproducible tests

Core tests use committed synthetic `omsynth` CWA files under
`tests/fixtures/golden/`. Reference NPZ and JSON oracles came from the
OpenMovement `omconvert` pipeline. Tests do not download data, call
external binaries, or skip when local recordings are missing.

See [tests/fixtures/README.md](tests/fixtures/README.md).

Run the development gates with:

```bash
uv sync --group dev
uv run ruff check src tests benchmarks
uv run ruff format --check src tests benchmarks
./scripts/check_cpp_format.sh
uv run pytest -q
```

## Benchmarks

`pytest-benchmark` times the pipeline. Peak memory is measured on the same
run. Both use synthetic CWA files generated on demand.

```bash
uv sync --group bench
uv run pytest benchmarks --cwa-hours 10
```

That suite is not in the default `pytest` run. Details in
[benchmarks/README.md](benchmarks/README.md).

## Showcase notebook

`examples/showcase_omcwa.ipynb` walks through calibration, resampling, the
`data`/`player` calibration-source parity check, and `dtype="float32"`
memory savings, all on committed synthetic fixtures:

```bash
uv sync --group showcase
uv run jupyter lab examples/showcase_omcwa.ipynb
```

## License

BSD-2-Clause. See `LICENSE`.

Vendored OpenMovement sources and licenses are in
`THIRD_PARTY_NOTICES.md`.
