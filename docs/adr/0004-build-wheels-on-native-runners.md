# Build every wheel on a runner native to its architecture

Each leg of the wheel matrix runs on a runner whose architecture matches the
wheel it builds, so cibuildwheel's import test executes the freshly built
extension module on the chip it targets. `.github/actions/build-wheels` reads
the architecture out of the leg's own build selector and fails the leg before
the build if `runner.arch` disagrees.

## Considered options

QEMU emulation on an x86 runner, and cross-compilation. Both were rejected for
the same reason: cibuildwheel cannot execute a wheel it cannot run, so it skips
the import test and reports the skip in a log line rather than failing. The leg
stays green and publishes a wheel that nothing has imported. An absent wheel
sends a user to a source build; a wheel that fails at `import` sends them
nowhere.

## Consequences

A platform is buildable only while a native runner exists for it. macOS x86_64
has none in this matrix and is not built, so Intel Macs build from source.

The two ARM runner labels carry a version, because GitHub publishes no
`-latest` alias for either image. Their x86 siblings float. That asymmetry is
GitHub's, not a local preference, and the ARM labels need bumping by hand.

Adding a leg means finding a native runner first. Without one the leg cannot
be added under this decision, whatever cibuildwheel would accept.
