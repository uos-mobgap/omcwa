"""The package root is the public API.

Every name the documentation tells a user to import comes from ``omcwa``
itself. The documentation is the input here rather than a copy of it. A
name the README promises and ``__init__`` forgets is exactly how
``slice_recording`` stayed documented and unreachable.
"""

from __future__ import annotations

import json
import re
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


# A ``from omcwa... import ...`` statement, in both the one-line and the
# parenthesised form. Matched as text rather than parsed. A snippet is not
# always a whole valid module, and a notebook magic or an abbreviated
# example must not turn into a failure about the public API.
_IMPORT = re.compile(
    r"^[ \t]*from[ \t]+(omcwa[\w.]*)[ \t]+import[ \t]+(\([^)]*\)|[^\n]+)",
    re.MULTILINE,
)


def _python_blocks() -> list[str]:
    """Return every Python snippet the documentation shows a user."""
    blocks = []

    fence: list[str] | None = None
    for line in README.read_text(encoding="utf-8").splitlines():
        if fence is None:
            if line.strip().startswith("```py"):
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


def _documented_imports() -> list[tuple[str, list[str]]]:
    """Return the module and imported names of each documented import."""
    imports = []
    for block in _python_blocks():
        for module, tail in _IMPORT.findall(block):
            names = [
                name.split(" as ")[0].strip()
                for name in tail.strip("()").split(",")
            ]
            imports.append((module, [name for name in names if name]))
    return imports


def test_the_documentation_shows_imports() -> None:
    """Documentation that stopped importing would pass the two tests below."""
    assert _documented_imports() != []


def test_no_documented_import_reaches_into_a_submodule() -> None:
    assert sorted({module for module, _ in _documented_imports()}) == ["omcwa"]


def test_every_documented_name_is_exported() -> None:
    documented = sorted(
        {name for _, names in _documented_imports() for name in names}
    )
    assert [name for name in documented if name not in omcwa.__all__] == []


def test_all_lists_the_exported_names() -> None:
    assert set(omcwa.__all__) == EXPORTED_NAMES


def test_all_has_no_duplicates() -> None:
    assert len(omcwa.__all__) == len(set(omcwa.__all__))


def test_every_listed_name_is_exported() -> None:
    """``from omcwa import *`` would fail on a name that is only listed."""
    assert [name for name in omcwa.__all__ if not hasattr(omcwa, name)] == []
