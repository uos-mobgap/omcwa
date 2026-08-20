# Coding standards

## Python (`src/omcwa/`, `tests/`)

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```bash
uv sync --group dev
uv run ruff check src tests
uv run ruff format src tests
```

Settings are in `pyproject.toml` under `[tool.ruff]`.

**Conventions**

- Public functions and classes need short, formal docstrings.
- Public APIs need type hints.

**Defaults**

Pipeline defaults live in `src/omcwa/defaults.py` (`InterpolateMode`,
`DEFAULT_*`, `USE_FILE_SAMPLE_RATE`). Keep them in sync with
`native/omcwa_defaults.h`.

## C++ (`native/bridge.cpp`, `native/omconvert_extern.h`, `native/omcwa_defaults.h`)

We use [clang-format](https://clang.llvm.org/docs/ClangFormat.html) (LLVM style, 4-space indent, 80-column limit). See `.clang-format`.

```bash
./scripts/check_cpp_format.sh   # CI-style check
./scripts/format_cpp.sh         # auto-format bridge sources
```

**Scope**

Only format omcwa-owned bridge files. Do not clang-format `native/vendored/omconvert/`. That folder is an upstream snapshot plus the local performance changes documented in `native/VENDORING.md`.

**Conventions**

- `bridge.cpp` is a thin adapter. It calls vendored C APIs and packs numpy/pybind types.
- pybind11 exported APIs need docstrings via `R"doc(...)doc"` so `help()` works.
- Default argument values come from `native/omcwa_defaults.h` (keep in sync with
  `src/omcwa/defaults.py`).
- Comments that document omconvert behaviour end with a `ref:` line pointing at
  `vendored/omconvert/...`.

**clang-tidy**

Not enforced yet.

## Package version

`0.1.0` is declared in three places. Bump them together:

- `pyproject.toml` -> `[project].version`
- `src/omcwa/__init__.py` -> `__version__`
- `native/bridge.cpp` -> `_native.version()`

Vendored omconvert is pinned separately in `native/vendored/omconvert/OMCONVERT_VERSION` (git commit SHA).