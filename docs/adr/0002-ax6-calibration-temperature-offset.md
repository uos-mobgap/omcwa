# Read AX6 calibration temperature from its fixed sector offset

omconvert located the temperature used for auto-calibration via the
accelerometer payload offset. That is correct for AX3, whose payload starts at
byte 30, and wrong for AX6, which stores gyroscope axes first and starts its
payload at byte 36. Temperature sits at byte 20 on both devices. We read it
from byte 20 and let AX6 calibrate directly from sectors, which removes a full
interpolating-player pass.

## Consequences

AX6 calibration coefficients differ from stock omconvert. AX3 output is
unchanged. `calibration_source="player"` still selects the original path for
anyone who needs omconvert's exact AX6 numbers.

This patches upstream's algorithm rather than adding a second implementation,
so it is a candidate for upstreaming. We have no contact with the OpenMovement
maintainers and are not resourcing that work; whether it lands upstream does
not gate any omcwa release. If it does land, `player` may be removed in a
later version.
