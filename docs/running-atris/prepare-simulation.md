# Prepare the simulation

**Next step:** [Plan chunks and restarts](plan-chunks.md).

Prepare a model of the planet's atmosphere and surface, any detector or dose
calculations, and the particle types and energies to simulate. The resulting
inputs can be used on your computer, a server, or a computing cluster. Start
with AtRIS and its Python tools [installed](installation.md).

For a worked example with intermediate files explained, use
[Prepare an Earth atmosphere simulation](../tutorials/earth-nrlmsis-full.md).

```{toctree}
:hidden:

download-nasa-atmosphere
```

## Start with your PSF

`simulation.psf` describes the planetary layers and their materials. Use an
existing model, [build one in the exoplanet notebook](../tutorials/exoplanet-psf.ipynb),
or [convert an Earth atmosphere from NASA](download-nasa-atmosphere.md).
Inspect the layer boundaries, units, density, and composition before generating
other inputs; the [PSF reference](../reference/inputs.md#planet-specification-format-psf)
defines the format.
Layer resolution affects both the physical approximation and
[the cost of transport and scoring](../background/what-determines-runtime.md#atmospheric-layers).

The recommended layout places `runs/` beside the AtRIS directory. From `runs/`,
or another directory where you keep simulations, create and enter a new run
directory. Replace `/path/to/model` with the directory containing your PSF:

```bash
mkdir simulation-run
cd simulation-run
cp /path/to/model/simulation.psf .
```

Use an unused directory name and keep the filename `simulation.psf`. If you
already created the model in its own run directory, work there instead of
copying it again. Run the remaining commands inside that directory.

## Convert the geometry

```bash
atris-psf-to-gdml simulation.psf
```

This creates `simulation.gdml`, the geometry and material description read by
Geant4. Keep the PSF: post-processing also uses its layer geometry.

## Optionally select phantoms

Phantom tables describe how a detector or material responds to radiation.
Use them to calculate dose or detector counts; skip this step if you only need
particle transport and energy deposition in the atmosphere.

Create `phantoms.txt` in the run directory,
listing the selected table stems and their masses and areas. Choose the
material, detector, and shielding appropriate to your observable from the
[phantom library](../reference/phantom-library.md). The
[selection-file reference](../reference/inputs.md#phantom-selection) gives the
row format and ID convention.

Once that file is ready, stage its tables:

```bash
atris-stage-phantoms . --copy
```

`--copy` keeps the response tables local for transferring the run directory.
Select phantoms before generating particle inputs: their responses are scored
during transport. See [phantom scoring](../background/radiation-quantities.md#phantom-responses)
and its [runtime cost](../background/what-determines-runtime.md#phantom-responses).

## Prepare particle inputs

`atris-generate-macros` prepares separate proton and alpha simulations.
Choose the energy range, number of energy points, and number of particles to
simulate. For example, the following explicitly sets the generator's
standard sampling values and fixes the seed used to generate macros:

```bash
atris-generate-macros . \
  --energy-min-power 0 \
  --energy-max-power 6 \
  --energy-points 121 \
  --particles-per-bin 5000 \
  --alpha-factor 0.66 \
  --random-seed 12345
```

Adapt these values to the particles and energies relevant to your study.
The energy powers specify proton kinetic energies in MeV; alpha energies are
four times the proton values. These are total energies per particle, not
energies per nucleon. Event counts control statistical sampling, not physical
source intensity. The [energy-grid and event-count conventions](../reference/inputs.md#energy-bins-and-macros)
explain exactly how the options determine the generated inputs.

The command creates `.gdml`, `.mac`, and `.bins` files for each species. It
refuses to overwrite existing species inputs. Check the generated macros if
your study requires a different source position or angular distribution; the
[macro-generator reference](../reference/commands/atris-generate-macros.md)
describes the supported options.

For more sampling with the same inputs, [extend the chunk plan](plan-chunks.md#extend-a-run).
For combining separately prepared batches, see
[combining compatible batches](../background/normalization-and-uncertainty.md#gather-raw-sums-before-normalization).

## Record physics and output choices

Choose a [Geant4 physics list](../background/physics-lists.md) and an
[output mode](../reference/executable.md#output-modes). The launch guides use
`FTFP_BERT_HP` and `response`; record your choices in your run notes and supply
them consistently to `atris-run` if they differ. These choices belong to the
physical calculation even though they are passed at launch time.

## Check the prepared inputs

With the plotting extra installed, inspect the model and source before running:

```bash
atris-plot .
```

Review the species input plots and, if selected, the phantom input plots.
The [input reference](../reference/inputs.md#run-directory-filenames) lists the
files that define the prepared simulation.

**Next step:** [Plan chunks and restarts](plan-chunks.md).
