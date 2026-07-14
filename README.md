# omcwa

**omcwa** loads OpenMovement `.cwa` recordings (accelerometer and optional
gyroscope), applies omconvert-compatible auto-calibration, and resamples streams
to a uniform sample rate. The default backends vendor the OpenMovement
**omconvert** C engine via pybind11, producing output aligned with **omgui**
export behaviour.

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

Requires **Python 3.11–3.14** and a C++17 toolchain for editable builds.

## Quickstart

```python
from omcwa import process_cwa

out = process_cwa("recording.cwa")

print(out.sample_rate_hz)          # file default rate (omgui "auto")
print(out.acc.shape, out.gyr.shape)
print(out.calibration.success)     # auto-cal outcome
print(out.calibration.error_code)  # non-zero when calibration failed
```

`process_cwa` runs auto-calibration on the full on-disk recording (omgui-compatible),
then resamples at the file default rate. Pass an explicit ``sample_rate_hz`` to
target a different rate. Returned arrays are uniformly sampled
`numpy` vectors with optional validity/clipping flags.

## Modular backends

Calibration and resampling are injectable. Pass `None` to skip a stage; pass a
callable to replace the default omconvert backend.

```python
from omcwa import OmConvertCalibrate, OmConvertResample, process_cwa

# Defaults (omgui form: auto-cal + file default rate)
out = process_cwa("recording.cwa")

# Explicit resample rate
out = process_cwa("recording.cwa", sample_rate_hz=100.0)

# Custom backends
out = process_cwa(
    "recording.cwa",
    sample_rate_hz=100.0,
    calibrate_fn=OmConvertCalibrate(stationary_time=15.0),
    resample_fn=OmConvertResample(sample_rate_hz=50.0),
)

# Skip auto-calibration (identity) or resampling
out = process_cwa("recording.cwa", calibrate_fn=None)
out = process_cwa("recording.cwa", resample_fn=None)
```

Custom callables receive typed recording objects (`RawRecording` →
`CalibratedRecording` → `ProcessedRecording`) and must preserve
`metadata["source_path"]` when delegating to native code.

## Calibration behaviour

Auto-calibration searches for stationary segments and fits scale/offset
parameters. When calibration cannot converge—as is common on short recordings—the
engine **falls back to identity correction** but still reports the outcome:

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

Parity tests compare `omgui_test.cwa` against
`omgui_test_autocal_100res.wav` (omgui export: auto-calibrate on, 100 Hz).
Place both under `tests/fixtures/`, or set `OMCWA_FIXTURE_DIR` to a directory
that contains them. CI may run without fixtures; parity tests skip gracefully.

Wheel builds are defined in `.github/workflows/wheels.yml` (cibuildwheel across
Linux, macOS, and Windows for CPython 3.11–3.14).

## License

**BSD-2-Clause** — see `LICENSE`.

Vendored OpenMovement omconvert sources are documented in `THIRD_PARTY_NOTICES.md`.
