# Vendoring omconvert

`native/vendored/omconvert/` is OpenMovement omconvert at the commit recorded
in `OMCONVERT_VERSION`, plus two local performance changes. The exact delta
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

Both changes are performance-only. Neither changes numerical output. The
golden-fixture tests in `tests/test_process_parity.py` pass unchanged, and both
were A/B tested on a 931.5 MB AX6 recording with byte-identical results for
`time`, `acc`, `gyr`, `valid`, `clipped`, and all calibration coefficients.

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

Both changes are candidates for upstreaming to
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

| tier | what                                    | where it lives             | flag                      |
| ---- | --------------------------------------- | -------------------------- | ------------------------- |
| A    | performance only, byte identical output | `native/vendored/`         | none, always on           |
| B    | changes numbers                         | `native/` outside vendored | runtime flag, default off |
| C    | new algorithms                          | `native/` or `src/omcwa/`  | runtime flag              |

The two local changes above are tier A. Anything that changes numbers or adds
an algorithm belongs outside `native/vendored/`, on omconvert's public API.
