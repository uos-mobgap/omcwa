# Local patches to vendored omconvert

`scripts/vendor_omconvert.sh` overwrites `native/vendored/omconvert/` with a
clean upstream copy. These patches are re-applied afterwards so local
performance fixes are not silently lost on the next re-vendor.

Both patches are performance-only. Neither changes numerical output: the
golden-fixture tests in `tests/test_process_parity.py` pass unchanged, and both
were A/B tested on a 931.5 MB AX6 recording with byte-identical results for
`time`, `acc`, `gyr`, `valid`, `clipped`, and all calibration coefficients.

## 0001-omdata-replace-timegm.patch

`OmDataTimestamp()` in `omdata.c` called `timegm()` once per sector per stream.
A 931.5 MB file has ~1.9 M sectors across 3 streams, so ~5.7 M calls.

`timegm()` takes a timezone lock and re-checks the TZ database on every call.
Measured on macOS 15 / Apple M1 Pro: **3051 ns/call**. That alone accounts for
~17 s of a ~17 s `OmDataLoad()`.

Replaced with the standard days-from-civil algorithm (Howard Hinnant, public
domain), measured at **2 ns/call**. CWA timestamps are UTC civil time with no
DST and no leap seconds, so nothing `timegm()` does beyond the arithmetic is
needed here.

Measured on the 931.5 MB file: `OmDataLoad` **16.84 s -> 0.23 s**.

The win is smaller on glibc, whose `timegm()` is faster than Apple's, but the
lock and TZ check are pure overhead on every platform.

## 0002-interpolator-neighbour-cache.patch

`InterpolatorSeek()` in `omconvert.c` re-fetched all four neighbouring source
samples (indices -1, 0, +1, +2) on every output sample, for every stream.
Measured with an instrumented build: **905,044,088 `OmDataGetValues()` calls for
75,420,850 output samples — exactly 12.00 per sample** (3 streams x 4).

Seeks only ever move forwards, so consecutive windows overlap. The patch adds a
4-row sliding cache to `interpolator_t` and shifts the retained rows instead of
re-decoding them.

Measured on the 931.5 MB file: **905 M -> 155 M calls (2.05 per sample)**,
resample stage **7.91 s -> 6.12 s (23% faster)**. The wall-clock gain is much
smaller than the call reduction because the decode itself is cheap; the rest is
per-sample loop overhead.

The cache is only used for a strictly contiguous window. Near segment
boundaries `idx[]` contains clamped duplicates, and there the original full
fetch runs and the cache is invalidated. It is also invalidated when the
interpolator advances to a new segment.

## Re-applying

`scripts/vendor_omconvert.sh` applies these automatically. To do it by hand:

```bash
git apply native/patches/*.patch
```

If a patch stops applying after an upstream change, resolve it against the new
source and regenerate:

```bash
git diff -- native/vendored/omconvert/omdata.c > native/patches/0001-omdata-replace-timegm.patch
```

Both changes are candidates for upstreaming to
https://github.com/openmovementproject/openmovement — if accepted upstream, the
corresponding patch here can be dropped.
