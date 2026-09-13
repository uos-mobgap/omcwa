# Releasing

## The changelog is the record

`CHANGELOG.md` is where a release is written down. No version is tagged before its entry has landed on `main`, so a tag cannot exist that the changelog does not account for.

Write the entry at release time, from the pull requests merged since the last tag. There is no "unreleased" section, because a second place to write things down is a second place for them to go stale.

## The release body is not a second changelog

The GitHub release body is written for whoever opens the release page. It can be shorter than the entry, or warmer, or lead with the one thing that matters. Neither text is copied from the other.

What the body must not do is carry a durable fact the entry does not, or contradict one it does. v0.1.0 shipped with a standalone release-notes document, a release body and a README that disagreed with each other and with the assets actually attached. That is the drift one record exists to prevent.

## Cutting a release

1. Dispatch the wheels workflow with scope `full`. Confirm every leg green and twenty wheels present.
2. Bump the version in the three places `coding-standards.md` lists.
3. Land the changelog entry.
4. Tag, then publish the release so the workflow attaches the wheels.

The order is the point. Tagging before a confirmed green full-matrix run is what shipped v0.1.0 with two failed legs and no CPython 3.14 wheels.

A published tag is never deleted or moved. Whoever already fetched it keeps getting what they fetched.

## Stability

omcwa is 0.x. A minor version may break the API, and a break goes at the top of its changelog entry rather than through a deprecation cycle.

The compatibility calibration path, `calibration_source="player"`, is the one to watch. `adr/0002-ax6-calibration-temperature-offset.md` records that it may be removed if the fix reaches upstream omconvert.

## Support policy

### Python

The supported range is declared in the four places `coding-standards.md` lists. Widen it only after the build legs have produced and imported a wheel for the new interpreter, never in advance. Claiming support for an interpreter nothing was built on is the mistake v0.1.1 corrects.

No date is promised for a new interpreter. NumPy is the gate in practice. Every leg installs NumPy to run its import test under `PIP_ONLY_BINARY=numpy`, so a leg fails until a NumPy wheel exists for the new CPython.

CPython 3.15 reaches its final release on 1 October 2026 ([PEP 790](https://peps.python.org/pep-0790/)). The range stops at 3.14 today, so 3.15 is the next one to go through this.

### Platforms

A platform is dropped when CI can no longer build it on a runner native to its architecture, and the drop is announced in the changelog entry for the release that makes it. `adr/0004-build-wheels-on-native-runners.md` covers why an emulated or cross-compiled leg is not an alternative.

There is no macOS x86_64 wheel and no leg for one. Intel Macs build from source, as the README says. Adding a leg later would mean taking on GitHub's last Intel image, `macos-15-intel`, which retires in August 2027, so that option has a closing date on it.
