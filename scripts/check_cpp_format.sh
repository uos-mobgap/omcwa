#!/usr/bin/env bash
# CI-style clang-format check for omcwa-owned C++ bridge sources.
#
# Usage (from repo root):
#   ./scripts/check_cpp_format.sh
#
# Exits 0 when every listed file already matches .clang-format.
# Exits 1 on formatting violations or if clang-format is missing.
#
# Scope: native/bridge.cpp, native/omconvert_extern.h, and native/omcwa_defaults.h.
# Vendored omconvert under native/vendored/ is intentionally excluded.

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

if ((${#files[@]} == 0)); then
    echo "no C++ bridge files found" >&2
    exit 1
fi

# --dry-run --Werror: report violations and exit non-zero without modifying files.
clang-format --dry-run --Werror "${files[@]}"
echo "clang-format OK (${#files[@]} files)"
