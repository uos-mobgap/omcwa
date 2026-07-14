#!/usr/bin/env bash
# Copy OpenMovement omconvert sources into native/vendored/omconvert.
#
# Usage (from repo root):
#   ./scripts/vendor_omconvert.sh
#
# Expects a sibling checkout of the openmovement repo:
#   ../openmovement/Software/AX3/omconvert/
#
# Writes OMCONVERT_VERSION with the upstream git commit and remote URL.
# Does not run clang-format on the vendored tree (keep upstream diffs small).

set -euo pipefail

# paths: omcwa repo root and the upstream omconvert source directory.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(cd "${script_dir}/.." && pwd)"
openmovement_dir="$(cd "${root_dir}/../openmovement" && pwd)"
src_dir="${openmovement_dir}/Software/AX3/omconvert"
dest_dir="${root_dir}/native/vendored/omconvert"

mkdir -p "${dest_dir}"

# copy C sources except main.c (CLI entry point, not needed in the library build)
find "${src_dir}" -maxdepth 1 -name '*.c' ! -name 'main.c' -exec cp {} "${dest_dir}/" \;

# copy public headers from the omconvert directory root
find "${src_dir}" -maxdepth 1 -name '*.h' -exec cp {} "${dest_dir}/" \;

# optional upstream docs/build files, copied only when present
for optional in Makefile README.md; do
    if [[ -f "${src_dir}/${optional}" ]]; then
        cp "${src_dir}/${optional}" "${dest_dir}/"
    fi
done

# upstream BSD licence lives at the openmovement repo root, not under omconvert/
cp "${openmovement_dir}/Software/LICENSE.TXT" "${dest_dir}/LICENSE"

# record the exact upstream revision vendored into this tree
commit="$(git -C "${openmovement_dir}" rev-parse HEAD)"
remote="$(git -C "${openmovement_dir}" remote get-url origin 2>/dev/null || true)"
if [[ -z "${remote}" ]]; then
    remote="https://github.com/openmovementproject/openmovement.git"
fi

# OMCONVERT_VERSION avoids shadowing C++ <version> on case-insensitive FS.
cat > "${dest_dir}/OMCONVERT_VERSION" <<EOF
remote: ${remote}
commit: ${commit}
path: Software/AX3/omconvert
EOF

# remove legacy pin file if a previous vendor run created it
rm -f "${dest_dir}/VERSION"

echo "vendored omconvert at ${commit} into ${dest_dir}"
