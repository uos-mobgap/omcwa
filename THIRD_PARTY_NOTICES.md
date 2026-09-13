# Third-party notices

## OpenMovement omconvert

`native/vendored/omconvert/` contains C sources vendored from the
[Open Movement](https://github.com/openmovementproject/openmovement) project.

Upstream path: `Software/AX3/omconvert`
License: BSD-2-Clause, in `native/vendored/omconvert/LICENSE`
Pinned version: `native/vendored/omconvert/OMCONVERT_VERSION`
Local changes: three edits against that pin. See `native/VENDORING.md`.

Copyright (c) 2009-2026, Newcastle University (UK) and Open Movement project
contributors.

## Microsoft Visual C++ runtime

From v0.1.1 every Windows wheel carries one file from the Microsoft Visual C++
runtime:

```
omcwa.libs/msvcp140-<hash>.dll
```

[delvewheel](https://github.com/adang1345/delvewheel) copies it in during the
wheel repair step and renames it, so that it cannot collide with another
package's copy of the same DLL. Without it the extension imports only on a
machine that already has the Visual C++ redistributable installed.

The file is not in this repository. It comes from the Visual Studio build
tools on the GitHub-hosted Windows runner that built the wheel. Redistribution
is permitted under the Distributable Code terms of the Microsoft Visual Studio
license, which name the Visual C++ runtime files as redistributable.

Copyright (c) Microsoft Corporation. All rights reserved.
