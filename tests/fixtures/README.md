# Synthetic CWA fixtures

The files in `golden/` are deterministic `omsynth` recordings. No participant
or device data. Small enough for every CI checkout.

## Provenance

Four outcomes:

- `resample_only.cwa`: five seconds of known sinusoidal accel and gyro data.
- `cal_success.cwa`: eight stationary orientations and a successful fit.
- `cal_failure.cwa`: too few stationary windows, calibration error `-1`.
- `cal_failure_no_axis.cwa`: no usable axis diversity, error `-2`.

The NPZ files hold physical-unit accel and gyro arrays decoded from the
reference WAV. WAV `int16` values convert with
`physical = int16 * (2 * Scale-N) / 65536`. See
`native/vendored/omconvert/README.md`, "Importing the WAV file", and
`native/vendored/omconvert/omdata.c`. Decoding lives in
`tests/fixtures/regen_golden.py` (`_decode_wav`). The JSON file holds
the calibration coefficients from `omconvert -info`.

## Regeneration

Opt-in. Tests never run this. Build or obtain the OpenMovement `omsynth` and
`omconvert` executables, then from the repository root:

```bash
uv run python tests/fixtures/regen_golden.py \
  --omsynth /path/to/omsynth \
  --omconvert /path/to/omconvert
```

The script rebuilds everything in a temporary directory, checks the expected
calibration result codes, and replaces `golden/` only after every command
succeeds.
