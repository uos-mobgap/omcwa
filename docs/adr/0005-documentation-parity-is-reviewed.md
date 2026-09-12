# Documentation parity with the public API is reviewed, not tested

Nothing in the suite reads `README.md` or the showcase notebook.
`tests/test_public_api.py` holds `__all__` to a pinned list of names and
checks that each one resolves. Whether the documentation promises those same
names, and only those, is a question for whoever reviews the change.

v0.1.0 shipped `slice_recording` documented but never exported, which is the
defect this decision has to answer for. A reviewer catches it by reading the
diff. CI does not catch it at all.

## Considered options

Parsing the `from omcwa import ...` lines out of the README's code fences and
the notebook's code cells, then asserting every name is exported. This was
built and it worked: dropping `slice_recording` from `__all__` failed it, and
so did documenting a name that does not exist.

It was rejected for what it costs the rest of the time. The README is among
the most-edited files in the repo, and the test read it on every run. An
early version parsed each fence with `ast`, so a `%matplotlib inline` or a
`>>>` transcript in any snippet failed three tests with a `SyntaxError`.
Matching import lines as text removed that, but not the shape of the problem:
a test that fails when prose changes trains people to stop reading its
failures.

The deeper objection is whose job this is. Documentation parity is a
judgement about whether the docs describe the library honestly. A regex over
import lines only ever checks the names, never the claims around them, so it
buys a fraction of the guarantee at the price of a standing CI dependency on
a file that changes for unrelated reasons.

## Consequences

A name can be documented and unexported again, and the suite will stay green.
Reviewing a change that touches the public API means reading the README
against `__all__`.

The pinned `EXPORTED_NAMES` set is deliberately a copy of `__all__`. It
catches an unintended change to the exported names, and it cannot catch a
documentation drift, which is the whole point of this decision.

Adding a name to the public API is a three-file edit: `__init__.py`,
`tests/test_public_api.py`, and whichever documentation introduces it.
