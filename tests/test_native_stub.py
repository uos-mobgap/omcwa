"""``_native.pyi`` describes the extension module the package ships.

The stub is the only description of the native surface a type checker
sees, and nothing at build time compares it to the compiled module. These
tests do, in both directions, over every public name.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

import omcwa
from omcwa import _native

PACKAGE_DIR = Path(omcwa.__file__).parent
STUB_PATH = PACKAGE_DIR / "_native.pyi"


def _public(names: Iterable[str]) -> set[str]:
    return {name for name in names if not name.startswith("_")}


def _declared(body: list[ast.stmt]) -> set[str]:
    """Return the public classes, functions and fields declared in ``body``."""
    names: set[str] = set()
    for node in body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.AnnAssign) and isinstance(
            node.target, ast.Name
        ):
            names.add(node.target.id)
    return _public(names)


def _stub_body() -> list[ast.stmt]:
    return ast.parse(STUB_PATH.read_text(encoding="utf-8")).body


def _stub_classes() -> dict[str, set[str]]:
    return {
        node.name: _declared(node.body)
        for node in _stub_body()
        if isinstance(node, ast.ClassDef)
    }


def test_the_package_is_marked_typed() -> None:
    assert (PACKAGE_DIR / "py.typed").is_file()


def test_the_stub_sits_beside_the_package() -> None:
    assert STUB_PATH.is_file()


def test_the_stub_covers_the_module_surface() -> None:
    assert _declared(_stub_body()) == _public(dir(_native))


def test_the_stub_covers_every_class_surface() -> None:
    runtime = {
        name: _public(dir(getattr(_native, name))) for name in _stub_classes()
    }
    assert _stub_classes() == runtime
