# AtRIS

AtRIS (Atmospheric Radiation Interaction Simulator) is a Geant4-based
particle-transport code for parametric studies of radiation propagation through
planetary and exoplanetary atmospheres. Its flexible description of the
atmosphere and regolith supports studies of altitude-dependent secondary
particles and ion-pair production for atmospheric chemistry and habitability
research.

AtRIS also calculates atmospheric ionization, absorbed dose, dose equivalent,
and count rate. It was developed by Saša Banjac and validated against Earth
measurements, as described by
[Banjac, Herbst, and Heber (2018)](https://doi.org/10.1029/2018JA026042). This
repository provides the simulator, preparation and post-processing tools, and
phantom response files; the workflow below focuses on multithreaded Earth
atmosphere simulations.

This guide explains how to prepare, run, and inspect an AtRIS simulation. See
[INSTALL.md](INSTALL.md) for installation and build instructions, and
[docs/hpc.md](docs/hpc.md) for architecture and sizing guidance for larger
scatter/gather simulations on an HPC system.

A small set of prepared inputs is included in the
[reduced Earth atmosphere example](examples/earth-nrlmsis/README.md).

## Start a shell session

These instructions use the [directory layout](INSTALL.md#directory-layout)
from `INSTALL.md`.
```bash
cd <ATRIS_WORK>
```
Prepare the current shell to run AtRIS with Geant4:
```bash
source atris/setup_atris.sh
```

If you wish you can source this script from your rc file.

## Prepare a run

Keep each simulation's inputs and outputs in a separate directory. This example
uses `runs/my-first-run`:

```bash
mkdir -p runs/my-first-run
cd runs/my-first-run
```

### Fetch the atmosphere model

Download an atmosphere from the
[NASA CCMC NRLMSIS Instant Run](https://kauai.ccmc.gsfc.nasa.gov/instantrun/nrlmsis/)
page. Select NRLMSIS 2.0, choose the time, location, and altitude profile, and
save the text result as `nrlmsis_output.txt` in the run directory.

Convert the downloaded table to `simulation.psf` in the run directory:

```bash
nrlmsis2psf nrlmsis_output.txt
```

The Planet Specification Format (PSF) is an editable table describing the
planet's spherical layers, including their geometry, temperature, density,
pressure, composition, and detector identifiers.

Convert the PSF into the Geant4 geometry read by AtRIS in the run directory:

```bash
psf2gdml
```

This creates `simulation.gdml` beside `simulation.psf`.

### Generate the particle inputs (`.mac` and `.bins`)

Generate a small, reproducible proton and alpha test in the run directory:

```bash
atrismacrogen \
  --particles-per-bin 4 \
  --alpha-factor 0.66 \
  --random-seed 12345 \
  --energy-max-power 3 \
  --energy-points 18
```

This copies `simulation.gdml` to `protons.gdml` and `alphas.gdml`, then
creates the matching `.mac` and `.bins` files. The reduced energy grid and
particle count are intended only to verify that AtRIS runs. The command refuses
to run if any of those proton or alpha input files already exist.

### Add phantom response files

Each row in `phantoms.txt` defines one phantom. Copy the supplied two-phantom
example into the run directory:

```bash
cp "$ATRIS_ROOT/examples/earth-nrlmsis/phantoms.txt" .
```

The supplied file contains:

```text
# Each row defines one phantom.
# IDs run contiguously from 0 and identify numbered AtRIS input and output.
# Phantom is the filename stem shared by _response.txt and _counting.txt.
# Mass is the phantom mass; area is its cross-sectional area.
# ID  Phantom                          mass [g] area [cm2]
   0  ramona_zero_0.060MeV_detA          0.5082      6.928
   1  icru_zero_0.000MeV_detAB       14094.7550    1413.72
```

Then stage the response files under the numbered names expected by AtRIS:

```bash
atris-stage-phantoms .
```

The command first looks for the files in the run directory, allowing custom
phantom files to be used directly. Otherwise, it uses the standard files from
`phantoms`. Relative symbolic links are created by default; pass `--copy` to
make a self-contained run directory.

A run without phantoms does not need `phantoms.txt` or this staging step. Pass
`0` as the final AtRIS argument for such a run.

The required proton inputs are now in the run directory:

```text
protons.gdml
protons.mac
protons.bins
radiation_phantom0.txt
counting_phantom0.txt
radiation_phantom1.txt
counting_phantom1.txt
phantoms.txt
```

- `protons.gdml` defines the planet, atmosphere, materials, and sensitive
  layers.
- `protons.mac` defines the particle source, energy distribution, and event
  count. Ordinary single-run macros also contain their random seeds.
- `protons.bins` contains the energy values used by the AtRIS output.
- Each phantom pair contains the response tables used for dose,
  dose-equivalent, and count-rate calculations.
- `phantoms.txt` selects the response tables and contains the mass and
  cross-sectional area used during post-processing.

### Clone a prepared run

To reuse the inputs from the current run in a new sibling directory:

```bash
atris-clone . ../my-second-run
```

This copies the prepared atmosphere, geometry, particle inputs, and phantom
inputs. Simulation results, plots, logs, and chunk progress are not copied. The
command refuses to use an existing destination directory.

## Run AtRIS

Run the proton and alpha simulations in the run directory:

```bash
AtRIS FTFP_BERT_HP protons -1 2
AtRIS FTFP_BERT_HP alphas -1 2
```

The four AtRIS arguments are:

```text
FTFP_BERT_HP   Geant4 physics list
protons/alphas prefix for the .gdml, .mac, .bins, and output files
-1             histogram/CSV output mode used by this workflow
2              number of numbered phantom pairs to load
```

AtRIS uses all processors detected by Geant4 by default. Set
`G4FORCENUMBEROFTHREADS` before starting AtRIS to use a specific number:

```bash
export G4FORCENUMBEROFTHREADS=4
```

An existing macro containing `/run/numberOfThreads` retains that setting unless
`G4FORCENUMBEROFTHREADS` is set.

Starting a simulation is reported by:

```text
### AtRIS: Starting the simulation
```

A completed simulation later reports:

```text
### AtRIS: the simulation has completed
### AtRIS: The logfile has been sucessfully closed...
```

The run directory then contains CSV output files beginning with `protons_` and
`alphas_`.

### Scatter and gather a larger run

Scatter/gather is suitable for larger simulations whose work should be divided
into independent, restartable chunks. After generating the ordinary particle
inputs, create 20 proton and 20 alpha chunks:

```bash
atris-scatter --chunks 20 --random-seed 12345
```

This creates seed-free `protons.chunk.mac` and `alphas.chunk.mac` variants, an
empty `chunks/` output directory, and `chunks.txt`. The ordinary macros are not
changed and remain available for single runs. Each line of `chunks.txt` gives a
particle species and two random seeds. Initial `--chunks` creation will not
overwrite an existing plan, chunk macro, or nonempty `chunks/` directory.

The `/run/beamOn` total from each ordinary macro is divided among its chunks.
All chunks share one macro, so the per-chunk count is rounded up when the total
does not divide evenly. In that case `atris-scatter` reports both the requested
and actual totals; the actual total exceeds the request by fewer than the number
of chunks.

The chunks can be executed independently. Each successful repetition writes
its outputs beneath `chunks/` and adds a `COMPLETE` marker. Incomplete chunks
can be run again without repeating completed work.

For worker-pool architecture, sizing, chunk safety, and recovery guidance, see
[Running AtRIS on an HPC system](docs/hpc.md). For a copy/paste workflow, use
the [full Earth Slurm example](examples/earth-nrlmsis-full-slurm/README.md),
which provides concrete five-node simulation and gather scripts.

Run the incomplete chunks sequentially in the current shell:

```bash
atris-run
```

Completed chunk outputs begin appearing beneath `chunks/` while the command is
still running. Raw AtRIS output is written to one log file per chunk. If the
command is interrupted, running it again skips chunks already marked
`COMPLETE`.

Gather whichever chunks have completed so far into ordinary proton and alpha
CSV outputs in the run directory:

```bash
atris-gather
```

Running `atris-gather` again replaces those files with a new aggregate of all
chunks complete at that time.

### Add samples when a run has not converged

After stopping all workers, append another independent batch without changing
or repeating any completed chunks:

```bash
atris-scatter --extend 20
atris-run
atris-gather
atris-postprocess
atris-plot
```

`--extend 20` adds 20 proton and 20 alpha entries using the existing per-chunk
event counts. It reports the added and cumulative events for each species. All
existing plan entries, outputs, and `COMPLETE` markers remain unchanged, so
`atris-run` processes only the new entries and the next gather incorporates
them into the convergence history.

The random seed pairs actually passed to AtRIS are stored in `chunks.txt`.
`--random-seed` is optional during extension; provide it only when reproducible
generation of the additional pairs is required. New pairs are checked against
the entire existing plan. Do not extend a plan while a worker allocation or
gather operation is active.

## Inspect the results

Post-process the proton and alpha CSV files in the run directory:

```bash
postprocess
```

This writes the scaled numerical ionization, absorbed-dose, dose-equivalent,
and count-rate files. Create quick-look PNG plots of the run inputs and those
processed files separately:

```bash
atris-plot
```

The input plots can also be created before running AtRIS. Each configured
species gets an image such as `protons.inputs.png`, showing its primary-energy
configuration, atmospheric profiles, composition, and source settings. Each
staged phantom gets an input image showing its radiation and counting response
tables.

After post-processing, each available species also gets a result image such as
`protons.png`, containing primary-energy, source-direction, source-position,
and ionization panels. Each phantom gets its own result image, such as
`protons.icru_zero_0.000MeV_detAB.png`, containing absorbed-dose,
dose-equivalent, and count-rate panels.

The previews below come from the reduced test configuration in this guide and
are not scientific production results.

**Protons**

![Proton response plots](examples/results/protons.png)

**Alphas**

![Alpha response plots](examples/results/alphas.png)
