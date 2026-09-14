"""Check an installed omcwa for the files and version a wheel must carry.

Usage (run against an installed package, not a checkout):
    python scripts/check_installed_package.py

Exits 0 when the package imports, ships its typing marker and native
stub, and reports one version from all three places that declare it.
Exits 1 naming whatever is wrong.

cibuildwheel runs this as CIBW_TEST_COMMAND on every leg, in a fresh
environment holding only the wheel it just built.
"""

from __future__ import annotations

import pathlib
import sys
from importlib.metadata import version

import omcwa
from omcwa import _native

REQUIRED = ("py.typed", "_native.pyi")


def main() -> int:
    package_dir = pathlib.Path(omcwa.__file__).parent
    missing = [name for name in REQUIRED if not (package_dir / name).is_file()]
    if missing:
        print(f"{package_dir} is missing {', '.join(missing)}", file=sys.stderr)
        return 1

    versions = {
        "__version__": omcwa.__version__,
        "_native.version()": _native.version(),
        "distribution metadata": version("omcwa"),
    }
    if len(set(versions.values())) != 1:
        reported = ", ".join(f"{k} {v}" for k, v in versions.items())
        print(f"{package_dir} reports {reported}", file=sys.stderr)
        return 1

    print(f"omcwa {omcwa.__version__} everywhere, with {', '.join(REQUIRED)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
