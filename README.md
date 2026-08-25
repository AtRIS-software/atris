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
phantom response matrices; the workflow below focuses on multithreaded Earth
atmosphere simulations.

This guide explains how to prepare, run, and inspect an AtRIS simulation. See
[INSTALL.md](INSTALL.md) for installation and build instructions.

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

Reusing a run directory overwrites files with the same names.

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
  --particles-per-bin 2 \
  --threads 4 \
  --alpha-factor 0.66 \
  --random-seed 12345 \
  --energy-max-power 3 \
  --energy-points 7
```

This copies `simulation.gdml` to `protons.gdml` and `alphas.gdml`, then
creates the matching `.mac` and `.bins` files. The reduced energy grid and
particle count are intended only to verify that AtRIS runs.

### Add phantom response files

The repository includes 32 numbered radiation/counting response pairs, indexed
from `0` through `31`. This test uses pair `0`; copy it into the run directory:

```bash
cp "$ATRIS_ROOT/phantoms/radiation_phantom0.txt" .
cp "$ATRIS_ROOT/phantoms/counting_phantom0.txt" .
cp "$ATRIS_ROOT/phantoms/phantoms.txt" .
```

The required proton inputs are now in the run directory:

```text
protons.gdml
protons.mac
protons.bins
radiation_phantom0.txt
counting_phantom0.txt
```

- `protons.gdml` defines the planet, atmosphere, materials, and sensitive
  layers.
- `protons.mac` defines the particle source, worker threads, random seeds,
  energy distribution, and event count.
- `protons.bins` contains the energy values used by the AtRIS output.
- The phantom pair contains the response matrices used for dose,
  dose-equivalent, and count-rate calculations.
- `phantoms.txt` contains the phantom mass and cross-sectional area used during
  post-processing.

## Run AtRIS

Run the proton and alpha simulations in the run directory:

```bash
AtRIS FTFP_BERT_HP protons -1 1
AtRIS FTFP_BERT_HP alphas -1 1
```

The four AtRIS arguments are:

```text
FTFP_BERT_HP   Geant4 physics list
protons/alphas prefix for the .gdml, .mac, .bins, and output files
-1             histogram/CSV output mode used by this workflow
1              number of numbered phantom pairs to load
```

The worker count is set by `--threads` when generating the macro files. More
threads do not always make a simulation faster; scaling depends on the
processor and its cache architecture.

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

## Inspect the results

Post-process the proton and alpha CSV files in the run directory and create the
PDF plots:

```bash
postprocess
```

This writes `protons.pdf` and `alphas.pdf` in the run directory, together with
the processed ionization, dose, dose-equivalent, and count-rate files. The
previews below come from the reduced test configuration in this guide and are
not scientific production results.

**Protons**

![Proton response plots](examples/results/protons.png)

**Alphas**

![Alpha response plots](examples/results/alphas.png)
