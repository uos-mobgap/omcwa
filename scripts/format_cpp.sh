#!/usr/bin/env bash
# Apply clang-format to omcwa-owned C++ bridge sources in place.
#
# Usage (from repo root):
#   ./scripts/format_cpp.sh
#
# Scope: native/bridge.cpp, native/omconvert_extern.h, and native/omcwa_defaults.h.
# Vendored omconvert under native/vendored/ is intentionally excluded.
# See docs/coding-standards.md for style rules (.clang-format).

set -euo pipefail

# resolve repo root from this script's location.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(cd "${script_dir}/.." && pwd)"

if ! command -v clang-format >/dev/null 2>&1; then
    echo "clang-format not found; install LLVM clang-format (e.g. brew install clang-format)" >&2
    exit 1
fi

# collect bridge file paths into an array.
# uses a while-read loop instead of mapfile so this works on macOS Bash 3.2.
files=()
while IFS= read -r file; do
    files+=("$file")
done < <(
    find "${root_dir}/native" \
        \( -name 'bridge.cpp' -o -name 'omconvert_extern.h' -o -name 'omcwa_defaults.h' \) \
        -print
)

# -i rewrites each file on disk to match .clang-format at the repo root.
clang-format -i "${files[@]}"
echo "formatted ${#files[@]} files"
