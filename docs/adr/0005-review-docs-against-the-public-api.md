# Keep the docs and the public API in agreement by review, not by test

`tests/test_public_api.py` pins `__all__` to a list of names and checks that
each one resolves. No test reads `README.md` or the showcase notebook.
Keeping the documentation and `__all__` in agreement is the job of whoever
reviews a change to the public API.

v0.1.0 documented `slice_recording` and left it out of `__all__`, so the only
way to reach a documented function was to import `omcwa.slice`, a module the
package treats as internal. That is the defect this decision has to answer
for. Nothing in CI would catch the same thing happening again.

## Considered options

A test that reads the `from omcwa import ...` lines out of the README's code
fences and the notebook's code cells, then asserts every name is exported. It
works. Dropping a name from `__all__` fails it, and so does documenting a
name that does not exist.

What it costs is a permanent CI dependency on the file this repo edits most.
Parsing each fence as a Python module makes that worse, because a
`%matplotlib inline` or a `>>>` transcript in an unrelated snippet fails the
test with a `SyntaxError`. Matching the import lines as plain text avoids
the crash and still leaves a test that goes red when someone rewrites prose.

A test like that also buys less than it looks. It compares names. Whether the
README describes what a function does is the half of the job that needs a
reader.

## Consequences

A name can go documented and unexported again, and the suite will stay green.

Adding a name to the public API is a three-file edit. `__init__.py`,
`tests/test_public_api.py`, and whichever documentation introduces it.

`EXPORTED_NAMES` in `tests/test_public_api.py` is a copy of `__all__` on
purpose. It catches a change to the exported names that nobody meant to make.
It cannot catch documentation drift, and it is not there to.
