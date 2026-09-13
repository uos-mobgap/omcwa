# Coding standards

## Python (`src/omcwa/`, `tests/`, `scripts/`)

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting, and [mypy](https://mypy.readthedocs.io/) for type checking.

```bash
uv sync --group dev
uv run ruff check src tests scripts
uv run ruff format src tests scripts
uv run mypy
```

Settings are in `pyproject.toml` under `[tool.ruff]` and `[tool.mypy]`.

### Conventions

- Public functions and classes need short, formal docstrings.
- Public APIs need type hints.
- `src/omcwa/py.typed` publishes those hints. mypy runs strict over `src/omcwa` and stays clean.
- No public return type is `Any`. `metadata: dict[str, Any]` is the one exception.
- `tests/typing/` holds type-level checks of the public API. mypy is their runner. pytest collects nothing there.
- Every wheel carries `py.typed` and `_native.pyi`. `scripts/check_installed_package.py` asserts both, as the cibuildwheel test command on every leg.

### Defaults

Pipeline defaults live in `src/omcwa/defaults.py` (`InterpolateMode`, the
`CalibrationFailurePolicy`, `CalibrationSource` and `Dtype` aliases,
`DEFAULT_*`, `USE_FILE_SAMPLE_RATE`). Keep them in sync with
`native/omcwa_defaults.h`.

Every `DEFAULT_*` carries a `Final` annotation naming the type its parameter
accepts.

## C++ (`native/bridge.cpp`, `native/omconvert_extern.h`, `native/omcwa_defaults.h`)

We use [clang-format](https://clang.llvm.org/docs/ClangFormat.html) with LLVM
style, 4-space indent, 80-column limit. See `.clang-format`.

```bash
./scripts/check_cpp_format.sh   # CI-style check
./scripts/format_cpp.sh         # auto-format bridge sources
```

### Scope

Only format omcwa-owned bridge files. Leave `native/vendored/omconvert/`
alone. That folder is an upstream snapshot plus the local performance
changes in `native/VENDORING.md`.

### Conventions

- `bridge.cpp` is a thin adapter. It calls vendored C APIs and packs numpy/pybind types.
- pybind11 exported APIs need docstrings via `R"doc(...)doc"` so `help()` works.
- Default argument values come from `native/omcwa_defaults.h`. Keep that file
  in sync with `src/omcwa/defaults.py`.
- Comments that document omconvert behaviour end with a `ref:` line pointing at
  `vendored/omconvert/...`.
- A name exported from `PYBIND11_MODULE` needs an entry in
  `src/omcwa/_native.pyi`. `tests/test_native_stub.py` compares the two in
  both directions.

### clang-tidy

Not enforced yet.

## Package version

`0.1.0` is declared in three places. Bump them together, following `releasing.md`:

- `pyproject.toml` -> `[project].version`
- `src/omcwa/__init__.py` -> `__version__`
- `native/bridge.cpp` -> `_native.version()`

Vendored omconvert is pinned separately in
`native/vendored/omconvert/OMCONVERT_VERSION` (git commit SHA).

## Licence files

Every wheel ships the licence text for each piece of code inside it, listed in `pyproject.toml` under `[project].license-files`:

- `LICENSE`, omcwa's own
- `THIRD_PARTY_NOTICES.md`, covering vendored omconvert and the Microsoft Visual C++ runtime DLL that delvewheel copies into the Windows wheels
- `native/vendored/omconvert/LICENSE`

Declaring the list turns off scikit-build-core's default globs, so a new licence or notice file at the root ships only once it is added here.

`README.md` points readers at the same paths under License. Nothing checks that the two agree, so change them together.

## Supported Python versions

The supported range is declared in five places. Change them together:

- `pyproject.toml` -> `[project].requires-python`
- `pyproject.toml` -> `[tool.mypy].python_version`, pinned to the oldest supported interpreter
- `.github/workflows/wheels.yml` -> `PYTHON_TAGS` in the `legs` job
- `.github/workflows/wheels.yml` -> the `cp3{...}` selector on every leg
- `README.md` -> the interpreter list under Install

Each leg checks the wheels it produced against `PYTHON_TAGS`. A selector that
matches fewer versions than expected fails the build rather than shipping a
gap, and adding a version without updating `PYTHON_TAGS` fails the same check.
The README is the one site nothing checks, so it is the one to change first.

## Build legs

The leg list is the `legs` array in `.github/workflows/wheels.yml`. Every leg
runs on a runner native to the architecture it builds, and the build action
fails a leg placed on a foreign runner. A new leg therefore needs a native
runner before anything else. See
`docs/adr/0004-build-wheels-on-native-runners.md`.

Adding or dropping a leg also changes the platform list in `README.md` under
Install.
