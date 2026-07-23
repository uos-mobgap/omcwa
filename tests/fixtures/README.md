# Synthetic CWA fixtures

The files in `golden/` are deterministic `omsynth` recordings. They contain no
participant or device data and are small enough to run in every CI checkout.

## Provenance

The fixtures exercise four outcomes:

- `resample_only.cwa`: five seconds of known sinusoidal accel and gyro data.
- `cal_success.cwa`: eight stationary orientations and a successful fit.
- `cal_failure.cwa`: too few stationary windows, calibration error `-1`.
- `cal_failure_no_axis.cwa`: no usable axis diversity, error `-2`.

The NPZ files contain physical-unit accel and gyro arrays decoded from the
reference WAV output. WAV `int16` values are converted with the omconvert
contract `physical = int16 * (2 * Scale-N) / 65536` (see
`native/vendored/omconvert/README.md`, "Importing the WAV file", and
`native/vendored/omconvert/omdata.c`). Decoding is implemented in
`tests/fixtures/regen_golden.py` (`_decode_wav`). The JSON file contains
the calibration coefficients reported by `omconvert -info`.

## Regeneration

Regeneration is opt-in and is never run by tests. Build or obtain the
OpenMovement `omsynth` and `omconvert` executables, then run from the repository
root:

```bash
uv run python tests/fixtures/regen_golden.py \
  --omsynth /path/to/omsynth \
  --omconvert /path/to/omconvert
```

The script recreates all artifacts in a temporary directory, verifies the  
expected calibration result codes, and replaces `golden/` only after every  
command succeeds.