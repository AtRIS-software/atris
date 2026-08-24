# Running AtRIS

AtRIS is a C++ executable that reads prepared geometry, macro, energy-bin, and
phantom files from its current directory. The one-time Geant4 and AtRIS build
is documented in [INSTALL.md](INSTALL.md).

## Start a shell session

These instructions use the [directory layout](INSTALL.md#directory-layout)
from `INSTALL.md`. In the commands below, `<VERSION>` is the installed
Geant4 version, for example `v11.4.2`.

```bash
cd <ATRIS_WORK>
source geant4-<VERSION>/install/bin/geant4.sh
```

## Prepare a run

Keep each simulation's inputs and outputs in a separate directory. This example
uses `runs/my-first-run`:

```bash
RUN_DIR="$PWD/runs/my-first-run"
mkdir -p "$RUN_DIR"
```

Reusing a run directory overwrites files with the same names.

### Create the PSF

Download an atmosphere from the
[NASA CCMC NRLMSIS Instant Run](https://kauai.ccmc.gsfc.nasa.gov/instantrun/nrlmsis/)
page. Select NRLMSIS 2.0, choose the time, location, and altitude profile, and
save the text result as `nrlmsis_output.txt` in `$RUN_DIR`.

Convert the downloaded table to `simulation.psf`:

```bash
cd "$RUN_DIR"
python ../../atris/nrlmsis_to_psf.py nrlmsis_output.txt
cd <ATRIS_WORK>
```

The Planet Specification Format (PSF) is an editable table describing the
planet's spherical layers, including their geometry, temperature, density,
pressure, composition, and detector identifiers.

### Create the GDML

Convert the PSF into the Geant4 geometry read by AtRIS:

```bash
cd atris/atris/interface
python psf2gdml.py "$RUN_DIR/simulation"
cd <ATRIS_WORK>
```

This creates `simulation.gdml`. The converter is run from its own directory
because it reads `nist.exist` and `atris.materials` there.

### Create macros and energy bins

Generate a small, reproducible proton and alpha test:

```bash
python atris/atrismacrogen.py "$RUN_DIR" \
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

### Add a phantom

Copy one radiation/counting response pair into the run directory:

```bash
cp atris/phantoms/radiation_phantom0.txt "$RUN_DIR/"
cp atris/phantoms/counting_phantom0.txt "$RUN_DIR/"
cp atris/phantoms/phantoms.txt "$RUN_DIR/"
```

The required proton inputs are now:

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

Run the proton and alpha simulations from the run directory:

```bash
cd "$RUN_DIR"
set -o pipefail
../../atris/atris/build/AtRIS FTFP_BERT_HP protons -1 1 2>&1 | tee protons.log
../../atris/atris/build/AtRIS FTFP_BERT_HP alphas -1 1 2>&1 | tee alphas.log
```

The four AtRIS arguments are:

```text
FTFP_BERT_HP   Geant4 physics list
protons/alphas prefix for the .gdml, .mac, .bins, and output files
-1             histogram/CSV output mode used by this workflow
1              number of numbered phantom pairs to load
```

Worker threads are configured inside the generated macro files rather than
passed to the executable.

Starting a simulation is reported by:

```text
### AtRIS: Starting the simulation
```

A completed simulation later reports:

```text
### AtRIS: the simulation has completed
### AtRIS: The logfile has been sucessfully closed...
```

The run directory then contains `protons.log`, `alphas.log`, and CSV output
files beginning with `protons_` and `alphas_`.

## Inspect the results

The inspection tools use the supplied Conda environment. Create it once:

```bash
cd <ATRIS_WORK>
conda env create -f atris/environment.yml
conda activate atris
```

Post-process the proton and alpha CSV files and create the PDF plots:

```bash
cd <ATRIS_WORK>
python atris/postprocess.py "$RUN_DIR"
```

This writes `protons.pdf` and `alphas.pdf` in the run directory, together with
the processed ionization, dose, dose-equivalent, and count-rate files. The
previews below come from the reduced test configuration in this guide and are
not scientific production results.

**Protons**

![Proton response plots](examples/results/protons.png)

**Alphas**

![Alpha response plots](examples/results/alphas.png)
