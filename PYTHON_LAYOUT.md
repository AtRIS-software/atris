# Python module layout

Each scientific concept has one implementation. Data modules do not depend on
plotting or command-line orchestration. NumPy arrays remain the calculation
interface. `PhantomBuilder` prepares, runs and gathers a build; `Phantom` holds
and saves its result. Both work from notebooks and ordinary scripts.

## Data and file formats

| File in `atris_tools/` | Responsibility |
| --- | --- |
| `phantom.py` | `Phantom`, dose-precision targets, result calculations and persistence. |
| `phantom_statistics.py` | `PhantomStatistics`, chunk-statistic reading and merging, and existing event-record reduction. |
| `phantom_geometry.py` | Spherical layer validation and the shared detector/source geometry conventions. |
| `phantom_table.py` | `PhantomTable`, its energy grid, and runtime response/counting text tables. |
| `histogram.py` | `Histogram` and ROOT/CSV histogram I/O, preserving available moments and metadata. |
| `root_records.py` | ROOT ntuple reading, interface/step schemas and bounded step summaries. No CSV step format. |
| `psf.py` | `PSF`, material/layer columns, PSF I/O and detector volumes/areas. |
| `gdml.py` | PSF-to-GDML conversion and reading spherical GDML layers. |
| `macros.py` | Reading macro settings and generating ordinary proton/alpha inputs. |
| `nrlmsis.py` | The single NRLMSIS-table-to-PSF converter. |
| `particles.py` | PDG codes, particle and element names, and symbols. |

`Histogram.sumw2` is the stored sum of squared weights, not a sample variance.
Missing moments remain missing. The phantom's sampling variance and standard
error retain their existing definitions. This reorganization does not change
physical units, source sampling, histogram contents or on-disk formats.

## Workflows

| File in `atris_tools/` | Responsibility |
| --- | --- |
| `phantom_builder.py` | `PhantomBuilder`, build settings, input preparation, execution and gathering completed batches. |
| `stage_phantoms.py` | Read `phantoms.txt` selections and stage existing runtime tables. Not phantom creation. |
| `chunks.py` | Read chunk plans, name outputs and report completion/progress. |
| `scatter.py` | Prepare and extend independently seeded chunk inputs. |
| `run_chunks.py` | Run selected incomplete chunks. |
| `gather.py` | Merge completed histogram chunks and retain provenance. |
| `convergence.py` | Calculations and reports for convergence of gathered responses. |
| `postprocess.py` | Normalize gathered atmospheric responses into scientific products. |
| `clone_run.py` | Copy reusable run inputs without results. |
| `dump.py` | Inspect ROOT records from the command line. |

The dependency points from `PhantomBuilder` to `Phantom`, not back again.
`builder.gather()` returns a result without running or saving; it also works
after `PhantomBuilder.open(directory)`. `Phantom.read_root(path)` reads a saved
result without requiring its build directory. Neither operation launches transport.

## Plotting and shared infrastructure

| File in `atris_tools/` | Responsibility |
| --- | --- |
| `plotting.py` | Processed-response and convergence plots; plotting command orchestration. |
| `input_plotting.py` | Plots of supplied atmosphere, source and phantom inputs. |
| `phantom_plotting.py` | Phantom response and sampling-precision plots, returning Matplotlib axes. |
| `interface_plotting.py` | Interface-crossing plots. |
| `step_plotting.py` | Shower/step plots. |
| `plotting_common.py` | Shared axis, shell-coordinate, normalization and species-group helpers. No file readers. |
| `file_io.py` | Atomic text-file replacement used by several workflows. |
| `cli.py` | Shared argument/help and logging conventions. |
| `version.py` | Package and executable version reporting. |
| `__init__.py` | Package identity, not a second public API made of re-exports. |

## Removed boundaries

- The unused second atmosphere converter `nrlm2psf.py` is removed.
- `atrismacrogen.py`, `psf2gdml.py` and `nrlmsis2psf.py` become `macros.py`, `gdml.py` and `nrlmsis.py`. Installed command names stay unchanged.
- `phantoms.py` becomes `stage_phantoms.py`; grid constants belong to `phantom_table.py`, not a staging command.
- `phantom_tables.py` and `phantom_diagnostics.py` become `phantom_table.py` and `phantom_plotting.py`.
- `response_histograms.py` and `root_histograms.py` become one `histogram.py`; chunk orchestration belongs in `gather.py`.
- `root_output.py`, `interface_output.py` and `step_output.py` become `root_records.py`.
- Generic chunk, atomic-write and convergence helpers move out of `gather.py`.
- GDML reading and shared plotting helpers move out of `input_plotting.py`.

Update callers, command entry points, tests and notebook imports together. Do
not keep forwarding modules or duplicate implementations under the old names.
Keep experiments and worked examples outside the library.

Python callers use `macros.generate_macros(particles_per_bin=..., alpha_factor=...,
run_directory=...)`, `gdml.psf_to_gdml(...)`, and
`stage_phantoms.read_phantom_selection(...)`. Histogram sums are exposed as
`Histogram.sumw2`; ROOT interface records are read with
`root_records.read_interface_records(...)`. These names replace the old Python
names; the installed command names and their options are unchanged.

Notebook examples follow these interfaces rather than fixing the library's
structure in place. `Phantom.gather(...)` is replaced by `builder.gather()`;
no forwarding method retains the dependency from the result back to its builder.
