# Development

Version 3.0 added scatter-gather support and placed the existing Python scripts
in a small package. Structural work should not change scientific or numerical
behaviour unless that change is explicitly documented and validated.

## Remaining goals

The remaining goals are:

- Reduce duplicated files and make the role of each retained dataset explicit.
- Provide small, reproducible system tests for installation and complete
  workflows.
- Protect existing scientific behaviour with numerical regression tests.

## Phantom data

The repository now has one `phantoms/` library. Its named response and counting
tables are source data. Run preparation selects entries from that library and
stages them under the numbered filenames required by the AtRIS executable; the
run's `phantoms.txt` records the mapping back to the source names.

The same directory still contains old response tables, variance tables, plots,
and other historical data. Their provenance and continuing role should be
established before removing them. The development notebook and historical
library notes are now in the [phantom library reference](reference/phantom-library.md).

## Companion Python package

The repository now contains an initial `atris_tools` package. It provides
command-line entry points for atmosphere conversion, PSF-to-GDML conversion,
macro generation, chunk scattering and gathering, post-processing, and binary
conversion. These commands are also importable as Python modules.

The package uses `atris-*` command names for these operations. Existing
standalone command names remain available for compatibility and to preserve the
current user documentation. New commands should use the `atris-` prefix.

The package now separates atmosphere preparation, PSF-to-GDML conversion,
macro generation, chunk management, numerical post-processing, and plotting.
The C++ executable remains the scientific simulation core; the Python package
prepares its inputs and manages the surrounding workflow.

## Binary output

Interface and transport-step files begin with the same 32-byte header. It
contains the `ATRISBIN` identifier, format and schema versions, record type,
byte-order marker, header size, and record size. Interface records retain the
historical five fields. Step records contain the event and track identifiers,
particle and detector identifiers, pre- and post-step positions and energies,
energy deposition, step length, time, primary energy, and process names.

The readers in `atris_tools.interface_output` and `atris_tools.step_output`
memory-map these files. `atris-dump` identifies either record type from the
header and writes CSV text to standard output. New formats must use a new
format or schema version rather than silently changing an existing record
layout.

Some modules still retain names and implementation details from the original
standalone scripts. Further cleanup should favor clear importable functions and
small command-line entry points without changing the supported workflow.

## Thread scaling

Do not assume that AtRIS becomes faster whenever more worker threads are added.
The imported README (commit `112e4dc`) says that scaling eventually stops
because of CPU cache topology. It does not give the limiting core count. The
accompanying `simstarter.ipynb` uses 16 worker threads. That is a historical
example, not a benchmark for current hardware.

The thread count applies to each AtRIS process. Therefore, an HPC chunk using
16 worker threads requires 16 cores, and concurrent chunks require separate
sets of cores. Benchmark representative chunks at several thread counts before
deciding how many cores to allocate to each chunk. Do not describe 16 as a
measured optimum. User-facing guidance for chunk sizing, scheduler worker
pools, and resource measurement is in
[Running AtRIS on an HPC system](hpc.md).

## Remaining tests

Temporary end-to-end harnesses are not part of the supported Python interface.
Useful harnesses should be converted into reproducible smoke or system tests;
those that do not provide lasting test coverage should be removed.

The current tests cover the Python tools and short runs of the compiled AtRIS
executable. The main remaining gaps are a complete preparation-to-post-processing
system test, behavioral tests for the Slurm wrappers, and reviewed numerical
regression baselines for scientific output.

See [Minimal test fixture](reference/minimal-test-fixture.md) for the fixture
layout and the limits of its validation.

The [workflow tutorial](tutorials/files-through-workflow.md) exercises preparation,
execution, and processing using a few chunks of the Earth example. It checks
the workflow, not scientific convergence.
