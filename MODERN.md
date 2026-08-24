# Running AtRIS

This document covers the work done for each shell session and each simulation.
The one-time Geant4 and AtRIS build is documented in
[INSTALL.md](INSTALL.md).

AtRIS is a C++ executable. It reads prepared geometry, macro, energy-bin, and
phantom files from the current directory. The final command is deliberately
simple; most of the scientific choices are contained in those input files.

## At the start of a shell session

The commands below expect the AtRIS checkout and Geant4 installation to be in
the same parent directory. The expected directory layout is:

```text
atris-work/
|-- atris/
|   |-- atris/
|   |   `-- build/
|   |       `-- AtRIS
|   `-- run_atris_bare.py
`-- geant4-<VERSION>/
    `-- install/
        `-- bin/
            `-- geant4.sh
```

The parent directory is called `atris-work` in these examples, but its name is
not significant. In the command below, `<VERSION>` is a placeholder for the
installed Geant4 version, for example `v11.4.2`. Start the shell session in
that directory:

```bash
cd atris-work
source geant4-<VERSION>/install/bin/geant4.sh
```

## Python environment

The PSF/GDML preparation tools use NumPy, Matplotlib, and pandas. Create a
[Conda](https://docs.conda.io/projects/conda/en/stable/) environment for these
tools once:

```bash
conda create -n atris python numpy matplotlib pandas
```

Activate it in shell sessions that use the preparation tools:

```bash
conda activate atris
```

## Inputs for one simulation

AtRIS uses a simulation prefix. With the prefix `protons`, the run directory
must contain:

```text
protons.gdml
protons.mac
protons.bins
radiation_phantom0.txt
counting_phantom0.txt
```

The final number passed to AtRIS is the number of phantom pairs to load. A
value of `1` loads the two files ending in `phantom0.txt`. A value of `32`
loads indices 0 through 31.

The files have distinct roles:

- `protons.gdml` defines the planet, atmosphere, sensitive layers, and
  materials.
- `protons.mac` defines the particle type, number of threads, random seeds,
  energy distribution, source geometry, and number of events.
- `protons.bins` supplies the energy-bin edges expected by the AtRIS output.
- The radiation and counting phantom files contain the response matrices used
  for dose, dose-equivalent, and count-rate calculations.

`simulation.psf` is an editable intermediate description used to generate
GDML. AtRIS itself reads the resulting `protons.gdml`, not the PSF file.

## Prepare a run directory

Give every simulation its own directory. For example:

```bash
RUN_DIR="$PWD/runs/quick-protons"
mkdir -p "$RUN_DIR"
```

Do not reuse a directory containing results that need to be preserved. AtRIS
writes output files using the simulation prefix and can overwrite files from an
earlier run.

## Prepare the geometry

Begin with an atmosphere/planet description that has been selected for the
simulation. For a student installation test, this should be a fixed,
instructor-supplied `simulation.psf`, not a live network download.

The repository does not currently track an approved installation-test PSF. It
must be added to the test inputs before the student installation exercise.

Place it in the run directory:

```bash
cp simulation.psf "$RUN_DIR/simulation.psf"
```

Convert the PSF to GDML with the existing converter. It must be launched from
`atris/interface` because it reads `nist.exist` and `atris.materials` there:

```bash
(
  cd atris/atris/interface
  python psf2gdml.py "$RUN_DIR/simulation"
)
cp "$RUN_DIR/simulation.gdml" "$RUN_DIR/protons.gdml"
```

Confirm that the geometry exists:

```bash
test -s "$RUN_DIR/protons.gdml"
```

## Prepare the macro and energy bins

Place the approved quick-test files in the run directory:

```bash
cp protons.mac "$RUN_DIR/protons.mac"
cp protons.bins "$RUN_DIR/protons.bins"
```

Before running, inspect the settings that control computational cost and
reproducibility:

```bash
grep -E '^/run/numberOfThreads|^/run/beamOn|^/random/setSeeds' \
  "$RUN_DIR/protons.mac"
wc -l "$RUN_DIR/protons.bins"
```

The intended installation test has 121 energy bins, 10 particles per bin,
1,210 total events, fixed random seeds, and a thread count chosen for the
machine or allocation.

The repository does not currently provide a clean standalone command for
creating an arbitrary macro and bin set. `atrismacrogen.py` and
`run_atris_bare.py` can create them, but both combine that operation with
additional assumptions. A tidy student installation test therefore requires a
small approved `protons.mac` and `protons.bins` pair to be supplied with the
test inputs. That pair is not currently tracked in the repository.

## Select the phantom files

For a one-phantom installation test:

```bash
cp atris/phantoms/radiation_phantom0.txt "$RUN_DIR/"
cp atris/phantoms/counting_phantom0.txt "$RUN_DIR/"
```

Only copy additional numbered pairs when the run is intended to load them.

## Check the run directory

Enter the run directory and verify that every required input file is present:

```bash
cd "$RUN_DIR"
test -s protons.gdml
test -s protons.mac
test -s protons.bins
test -s radiation_phantom0.txt
test -s counting_phantom0.txt
```

These checks should produce no output. A nonzero status means a required file
is missing or empty.

## Run AtRIS directly

Launch AtRIS from the run directory and record its console output in
`protons.log`:

```bash
(
  cd "$RUN_DIR"
  set -o pipefail
  ../../atris/atris/build/AtRIS FTFP_BERT_HP protons -1 1 2>&1 | tee protons.log
)
```

The arguments are:

```text
FTFP_BERT_HP   Geant4 physics list
protons        prefix for protons.gdml, protons.mac, protons.bins, and outputs
-1             histogram/CSV output mode used by the current workflow
1              number of numbered phantom pairs to load
```

The number of worker threads is not an executable argument. It is set by
`/run/numberOfThreads` inside `protons.mac`.

## Confirm completion

Entering the simulation is reported by:

```text
### AtRIS: Starting the simulation
```

That line is not completion. A successful run later reports:

```text
### AtRIS: the simulation has completed
### AtRIS: The logfile has been sucessfully closed...
```

The run directory should then contain CSV files beginning with `protons_`.

## Proton and alpha runs

An alpha run is a separate invocation with its own files:

```text
alphas.gdml
alphas.mac
alphas.bins
```

After those files have been prepared, the command is:

```bash
(
  cd "$RUN_DIR"
  set -o pipefail
  ../../atris/atris/build/AtRIS FTFP_BERT_HP alphas -1 1 2>&1 | tee alphas.log
)
```

## Role of `run_atris_bare.py`

`run_atris_bare.py` automates atmosphere generation, PSF and GDML generation,
phantom copying, macro and bin generation, process launch, and log monitoring.
That makes it useful as a small end-to-end system test. It is not the clearest
way for a student to learn or verify the individual AtRIS inputs, and it should
not be treated as the normal per-run interface.

The system-test runner reads `ATRIS_ROOT`, `ATRIS_EXECUTABLE`, and either
`GEANT4_SH` or `GEANT4_INSTALL`. The corresponding command-line options take
precedence when supplied. It does not search the filesystem for any of these
locations.
