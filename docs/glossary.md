# omcwa

Loading OpenMovement `.cwa` recordings from AX3 and AX6 devices into uniform
NumPy arrays.

## Language

**Recording**:
One continuous capture from a single device, as stored in a `.cwa` file.
_Avoid_: file, dataset, trial

**Session**:
A block of contiguous samples within a recording. A recording may hold
several; omcwa processes the first.
_Avoid_: segment, block, run

**Uniform recording**:
A recording decoded and resampled onto an evenly spaced time grid, with no
calibration fitted.
_Avoid_: raw recording, loaded recording

**Processed recording**:
A uniform recording with a fitted accelerometer calibration applied.
_Avoid_: calibrated recording, output recording

**Calibration source**:
Where the temperature series used to fit calibration is read from. `data`
reads it from the recording's own sectors; `player` reproduces omconvert's
original interpolating pass.
_Avoid_: calibration mode, temperature source

**Identity calibration**:
A calibration that leaves acceleration unchanged. Used when fitting is
skipped, and as the fallback when a fit fails.
_Avoid_: null calibration, no-op calibration
