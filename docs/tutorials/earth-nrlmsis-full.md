# Prepare an Earth atmosphere simulation

**Next step:** [Plan chunks for the prepared simulation](../running-atris/plan-chunks.md).

This example prepares an Earth simulation from an NRLMSIS 2.0 atmosphere. The
profile is for 18 August 2026 at 00:00 UTC, 55 degrees north and 45 degrees
east, covering 0 to 100 km in 0.2 km steps.

These preparation steps are independent of execution environment. Continue with
[chunk planning](../running-atris/plan-chunks.md) once the inputs are ready.

The particle inputs use the `atris-generate-macros` defaults: 121 logarithmically
spaced energy points, 3000 protons per point, and 1980 alpha particles per
point. This produces 363,000 proton events and 239,580 alpha events.

## Create the run directory

From `runs/`, create and enter the run directory:

```bash
mkdir earth-nrlmsis-full
cd earth-nrlmsis-full
```

## Prepare the atmosphere

Each example keeps its downloaded atmosphere tables in its own directory. The
files in `examples/earth-nrlmsis-full` contain NRLMSIS 2.0 data for 18 August
2026 at 00:00 UTC, 55 degrees north and 45 degrees east, covering 0 to 100 km
in 0.2 km steps. Use these files unless you need a different time or location:

```bash
cp "$ATRIS_ROOT"/examples/earth-nrlmsis-full/nrlmsis-*.txt .
```

### Use a different time or location (optional)

See [Download an atmosphere from NASA](../running-atris/download-nasa-atmosphere.md)
for current form controls, date restrictions, activity inputs, and conversion.
The web form checked on 29 September 2026 requires a step of at least 1 km;
it does not accept the 0.2 km spacing used by the archived tables here.
Keep the archived tables to reproduce this example. To obtain a new profile
at that resolution, use a model interface that supports the finer grid and
export a compatible table, or construct a PSF from your own model. A 1 km
request creates a different, coarser atmosphere and should be recorded as such.

### Convert the atmosphere

Merge and validate all downloaded tables while converting them to
`simulation.psf`:

```bash
atris-nrlmsis-to-psf nrlmsis-*.txt --output simulation.psf
```

The overlapping boundary rows allow the converter to replace a malformed row
from one response with the valid copy from the next. It rejects conflicting
duplicates, missing altitude levels, mismatched request parameters, and
non-finite, zero, or negative atmospheric values.

Convert the PSF to the Geant4 geometry `simulation.gdml`:

```bash
atris-psf-to-gdml simulation.psf
```

## Prepare the phantom inputs

Copy and stage the example's two-phantom selection:

```bash
cp "$ATRIS_ROOT/examples/earth-nrlmsis-full/phantoms.txt" .
atris-stage-phantoms .
```

## Prepare the particle inputs

Generate inputs with the default energy grid and particle counts. The values
are written out explicitly below, and the fixed random seed makes the generated
macros reproducible:

```bash
atris-generate-macros . \
  --particles-per-bin 3000 \
  --alpha-factor 0.66 \
  --random-seed 12345 \
  --energy-min-power 0 \
  --energy-max-power 6 \
  --energy-points 121
```

These are the `atris-generate-macros` defaults except for `--random-seed 12345`;
omitting that option generates new random seeds. With 121 energy points, AtRIS
will process 363,000 proton events (`121 x 3000`) and 239,580 alpha events
(`121 x int(3000 x 0.66)`).

## Physics choices and execution

Use `FTFP_BERT_HP` and `response` output for
this example. It includes two phantoms. The prepared files now define the
simulation; no events have run yet.

Choose [local](../running-atris/run-locally.md),
[server/workstation](../running-atris/run-on-server.md), or
[HPC](../hpc.md) execution. First [prepare a chunk plan](../running-atris/plan-chunks.md);
the runner reads the phantom count from `phantoms.txt`.

Start with [a few chunks](files-through-workflow.md#6-plan-and-run-chunks),
[gather and inspect their results](../running-atris/process-results.md), and
[decide whether to continue](../running-atris/process-results.md#decide-whether-to-continue). This keeps the same
atmosphere, energy range, and particle inputs.

After a chunk completes, [gather, post-process, and plot](../running-atris/process-results.md).

## Prepared reference files

The example retains the downloaded atmosphere tables and generated
AtRIS input files. Simulation outputs, plots, logs, and staged phantom links
are not included.

As an alternative to generating the inputs above, copy the prepared example
into a fresh run directory. Do not repeat this in a directory already used for
a simulation:

```bash
mkdir earth-nrlmsis-full
cd earth-nrlmsis-full
cp -R "$ATRIS_ROOT/examples/earth-nrlmsis-full/." .
atris-stage-phantoms .
```


**Next step:** [Plan chunks for the prepared simulation](../running-atris/plan-chunks.md).
