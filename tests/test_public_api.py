"""The package root is the public API.

Every name the documentation tells a user to import comes from ``omcwa``
itself. The documentation is the input here rather than a copy of it: a name
the README promises and ``__init__`` forgets is exactly how
``slice_recording`` stayed documented and unreachable.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import omcwa

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
NOTEBOOK = REPO_ROOT / "examples" / "showcase_omcwa.ipynb"

# Adding a name to the public API means adding it here too, so a new export
# lands as a deliberate edit rather than a surprise.
EXPORTED_NAMES = frozenset(
    {
        "__version__",
        "load_cwa",
        "process_cwa",
        "slice_recording",
        "CalibrationError",
        "Calibration",
        "UniformRecording",
        "ProcessedRecording",
        "InterpolateMode",
        "DEFAULT_SAMPLE_RATE_HZ",
        "DEFAULT_INTERPOLATE",
        "DEFAULT_STATIONARY_TIME",
        "DEFAULT_CALIBRATE",
        "DEFAULT_CALIBRATION_SOURCE",
        "USE_FILE_SAMPLE_RATE",
    }
)


def _python_blocks() -> list[str]:
    """Return every Python snippet the documentation shows a user."""
    blocks = []

    lines = README.read_text(encoding="utf-8").splitlines()
    fence: list[str] | None = None
    for line in lines:
        if fence is None:
            if line.strip() == "```python":
                fence = []
        elif line.strip() == "```":
            blocks.append("\n".join(fence))
            fence = None
        else:
            fence.append(line)

    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    blocks += [
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
    ]

    return blocks


def _documented_imports() -> list[ast.ImportFrom]:
    """Return every ``from omcwa... import ...`` in the documentation."""
    return [
        node
        for block in _python_blocks()
        for node in ast.walk(ast.parse(block))
        if isinstance(node, ast.ImportFrom)
        and (node.module or "").split(".")[0] == "omcwa"
    ]


def test_the_documentation_shows_imports() -> None:
    """Documentation that stopped importing would pass the two tests below."""
    assert _documented_imports() != []


def test_no_documented_import_reaches_into_a_submodule() -> None:
    modules = sorted({node.module for node in _documented_imports()})
    assert modules == ["omcwa"]


def test_every_documented_name_is_exported() -> None:
    documented = sorted(
        {alias.name for node in _documented_imports() for alias in node.names}
    )
    assert [name for name in documented if name not in omcwa.__all__] == []


def test_all_lists_the_exported_names() -> None:
    assert set(omcwa.__all__) == EXPORTED_NAMES


def test_all_has_no_duplicates() -> None:
    assert len(omcwa.__all__) == len(set(omcwa.__all__))


def test_every_listed_name_is_exported() -> None:
    """``from omcwa import *`` would fail on a name that is only listed."""
    assert [name for name in omcwa.__all__ if not hasattr(omcwa, name)] == []
