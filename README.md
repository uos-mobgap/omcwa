# omcwa

**omcwa** loads OpenMovement `.cwa` recordings from **AX3**/**AX6** devices, applies omconvert-compatible
auto-calibration, and resamples streams to a uniform sample rate. The default
backends vendor the OpenMovement **omconvert** C engine via pybind11, producing
output aligned with **omgui** export behaviour.

## Install

Published wheels (once available):

```bash
pip install omcwa
# or
uv add omcwa
```

From a local checkout:

```bash
git clone <repository-url>
cd omcwa
uv sync
```

Requires Python 3.11-3.14 and a C++17 toolchain for editable builds.

## Quickstart

```python
from omcwa import load_cwa, process_cwa

out = process_cwa("recording.cwa")

print(out.sample_rate_hz)          # file default rate (omgui "auto")
print(out.acc.shape)

if out.gyr is not None:            # AX6, none on AX3
    print(out.gyr.shape)

print(out.calibration.success)     # auto-cal outcome
print(out.calibration.error_code)  # non-zero when calibration failed

uniform = load_cwa("recording.cwa")
print(uniform.temp.shape)          # temperature (C), used during accel calibration
```

`process_cwa` runs auto-calibration on the full on-disk recording (omgui-compatible),
then resamples at the file default rate. Pass an explicit `sample_rate_hz` to
target a different rate. Pass `time_range=(start, stop)` to trim output after
processing (auto-calibration still uses the full file). Returned arrays are
uniformly sampled `numpy` vectors with optional validity/clipping flags.

For ad-hoc windows on any recording type, use `slice_recording` from
`omcwa.slice` (`start <= time < stop`).

### Naming

| Type | Meaning |
|------|---------|
| **`UniformRecording`** | Uncalibrated (identity / pre-cal) samples on a uniform grid at the file default rate |
| **`CalibratedRecording`** | Auto-calibrated (or identity) samples, still at the file default rate |
| **`ProcessedRecording`** | Final resampled output from `process_cwa` |

`load_cwa` returns a **`UniformRecording`**. That
stage is uncalibrated float64 data, not raw device packets.

### AX3 vs AX6

| Device | Streams in output |
|--------|-------------------|
| **AX3** | `acc` |
| **AX6** | `acc`, `gyr` |

Auto-calibration fits accelerometer scale/offset (with temperature correction).
Gyro is rescaled but not auto-calibrated.

## Examples

To run [`examples/showcase_omcwa.ipynb`](examples/showcase_omcwa.ipynb), install the
showcase dependencies first:

```bash
uv sync --group showcase
# or with pip from a checkout:
pip install -e ".[showcase]"
```

### Temperature

Temperature is read from the CWA and used during accelerometer calibration.
It is exposed on **`UniformRecording`** and **`CalibratedRecording`** (e.g. via
`load_cwa()` or injectable pipeline stages). The high-level **`ProcessedRecording`**
returned by `process_cwa()` does not include a temperature array. It keeps
`acc`, `gyr`, timing, and calibration metadata only.

## File handles and loading

`open_cwa(path)` returns a **`CwaHandle`** that loads the file once into native
memory. Reuse the handle across pipeline stages so calibrate and resample do not
reload the CWA.

`load_cwa(path)` is a convenience wrapper around `open_cwa(path).materialize()`.
It returns a **`UniformRecording`** at the file default rate with identity
calibration (uncalibrated float64 samples).

```python
from omcwa import open_cwa, load_cwa

handle = open_cwa("recording.cwa")
uniform = handle.materialize()   # same as load_cwa("recording.cwa")
```

## Modular backends

Calibration and resampling are injectable. Pass `None` to skip a stage. Pass a
callable to replace the default omconvert backend.

```python
from omcwa import OmConvertCalibrate, OmConvertResample, process_cwa

# Defaults (omgui form: auto-cal + file default rate)
out = process_cwa("recording.cwa")

# Explicit resample rate
out = process_cwa("recording.cwa", sample_rate_hz=100.0)

# Trim output after processing (auto-cal still uses the full file)
out = process_cwa("recording.cwa", time_range=(start, stop))

# Custom backends
out = process_cwa(
    "recording.cwa",
    calibrate_fn=OmConvertCalibrate(stationary_time=15.0),
    resample_fn=OmConvertResample(sample_rate_hz=50.0),
)

# Skip auto-calibration (identity) or resampling
out = process_cwa("recording.cwa", calibrate_fn=None)
out = process_cwa("recording.cwa", resample_fn=None)
```

Custom callables must match the `CalibrateFn` and `ResampleFn` shapes
(`UniformRecording -> CalibratedRecording` and
`CalibratedRecording -> ProcessedRecording`). Return valid recording instances
with consistent arrays. Keep `path` set to the on-disk CWA path when the next
stage is an omconvert backend.

When chaining into `OmConvertResample`, set `metadata["_native_calibration"]`
to a native calibration object (as `OmConvertCalibrate` and
`uniform_to_calibrated_identity` do). Omconvert backends reuse
`metadata["_cwa_handle"]` when present. If the handle is missing, they load
from `recording.path`.

Those two keys are pipeline-only. They are dropped when building a
**`ProcessedRecording`**, so the final result does not keep the native file
buffer alive.

`OmConvertCalibrate(..., apply_to_arrays=False)` fits calibration and stores
`_native_calibration` without rewriting accel arrays. `process_cwa` uses that
when both stages are OmConvert on the slow path, because
`OmConvertResample` applies calibration during the player pass.

### Fast path

When `calibrate_fn` and `resample_fn` are each `OmConvertCalibrate`,
`OmConvertResample`, or `None`, `process_cwa` uses a single native `process`
call (or one materialize when both stages are skipped). Any combination of
those backends qualifies, including non-default `stationary_time` or
`sample_rate_hz`.

If `OmConvertCalibrate` and `OmConvertResample` disagree on `interpolate`,
processing falls through to the slower injectable path.

## Calibration behaviour

Auto-calibration searches for stationary segments and fits scale/offset
parameters. When calibration cannot converge (as is common on short recordings),
the engine **falls back to identity correction** but still reports the outcome:

- `Calibration.success` is `False`
- `Calibration.error_code` is non-zero

Callers should inspect these fields rather than assuming a successful fit.
Identity fallback keeps pipelines running while making failure observable.

## Native backend

Default `OmConvertCalibrate` and `OmConvertResample` wrap vendored omconvert
sources under `native/vendored/omconvert/`. The pybind11 module `omcwa._native`
loads CWA files, runs auto-calibration, and performs interpolation/resampling
identically to the reference desktop tooling.

## Development

```bash
uv sync --group dev
uv run ruff check src tests    # python lint
uv run ruff format src tests   # python format
./scripts/check_cpp_format.sh  # c++ format check
./scripts/format_cpp.sh        # c++ auto-format
uv run pytest -q
```

Coding standards (Python + C++): [docs/coding-standards.md](docs/coding-standards.md).

Parity tests compare `omgui_test.cwa` (AX6 fixture) against
`omgui_test_autocal_100res.wav` (omgui export: auto-calibrate on, 100 Hz).
Place both under `tests/fixtures/`, or set `OMCWA_FIXTURE_DIR` to a directory
that contains them. CI may run without fixtures. Parity tests skip gracefully.

Wheel builds are defined in `.github/workflows/wheels.yml` (cibuildwheel across
Linux, macOS, and Windows for CPython 3.11-3.14).

## License

**BSD-2-Clause**. See `LICENSE`.

Vendored OpenMovement omconvert sources are documented in `THIRD_PARTY_NOTICES.md`.
