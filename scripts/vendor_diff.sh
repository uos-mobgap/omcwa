#!/usr/bin/env bash
# Print every local change to the vendored omconvert tree.
set -euo pipefail
root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if git -C "${root_dir}" rev-parse --verify --quiet vendor/omconvert >/dev/null; then
    upstream_ref="vendor/omconvert"
elif git -C "${root_dir}" rev-parse --verify --quiet origin/vendor/omconvert >/dev/null; then
    upstream_ref="origin/vendor/omconvert"
else
    echo "ERROR: branch vendor/omconvert is missing." >&2
    echo "See native/VENDORING.md for the vendor-branch workflow." >&2
    exit 1
fi

echo "Local changes to native/vendored/omconvert vs upstream"
echo "upstream pin: $(git -C "${root_dir}" show "${upstream_ref}":native/vendored/omconvert/OMCONVERT_VERSION | tr '\n' ' ')"
echo
git -C "${root_dir}" diff --stat "${upstream_ref}" -- native/vendored/omconvert/
echo
git -C "${root_dir}" diff "$@" "${upstream_ref}" -- native/vendored/omconvert/
