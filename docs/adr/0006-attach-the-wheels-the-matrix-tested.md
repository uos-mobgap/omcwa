# Attach the wheels the matrix tested, and build none on publish

A release carries the wheels from the full-matrix dispatch that
`releasing.md` step 4 confirmed. A maintainer downloads that run's artifacts
and passes them to `gh release create`, so the draft holds twenty wheels from
the moment it exists. `wheels.yml` runs on `workflow_dispatch` and nothing
else.

## Considered options

Building on `release: published`, which is how v0.1.0 shipped. The workflow
triggered on publish, rebuilt every leg, and each leg uploaded its own wheels
to the release.

That ships wheels no green run produced. The dispatch tests twenty, and the
publish run builds twenty more from the same commit on whatever runner images
exist that day. Same source, different compile, and the compile a user
downloads is the one nothing checked. A leg that dies on the publish run
leaves a release already public and missing its assets, and publishing is how
you find out.

A workflow that finds the green run by head SHA and re-uploads its artifacts
reaches the same place without the manual step. It was rejected for its size.
v0.1.0's nine wheels came to 1 MB, so twenty is a two megabyte download.

## Consequences

Publishing attaches nothing and starts nothing.

Nothing in CI forces a release to carry wheels. A maintainer who skips steps 6
and 7 publishes an empty release, and reading the draft is what catches it.

The wheels have to reach the release while the dispatch run still holds its
artifacts. That window is GitHub's retention setting, not something this repo
sets.
