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

Wheels are not published yet:

```bash
uv add omcwa
# or
pip install omcwa
```

Editable builds need Python 3.11-3.14 and a C++17 toolchain.

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
    stationary_time=10.0,
    on_calibration_failure="raise",
    time_range=None,
)
```

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
temperature, success flag, and error code
- `valid` and `clipped`: per-sample boolean flags
- `metadata`: public device and first-session metadata

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

`acc` and `gyr` units match `ProcessedRecording`. `temp` is `float64`
degrees Celsius. `slice_recording` in `omcwa.slice` cuts half-open time
slices of either public recording type.

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

The notebook at `examples/showcase_omcwa.ipynb` uses the committed
`cal_success.cwa` fixture:

```bash
uv sync --group showcase
uv run jupyter lab examples/showcase_omcwa.ipynb
```

## License

BSD-2-Clause. See `LICENSE`.

Vendored OpenMovement sources and licenses are in
`THIRD_PARTY_NOTICES.md`.
