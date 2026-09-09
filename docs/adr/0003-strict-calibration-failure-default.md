# Raise on calibration failure by default

omconvert silently substitutes an identity calibration when auto-calibration
fails. omcwa raises `CalibrationError` instead, before any resampled output is
allocated, so a failed fit cannot be mistaken downstream for a successful one.

## Consequences

This is a behavioural break from omconvert that anyone porting from it will
hit on their first bad recording. `on_calibration_failure="identity"` restores
the original behaviour, keeping the native code on `Calibration.error_code`
and leaving `Calibration.success` false.
