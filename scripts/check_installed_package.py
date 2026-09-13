"""Check an installed omcwa for the files a wheel has to carry.

Usage (run against an installed package, not a checkout):
    python scripts/check_installed_package.py

Exits 0 when the package imports and ships its typing marker and native
stub. Exits 1 naming whatever is missing.

cibuildwheel runs this as CIBW_TEST_COMMAND on every leg, in a fresh
environment holding only the wheel it just built.
"""

from __future__ import annotations

import pathlib
import sys

import omcwa

REQUIRED = ("py.typed", "_native.pyi")


def main() -> int:
    package_dir = pathlib.Path(omcwa.__file__).parent
    missing = [name for name in REQUIRED if not (package_dir / name).is_file()]
    if missing:
        print(f"{package_dir} is missing {', '.join(missing)}", file=sys.stderr)
        return 1

    print(f"omcwa {omcwa.__version__} with {', '.join(REQUIRED)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
