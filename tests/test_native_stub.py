"""``_native.pyi`` describes the extension module the package ships.

A type checker reads the stub and never the compiled module, so a stub
that drifts from ``bridge.cpp`` validates call sites against a signature
that no longer exists.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import omcwa
from omcwa import _native

PACKAGE_DIR = Path(omcwa.__file__).parent
STUB_PATH = PACKAGE_DIR / "_native.pyi"


def _public(names: Iterable[str]) -> set[str]:
    return {name for name in names if not name.startswith("_")}


def _parameters(arguments: ast.arguments) -> list[str]:
    return [
        argument.arg
        for argument in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        )
    ]


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


def _is_property(node: ast.FunctionDef) -> bool:
    return any(
        isinstance(decorator, ast.Name) and decorator.id == "property"
        for decorator in node.decorator_list
    )


def _stub_signatures() -> dict[str, list[str]]:
    """Map every stub callable to its parameter names, keyed by dotted path.

    A ``def_readonly`` field reaches the stub as a property, and its
    ``__doc__`` holds prose rather than a signature line, so properties
    stay out of the map.
    """
    signatures: dict[str, list[str]] = {}
    for node in _stub_body():
        if isinstance(node, ast.FunctionDef):
            signatures[node.name] = _parameters(node.args)
        elif isinstance(node, ast.ClassDef):
            signatures.update(
                {
                    f"{node.name}.{method.name}": _parameters(method.args)
                    for method in node.body
                    if isinstance(method, ast.FunctionDef)
                    and not _is_property(method)
                }
            )
    return signatures


def _runtime_parameters(obj: Any) -> list[str]:
    """Read parameter names off pybind11's signature docstring line."""
    signature = (obj.__doc__ or "").splitlines()[0]
    definition = ast.parse(f"def {signature}: ...").body[0]
    assert isinstance(definition, ast.FunctionDef)
    return _parameters(definition.args)


def _runtime_attribute(dotted: str) -> Any:
    target: Any = _native
    for part in dotted.split("."):
        target = getattr(target, part)
    return target


def test_the_stub_covers_the_module_surface() -> None:
    assert _declared(_stub_body()) == _public(dir(_native))


def test_the_stub_covers_every_class_surface() -> None:
    runtime = {
        name: _public(dir(getattr(_native, name))) for name in _stub_classes()
    }
    assert _stub_classes() == runtime


def test_the_stub_names_the_parameters_the_module_takes() -> None:
    """A renamed ``py::arg`` reaches every call site through the stub."""
    runtime = {
        dotted: _runtime_parameters(_runtime_attribute(dotted))
        for dotted in _stub_signatures()
    }
    assert _stub_signatures() == runtime
