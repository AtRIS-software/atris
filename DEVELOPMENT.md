# Development Towards Version 3.0

Version 3.0 should simplify the repository and make AtRIS easier to build,
understand, test, and run. Structural work should not change scientific or
numerical behaviour unless that change is explicitly documented and validated.

## Goals

The goals for version 3.0 are:

- Make the repository root the clear entry point for building and using AtRIS.
- Remove the confusing nested `atris/atris` naming.
- Give source code, runtime data, development data, tools, examples, tests, and
  documentation clear locations.
- Keep one authoritative set of user documentation.
- Reduce duplicated files and make the role of each retained dataset explicit.
- Replace monolithic workflow scripts with a small companion Python package
  containing focused, independently runnable tools.
- Keep generated build files and simulation output separate from source files.
- Provide small, reproducible smoke and system tests for installation and
  complete workflows.
- Protect existing scientific behaviour with numerical regression tests.
- Make workstation and HPC use follow the same documented input workflow.

## Current Duplication

The current layout contains duplication and overlapping responsibilities:

- The root `README.md` and `atris/README.md` both describe AtRIS, but the
  inner README contains older paths and build instructions.
- Root `phantoms/` contains 64 numbered runtime response matrices.
- Inner `atris/phantoms/` contains named response matrices, old response
  matrices, variance tables, plots, and a notebook.
- Byte-level comparison shows that 60 of the 64 numbered runtime matrices are
  copies of named files in `atris/phantoms/`.
- Atmosphere and geometry preparation currently overlaps between
  `prepare_psf.py`, `nrlm2psf.py`, `psf2gdml.py`, `simtools.py`, and the
  temporary `run_atris_bare.py` test harness.
- Generated CMake output currently appears under the inner application
  directory at `atris/build/`.

## Target Structure

A version 3.0 repository should have one obvious build root and directories
named by their role:

```text
atris/
├── CMakeLists.txt
├── main.cc
├── include/
├── src/
├── data/
│   ├── materials/
│   └── phantoms/
├── python/
│   └── atris/
│       ├── __init__.py
│       ├── atmosphere.py
│       ├── psf.py
│       ├── gdml.py
│       ├── macros.py
│       └── run.py
├── examples/
│   └── minimal/
├── tests/
│   ├── fixtures/
│   ├── regression/
│   └── system/
├── docs/
├── pyproject.toml
├── README.md
├── INSTALL.md
├── DEVELOPMENT.md
└── LICENSE
```

This structure is a goal for the 3.0 cleanup. It does not by itself decide
which historical or development files should be retained.

## Companion Python Package

AtRIS should include an `atris` Python package for the workflow surrounding
the C++ simulation executable. Atmosphere retrieval, PSF preparation, PSF to
GDML conversion, macro generation, input validation, simulation launch, and
post-processing can share tested Python functions instead of duplicating logic
across unrelated scripts.

The package should also provide command-line entry points for normal use, such
as `atris-prepare-psf`, `atris-psf-to-gdml`, and `atris-run`. The same
implementation would remain importable for tests and more specialised
workflows. The C++ executable remains the scientific simulation core; the
Python package prepares its inputs and manages the surrounding workflow.

The atmosphere-to-PSF path should move away from pandas. Its current role is
limited to reading whitespace-separated NRLMSIS output, joining downloaded
chunks, sorting rows, removing duplicate altitudes, and selecting columns.
These operations do not justify making pandas a dependency of the preparation
tools. The existing implementation should remain in place until regression
tests cover the generated PSF files. Pandas may still be useful in
post-processing code that performs substantial tabular analysis.

Temporary end-to-end harnesses such as `run_atris_bare.py` are not part of the
supported Python interface. Useful harnesses should be converted into
reproducible smoke or system tests; those that do not provide lasting test
coverage should be removed. The repository can contain several focused tests
covering installation, input preparation, short simulation runs, and complete
workflows.
