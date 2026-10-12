# atris-plot

Create PNG diagnostics for available input and output groups.

```bash
atris-plot .
```

The directory defaults to the current directory. Install the `plot` extra to
provide Matplotlib (`python -m pip install -e ".[plot]"`).

**Inputs:** prepared species macros/geometry/bins, staged phantom tables,
processed responses and their raw diagnostics, convergence CSVs, interface
and step ntuples in ROOT output, as available. It discovers the
canonical prefixes `protons` and `alphas`. **Outputs:** the
[PNG products](../outputs.md#plots-and-chunk-metadata), replacing existing images.

Absent product groups are skipped. Errors in individual groups are reported
as warnings while other groups are attempted; command success does not imply
that every possible plot was created. No gather, post-processing, or simulation
is performed. Per-chunk ROOT files are not automatically discovered or combined.

## Reading the plots

Input images show the primary-energy configuration, atmospheric profiles,
composition, and source settings. Each phantom gets one input image; these
plots can be made before running a simulation. Counting efficiency occupies
the top row, with an automatically scaled linear vertical axis that includes
exact zero and unit efficiencies. The bottom row shows the mean deposited
ionizing-energy fraction $\langle W/K\rangle$ on logarithmic axes. Here $W$ is
deposited ionizing energy and $K$ is incident kinetic energy.
Diagonal guides show constant deposited energy in MeV, evaluated as
$\langle W/K\rangle=W/K$ at the energy-bin centre; their labels sit outside
the panels. Fractions above 1 remain visible, including energy released by
decay or annihilation.

The image retains separate particles and nuclei columns.
A missing or invalid response table does not
prevent plotting its available companion. Staged tables do not contain
statistical uncertainties, so these input plots do not add uncertainty bands.

After post-processing, each species result image contains primary-energy,
source-direction, source-position, and ionization panels. Separate phantom
images show absorbed-dose, dose-equivalent, and counting responses.

### Convergence

Each convergence image has ionization-change diagnostics in the upper panel
and estimated Monte Carlo uncertainty in the lower panel. The colour-matched
dashed guides in the upper panel scale as $N^{-1/2}$, where $N$ is the number
of completed chunks. The lower panel fits power laws to the most recent half
of the completed-chunk history and extrapolates them through the planned run.
Both axes are logarithmic so the slopes can be compared directly. These fits
describe the observed trend; they do not guarantee future convergence. See
[the convergence definitions](../chunks.md#convergence-csv) for the quantities
being plotted.

### Step traces

For an available `steps` ntuple from `--mode shower`, `<species>.steps.png`
summarizes particle species, step-defining processes, shower development by
layer, and kinetic-energy distributions. `<species>.shower.png` shows the
event with the most recorded steps in altitude and transverse radius, on
linear axes. The altitude range focuses on the interaction region.

## Arguments and options

The following is the command's `--help` output for this revision.

```text
usage: atris-plot [-h] [-q | -v] [--version] [RUN_DIRECTORY]

Create quick-look PNG plots from the AtRIS inputs and result products already present
in a run directory.

positional arguments:
  RUN_DIRECTORY  Run directory to inspect (default: current directory).

optional arguments:
  -h, --help     show this help message and exit
  -q, --quiet    Suppress normal progress; show warnings and errors only.
  -v, --verbose  Include detailed per-file, per-request, or per-chunk progress.
  --version      Show the AtRIS and atris-tools versions and exit.

Recognized products include prepared macros and geometry, ROOT interface and step
records, convergence tables, and post-processed proton
and alpha responses. Missing product groups are skipped so partial runs can still be
inspected. Existing PNG files with the generated names are replaced. This command does
not run AtRIS, gather chunks, or post-process raw histograms.
```

Implementation: `atris_tools/plotting.py`.
