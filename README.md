# omcwa

**omcwa** loads OpenMovement `.cwa` recordings from AX3 and AX6 devices,
applies omconvert-compatible accelerometer auto-calibration, and resamples to
uniform NumPy arrays.

Version 0.1 exposes one fixed CWA-to-NumPy pipeline. It uses the
vendored OpenMovement C implementation directly through pybind11.

## Install

Recommended: [uv](https://docs.astral.sh/uv/)

From a checkout:

```bash
git clone https://github.com/uos-mobgap/omcwa.git
cd omcwa
uv sync
```

Published wheels, once available (TODO):

```bash
uv add omcwa
# or
pip install omcwa
```

Editable builds require Python 3.11-3.14 and a C++17 toolchain.

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

The default call:

1. loads the CWA once
2. fits omconvert auto-calibration on the complete first session
3. raises before allocating resampled output if calibration failed
4. resamples with cubic interpolation at the file default rate.

All behavior is configured with primitive options:

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

`time_range=(start, stop)` uses a half-open interval in Unix seconds:
`start <= time < stop`. Calibration and resampling still process the full
session - the range trims the completed output.

## Calibration failures

Strict failure is the default. `CalibrationError` is a `RuntimeError` with the
native omconvert code available as `error.error_code`. The synthetic fixtures
cover the common `-1` (too few stationary points) and `-2` (no usable axis fit)
outcomes.

Use identity fallback only when continuing with uncalibrated acceleration is an
explicit workflow decision:

```python
fallback = process_cwa(
    "recording.cwa",
    on_calibration_failure="identity",
)

if not fallback.calibration.success:
    print(fallback.calibration.error_code)
```

This matches omconvert/OMGUI's numerical fallback: identity coefficients are
applied, while `Calibration.success` stays `False` and the failure code is
preserved.

To skip fitting altogether, use `calibrate=False`. Its returned
`Calibration` is a successful identity calibration with error code `0`.

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

AX3 recordings normally provide acceleration only. AX6 recordings normally
provide acceleration and gyroscope data. Auto-calibration corrects the
accelerometer. Gyroscope values are scaled to physical units.

`load_cwa` materializes a `UniformRecording` at the file rate with identity
calibration:

```python
from omcwa import load_cwa

uniform = load_cwa("recording.cwa")
print(uniform.acc.shape)
print(uniform.temp.shape)
```

Its `acc` and `gyr` units match `ProcessedRecording`. `temp` is `float64`
degrees Celsius. Use `slice_recording` from `omcwa.slice` for ad-hoc half-open
time slices of either public recording type.

## Current limits

- The complete CWA and complete resampled output are materialized in memory.
- `time_range` trims after processing. It does not reduce decode, calibration,
resampling, or peak-memory work.
- Native processing currently selects the first session in a CWA file.
- Version 0.1 makes no deployment-scale or 1 GB recording readiness claim.  
Native windowing and chunked output require a separate design and PR.

## Reproducible tests

Core tests use committed synthetic `omsynth` CWA files under
`tests/fixtures/golden/`. Reference NPZ and JSON oracles were generated with
the OpenMovement `omconvert` pipeline. Tests do not download data, invoke
external binaries, or skip when local recordings are absent.

Fixture provenance, waveform definitions, reference decoding, and the opt-in
regeneration command are documented in
`[tests/fixtures/README.md](tests/fixtures/README.md)`.

Run the development gates with:

```bash
uv sync --group dev
uv run ruff check src tests benchmarks
uv run ruff format --check src tests benchmarks
./scripts/check_cpp_format.sh
uv run pytest -q
```

## Benchmarks

Runtime is measured with `pytest-benchmark` and peak memory is measured
alongside it, both against synthetic CWA recordings that are generated on
demand.

```bash
uv sync --group bench
uv run pytest benchmarks --cwa-hours 10
```

The suite is not part of the default `pytest` run. See
[benchmarks/README.md](benchmarks/README.md) for the options, for how to
compare two branches, and for how the generated recording is built.

The showcase notebook uses the committed `cal_success.cwa` fixture:

```bash
uv sync --group showcase
uv run jupyter lab examples/showcase_omcwa.ipynb
```

## License

**BSD-2-Clause**. See `LICENSE`.

Vendored OpenMovement sources and licenses are documented in
`THIRD_PARTY_NOTICES.md`.