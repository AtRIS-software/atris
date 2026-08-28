# Reduced Earth atmosphere example

This example reproduces a short end-to-end AtRIS run from an NRLMSIS 2.0
atmosphere. The profile is for 18 August 2026 at 00:00 UTC, 55 degrees north
and 45 degrees east, covering 0 to 1000 km in 50 km steps.

For a finer atmosphere grid and the default particle settings, use the
[full Earth atmosphere example](../earth-nrlmsis-full/README.md).

The particle inputs use ten logarithmically spaced energy points. The proton
run contains 20 events from 1 to 1000 MeV, while the alpha run contains 10
events from 4 to 4000 MeV. These small event counts check the installation and
workflow; they are not suitable for scientific results.

## Create the run directory

From `<ATRIS_WORK>`, prepare the shell and create an empty run directory:

```bash
source atris/setup_atris.sh
mkdir -p runs/earth-nrlmsis-reduced
cd runs/earth-nrlmsis-reduced
```

## Prepare the atmosphere

Each example keeps its atmosphere file in its own directory. The reduced
profile is `examples/earth-nrlmsis-reduced/nrlmsis_output.txt`; it contains NRLMSIS 2.0
data for 18 August 2026 at 00:00 UTC, 55 degrees north and 45 degrees east,
covering 0 to 1000 km in 50 km steps. Use this file unless you need a different
time or location:

```bash
cp "$ATRIS_ROOT/examples/earth-nrlmsis-reduced/nrlmsis_output.txt" .
```

### Use a different time or location (optional)

To use a different UTC time or coordinates, open the
[NASA CCMC NRLMSIS Instant Run](https://kauai.ccmc.gsfc.nasa.gov/instantrun/nrlmsis/)
page and select NRLMSIS 2.0. Choose the new time and coordinates, and use
altitudes from 0 to 1000 km in 50 km steps to retain this example's reduced
geometry. Save the downloaded text in the run directory as
`nrlmsis_output.txt`.

Convert the atmosphere to the Planet Specification Format file
`simulation.psf`:

```bash
nrlmsis2psf nrlmsis_output.txt
```

The PSF describes the atmosphere's spherical layers, temperatures, densities,
pressures, compositions, and detector identifiers. Convert it to the Geant4
geometry `simulation.gdml`:

```bash
psf2gdml
```

## Prepare the particle inputs

Generate the proton and alpha geometries, macros, and energy-bin files:

```bash
atrismacrogen \
  --particles-per-bin 2 \
  --alpha-factor 0.66 \
  --random-seed 12345 \
  --energy-max-power 3 \
  --energy-points 10
```

This creates `protons.gdml`, `protons.mac`, and `protons.bins`, together with
the corresponding alpha files. With 10 energy points, AtRIS will process 20
proton events (`10 x 2`) and 10 alpha events (`10 x int(2 x 0.66)`).

On an Apple M1 using four worker threads, the proton and alpha runs took about
eight seconds in total. Expect roughly seconds to a minute on a current
workstation; startup time dominates this very small run.

## Prepare the phantom inputs

Copy the example's phantom selection into the run directory:

```bash
cp "$ATRIS_ROOT/examples/earth-nrlmsis-reduced/phantoms.txt" .
```

It selects these two response-table pairs:

```text
# ID  Phantom                          mass [g] area [cm2]
   0  ramona_zero_0.060MeV_detA          0.5082      6.928
   1  icru_zero_0.000MeV_detAB       14094.7550    1413.72
```

Stage the selected response files under the numbered filenames expected by
AtRIS:

```bash
atris-stage-phantoms .
```

The command creates relative symbolic links to the response tables in
`$ATRIS_ROOT/phantoms`.

## Run and inspect the example

Use four Geant4 worker threads and run both particle species:

```bash
export G4FORCENUMBEROFTHREADS=4
AtRIS FTFP_BERT_HP protons -1 2
AtRIS FTFP_BERT_HP alphas -1 2
```

Post-process and plot the results:

```bash
postprocess
atris-plot
```

## Prepared reference files

The committed example directory retains the downloaded atmosphere and every
generated input file so the results of each preparation step can be compared.
Simulation outputs, plots, logs, and staged phantom links are not included.

To run those prepared inputs directly instead of reproducing them, copy the
example to a different run directory:

```bash
cd <ATRIS_WORK>
cp -R "$ATRIS_ROOT/examples/earth-nrlmsis-reduced" runs/earth-nrlmsis-reduced-prepared
cd runs/earth-nrlmsis-reduced-prepared
atris-stage-phantoms .
```
