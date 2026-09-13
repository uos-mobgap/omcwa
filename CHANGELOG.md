# Changelog

Every released version has an entry here. Breaking changes come first in an
entry, under their own heading, so an upgrade decision does not depend on
reading to the end.

omcwa is 0.x, so a minor version may break the API. `docs/releasing.md` holds
the release process and the support policy for platforms and interpreters.

## 0.1.0 (2026-08-23)

First release, published as a pre-release. omcwa loads OpenMovement `.cwa`
recordings from AX3 and AX6 devices and resamples them to uniform NumPy
arrays. Decoding and calibration run omconvert's own C code, vendored, not a
Python reimplementation.

### AX6 calibration differs from stock omconvert

Stock omconvert located calibration temperature using the accelerometer
payload offset. That is correct for AX3, where the payload starts at byte 30,
and wrong for AX6, which stores gyro axes first and starts the payload at byte
36. The bug pushed AX6 through a slow interpolating "player" pass to get a
usable fit.

The default `calibration_source="data"` reads temperature from its real
offset, byte 20 on both devices, and calibrates AX6 straight from CWA sectors.
AX6 coefficients therefore differ from stock omconvert. AX3 output is
unchanged. Pass `calibration_source="player"` to reproduce omconvert's
original AX6 numbers.

### API

- `process_cwa(path, ...)` loads, calibrates, and resamples in one call,
returning a `ProcessedRecording`.
- `load_cwa(path)` loads and resamples at the file rate with identity
calibration.
- `dtype="float32"` halves `acc`/`gyr` memory. `time` stays `float64`.
- `time_range=(start, stop)` trims the output. Calibration and resampling
still run on the full session.
- `CalibrationError` carries the native `error_code` and raises before any
resampled output is allocated. `on_calibration_failure="identity"` falls
back the way omconvert does.

### Performance

On a 931.5 MB AX6 file on a MacBook M1 Pro 16GB:

- Load: 16.84 s to 0.23 s, replacing a per-sector `timegm()` call with
days-from-civil arithmetic.
- Resample: 7.91 s to 6.12 s, from a 4-row neighbour cache in the
interpolator that cut `OmDataGetValues()` calls from 905M to 155M.

The extension also releases the GIL around the native load and calibration
loops, and derives `recording.time` from `start_time` instead of storing it,
saving one array per recording. Details in `native/VENDORING.md`.

### Wheels

The release carries nine wheels: Linux x86_64, macOS arm64 and Windows amd64,
for CPython 3.11, 3.12 and 3.13. Its own notes promised twenty, across five
platforms and CPython 3.11 to 3.14. Two build legs failed and the 3.14
selector matched nothing. Anything not on that list builds from source.

### Limits

- The whole CWA and the whole resampled output sit in memory.
- Only the first session in a CWA file is processed.
