# Prepare an Earth atmosphere simulation

**Next step:** [Run and inspect the Earth simulation](run-earth-simulation.md).

This example prepares an Earth atmosphere with 101 layers, each 1 km thick,
from the surface to 101 km. The supplied `simulation.psf` also includes the
solid interior, crust, and outer stopping shell. Each step below shows which
files it reads and creates.

AtRIS and the Python tools should already be [installed](../running-atris/installation.md),
with `ATRIS_ROOT` pointing to the AtRIS directory. All commands run inside the
new simulation directory.

## Create the run directory

From `runs/`, create and enter the run directory, then copy the model:

```bash
mkdir earth-nrlmsis-full
cd earth-nrlmsis-full
cp "$ATRIS_ROOT/examples/earth-nrlmsis-full/simulation.psf" .
```

## Inspect and convert the atmosphere

```bash
head -n 5 simulation.psf
atris-psf-to-gdml simulation.psf
```

The first PSF line defines the materials; the numeric rows describe the shells.
The [PSF reference](../reference/inputs.md#planet-specification-format-psf)
defines their columns and units. To use another time or location, obtain a
profile with the [NASA atmosphere guide](../running-atris/download-nasa-atmosphere.md).

| Reads | Creates |
| --- | --- |
| `simulation.psf`, packaged material definitions | `simulation.gdml` |

`simulation.gdml` describes the geometry and materials in Geant4's format. It
also identifies the layers where AtRIS records results. The later preparation
and analysis steps use `simulation.psf` as well.

```{figure} ../images/earth-example/simulation.psf.png
:name: earth-atmosphere-plot
:alt: Earth atmosphere profiles of density, pressure, temperature, and elemental mass fractions from the surface to 101 km.
:width: 100%

The example's atmosphere, plotted from `simulation.psf`. The steps follow the
1 km layers; the right panel shows elemental mass fractions.
```

[Open the full-size atmosphere plot](../images/earth-example/simulation.psf.png).

## Prepare the phantom inputs

Phantom tables let us estimate dose and detector counts from particles crossing
each atmospheric layer. This example uses the original RAMONA silicon detector
A and ICRU water-sphere tables, both without added shielding.
Skip this step if you only need energy deposition in the atmosphere.

Copy the selection file and prepare its tables:

```bash
cp "$ATRIS_ROOT/examples/earth-nrlmsis-full/phantoms.txt" .
atris-stage-phantoms . --copy
```

| Reads | Creates |
| --- | --- |
| `phantoms.txt`, selected tables in `$ATRIS_ROOT/phantoms` | Local response/counting tables and four numbered symlinks |

`phantoms.txt` records each phantom's mass and area. Staging connects its named
tables to the numbered inputs read by AtRIS:

```text
radiation_phantom0.txt -> ramona_zero_0.060MeV_detA_old_response.txt
counting_phantom0.txt  -> ramona_zero_0.060MeV_detA_old_counting.txt
radiation_phantom1.txt -> icru_zero_0.000MeV_detAB_old_response.txt
counting_phantom1.txt  -> icru_zero_0.000MeV_detAB_old_counting.txt
```

The responses use the supplied `_old` energy-fraction tables. The corresponding
`_old_counting.txt` names are aliases of the original `_counting.txt` files,
containing the supplied counting efficiencies. The [phantom reference](../reference/phantom-library.md#existing-earth-example)
gives the geometry and file pairing.

`--copy` keeps the link targets inside the run directory. Inspect them with
`ls -l radiation_phantom*.txt counting_phantom*.txt`.
The tables score [phantom responses](../background/radiation-quantities.md#phantom-responses)
during transport; they do not add detector volumes to the geometry.

## Prepare the particle inputs

Use the default sampling values and a fixed seed for reproducible input generation:

```bash
atris-generate-macros . \
  --particles-per-bin 5000 \
  --alpha-factor 0.66 \
  --energy-min-power 0 \
  --energy-max-power 6 \
  --energy-points 121 \
  --random-seed 12345
```

| Reads | Creates |
| --- | --- |
| `simulation.psf`, `simulation.gdml` | `protons.gdml`, `protons.mac`, `protons.bins` |
| The same model | `alphas.gdml`, `alphas.mac`, `alphas.bins` |

Each species has a geometry copy (`.gdml`), source and event commands (`.mac`),
and histogram energy edges (`.bins`). The 121 energy edges span 1–1,000,000 MeV
for protons and 4–4,000,000 MeV for alphas, with 605,000 and 399,300 requested
events respectively. See the [energy-grid convention](../reference/inputs.md#energy-bins-and-macros)
for how these counts are calculated.

The example uses `FTFP_BERT_HP` physics and `response` output when launched.
The model and particle inputs are ready; simulation begins in the next tutorial.

**Next step:** [Run and inspect the Earth simulation](run-earth-simulation.md).
