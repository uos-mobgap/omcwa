# Releasing

## The changelog is the record

`CHANGELOG.md` carries an entry for every released version. No version is tagged before its entry has landed on `main`.

Write the entry at release time, from the pull requests merged since the last tag. There is no "unreleased" section.

## The release body

The GitHub release body is written for the release page. It is not copied from the changelog, and the changelog is not copied from it. It must not carry a durable fact the entry does not, or contradict one the entry does.

## Cutting a release

1. Bump the version in the three places `coding-standards.md` lists.
2. Land the changelog entry.
3. Dispatch the wheels workflow with scope `full` against the commit to be tagged. Confirm every leg green and twenty wheels present.
4. Tag that commit.
5. Create the release.

No tag is created before a full-matrix run on the commit being tagged has been confirmed green with twenty wheels.

A published tag is never deleted or moved.

## Stability

omcwa is 0.x. A minor version may break the API, and a break goes at the top of its changelog entry rather than through a deprecation cycle.

## Support policy

### Python

The supported range is declared in the four places `coding-standards.md` lists. Widen it only after the build legs have produced and imported a wheel for the new interpreter, never in advance.

No date is promised for a new interpreter. NumPy is the gate in practice. Every leg installs NumPy to run its import test under `PIP_ONLY_BINARY=numpy`, so a leg fails until a NumPy wheel exists for the new CPython.

CPython 3.15 reaches its final release on 1 October 2026 ([PEP 790](https://peps.python.org/pep-0790/)). The supported range stops at 3.14.

### Platforms

A platform is dropped when CI can no longer build it on a runner native to its architecture, and the drop is announced in the changelog entry for the release that makes it. See `adr/0004-build-wheels-on-native-runners.md`.

There is no macOS x86_64 wheel and no leg for one. Intel Macs build from source, as the README says. GitHub's last Intel image, `macos-15-intel`, retires in August 2027.
