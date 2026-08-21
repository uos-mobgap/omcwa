# Vendoring omconvert

`native/vendored/omconvert/` is OpenMovement omconvert at the commit recorded
in `OMCONVERT_VERSION`, plus three local changes. The exact delta
against unmodified upstream:

```bash
./scripts/vendor_diff.sh          # full diff
./scripts/vendor_diff.sh --stat   # summary
```

That is `git diff vendor/omconvert -- native/vendored/omconvert/`.

## Why a vendor branch

Branch `vendor/omconvert` holds an unmodified upstream snapshot in the same
paths. The working branch merges from it, so a later upstream update is a
normal three-way merge with conflict markers in the C files.

`git diff vendor/omconvert -- native/vendored/omconvert/` cannot go stale.
It is the live delta, not a replay script you have to keep in sync by hand.

## Local changes

The first two changes are performance-only and leave numerical output
unchanged. The AX6 calibration fix changes coefficients because it replaces an
interpolated scan with the existing direct-data algorithm. The old player scan
remains selectable for compatibility.

### Replace `timegm()` in `omdata.c`

`OmDataTimestamp()` in `omdata.c` called `timegm()` once per sector per stream.
A 931.5 MB file has ~1.9 M sectors across 3 streams, so ~5.7 M calls.

`timegm()` takes a timezone lock and re-checks the TZ database on every call.
On macOS 15 / Apple M1 Pro that is 3051 ns/call. That alone is ~17 s of a
~17 s `OmDataLoad()`.

The replacement is Howard Hinnant's days-from-civil algorithm, public domain,
measured at 2 ns/call. CWA timestamps are UTC civil time with no
DST and no leap seconds, so nothing `timegm()` does beyond the arithmetic is
needed here.

On the 931.5 MB file, `OmDataLoad` went 16.84 s -> 0.23 s.

The win is smaller on glibc, whose `timegm()` is faster than Apple's, but the
lock and TZ check are still wasted work on every platform.

### Neighbour cache in `interpolator_t`

`InterpolatorSeek()` in `omconvert.c` re-fetched all four neighbouring source
samples (indices -1, 0, +1, +2) on every output sample, for every stream.
An instrumented build counted 905,044,088 `OmDataGetValues()` calls for
75,420,850 output samples. That is exactly 12.00 per sample, 3 streams times 4.

Seeks only ever move forwards, so consecutive windows overlap. A 4-row sliding
cache in `interpolator_t` shifts the retained rows instead of re-decoding them.

On the 931.5 MB file that is 905 M -> 155 M calls, 2.05 per sample. Resample
went 7.91 s -> 6.12 s, 23% faster. The wall-clock gain is much
smaller than the call reduction because the decode itself is cheap. The rest is
per-sample loop overhead.

The cache is only used for a strictly contiguous window. Near segment
boundaries `idx[]` contains clamped duplicates. There the original full
fetch runs and the cache is invalidated. It is also invalidated when the
interpolator advances to a new segment.

### Read AX6 calibration temperature from its fixed sector bytes

`OmCalibrateFindStationaryPointsFromData()` used the accelerometer payload
offset as a proxy for temperature availability. That works on AX3, where the
accelerometer payload starts at byte 30. AX6 stores gyroscope axes first, so
its accelerometer payload starts at byte 36. Temperature remains at byte 20
for both devices.

The patch reads temperature from byte 20 for every CWA sector and lets AX6 use
the direct-data path. This removes a full interpolating-player pass during
calibration. Omconvert's existing `-calibrate 2` setting still forces the
player path. The Python API exposes the same choice as
`calibration_source="player"`.

All three changes are candidates for upstreaming to
https://github.com/openmovementproject/openmovement. If they land upstream,
the corresponding delta here disappears on the next merge from
`vendor/omconvert`.

## Updating upstream

There is no re-vendor script. `vendor/omconvert` is a pin of unmodified
omconvert at the `OMCONVERT_VERSION` commit, and the working branch is not
overwritten from a sibling checkout.

If that pin ever has to move, copy the new upstream sources onto
`vendor/omconvert` at the same paths under `native/vendored/omconvert/`, commit
there, and `git merge vendor/omconvert` into the working branch. Conflicts
arrive as markers in the C files. Then `./scripts/vendor_diff.sh --stat` to
confirm the local delta is still only the two performance changes, or the
subset that has not landed upstream.

## What belongs in the vendored tree

| tier | what                                      | where it lives            | compatibility             |
| ---- | ----------------------------------------- | ------------------------- | ------------------------- |
| A    | performance only, byte-identical output   | `native/vendored/`        | none needed               |
| B    | focused upstream fix that changes numbers | `native/vendored/`        | keep old path selectable  |
| C    | new algorithm                             | `native/` or `src/omcwa/` | runtime option            |

The timestamp and interpolator changes are tier A. The AX6 calibration fix is
tier B. It patches the existing algorithm rather than maintaining a second
copy, while the player option preserves the old result when needed.
