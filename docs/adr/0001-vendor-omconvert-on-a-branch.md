# Vendor omconvert on a branch, not as patch files

`native/vendored/omconvert/` holds OpenMovement's C sources with our local
changes applied directly. Branch `vendor/omconvert` holds an unmodified
upstream snapshot at the same paths, so the local delta is
`git diff vendor/omconvert -- native/vendored/omconvert/` and an upstream
update is an ordinary three-way merge.

## Considered options

A directory of `.patch` files applied at build time. Rejected because patches
have to be kept applying by hand as upstream moves, and the recorded delta can
silently diverge from what is actually in the tree. A branch diff cannot go
stale: it is computed from the two trees rather than replayed from a script.

## Consequences

Moving the upstream pin means committing new sources onto `vendor/omconvert`
and merging, with conflicts arriving as markers in the C files. There is
deliberately no re-vendor script.
