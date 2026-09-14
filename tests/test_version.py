"""The three files that declare the version declare the same one."""

from __future__ import annotations

import tomllib
from importlib.metadata import version
from pathlib import Path

import omcwa
from omcwa import _native

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_pyproject_declares_the_package_version() -> None:
    declared = tomllib.loads(PYPROJECT.read_text())["project"]["version"]
    assert declared == omcwa.__version__


def test_the_native_extension_reports_the_package_version() -> None:
    assert _native.version() == omcwa.__version__


def test_the_installed_distribution_reports_the_package_version() -> None:
    assert version("omcwa") == omcwa.__version__
