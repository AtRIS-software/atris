# Full Earth atmosphere example

This example prepares a full Earth run from an NRLMSIS 2.0 atmosphere. The
profile is for 18 August 2026 at 00:00 UTC, 55 degrees north and 45 degrees
east, covering 0 to 100 km in 0.2 km steps.

For a concrete five-node worker-pool setup, see the
[Slurm version of this example](../earth-nrlmsis-full-slurm/README.md).

The particle inputs use the `atrismacrogen` defaults: 121 logarithmically
spaced energy points, 3000 protons per point, and 1980 alpha particles per
point. This produces 363,000 proton events and 239,580 alpha events.

## Create the run directory

From `<ATRIS_WORK>`, prepare the shell and create an empty run directory:

```bash
source atris/setup_atris.sh
mkdir -p runs/earth-nrlmsis-full
cd runs/earth-nrlmsis-full
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

To use a different UTC time or coordinates, open the
[NASA CCMC NRLMSIS Instant Run](https://kauai.ccmc.gsfc.nasa.gov/instantrun/nrlmsis/)
page and select NRLMSIS 2.0. Choose the new time and coordinates, and retain
the 0 to 100 km range and 0.2 km step for this full-resolution setup.

The service returns at most 150 rows and can produce a malformed final row.
Use four overlapping quarter-atmosphere ranges:

```text
0.0 to 25.0 km
25.0 to 50.0 km
50.0 to 75.0 km
75.0 to 100.0 km
```

Save the responses as `nrlmsis-000.txt`, `nrlmsis-025.txt`,
`nrlmsis-050.txt`, and `nrlmsis-075.txt`.

### Convert the atmosphere

Merge and validate all downloaded tables while converting them to
`simulation.psf`:

```bash
nrlmsis2psf nrlmsis-*.txt --output simulation.psf
```

The overlapping boundary rows allow the converter to replace a malformed row
from one response with the valid copy from the next. It rejects conflicting
duplicates, missing altitude levels, mismatched request parameters, and
non-finite, zero, or negative atmospheric values.

Convert the PSF to the Geant4 geometry `simulation.gdml`:

```bash
psf2gdml simulation.psf
```

## Prepare the particle inputs

Generate inputs with the default energy grid and particle counts. The values
are written out explicitly below, and the fixed random seed makes the generated
macros reproducible:

```bash
atrismacrogen \
  --particles-per-bin 3000 \
  --alpha-factor 0.66 \
  --random-seed 12345 \
  --energy-min-power 0 \
  --energy-max-power 6 \
  --energy-points 121
```

These are the `atrismacrogen` defaults except for `--random-seed 12345`;
omitting that option generates new random seeds. With 121 energy points, AtRIS
will process 363,000 proton events (`121 x 3000`) and 239,580 alpha events
(`121 x int(3000 x 0.66)`).

## Prepare the phantom inputs

Copy and stage the same two-phantom selection used by the reduced example:

```bash
cp "$ATRIS_ROOT/examples/earth-nrlmsis-full/phantoms.txt" .
atris-stage-phantoms .
```

## Scatter and run the example

Divide each particle species into 1,210 independently seeded chunks:

```bash
atris-scatter --chunks 1210 --random-seed 12345
```

This preserves those totals: each proton chunk contains 300 events, and each
alpha chunk contains 198 events.

Each line in `chunks.txt` runs one chunk. The chunks are independent and may be
run in sequence or concurrently. Chunking splits the fixed total workload; it
does not duplicate events or reduce the total computation. It provides partial
output and allows interrupted runs to continue without repeating completed
chunks. On a larger system, independent chunks can also run on separate nodes.

Run the incomplete chunks sequentially. Completed outputs begin appearing in
`chunks/` while this command continues with the remaining work:

```bash
export G4FORCENUMBEROFTHREADS=4
atris-run
```

The command skips chunks already marked `COMPLETE`, so it can be interrupted
and run again without repeating completed work. Raw AtRIS output is written to
one log file per chunk. On an Apple M1 using four worker threads, the first
300-event proton chunk produced its result files after about two and a half
minutes and completed in about two minutes and 47 seconds.

Gather the completed chunks, then post-process and plot the results:

```bash
atris-gather
postprocess
atris-plot
```

If the convergence plots show that more independent samples are required, stop
all runners and append another batch without repeating completed work:

```bash
atris-scatter --extend 20
atris-run
atris-gather
atris-postprocess
atris-plot
```

The extension reuses the existing per-chunk event counts and reports the added
and cumulative event totals. Its seed-generator argument is optional because
the actual AtRIS seed pairs are recorded in `chunks.txt`.

## Prepared reference files

The committed example retains the downloaded atmosphere tables and generated
AtRIS input files. Simulation outputs, plots, logs, and staged phantom links
are not included.

To run the prepared inputs directly, copy the example to another run directory:

```bash
cd <ATRIS_WORK>
cp -R "$ATRIS_ROOT/examples/earth-nrlmsis-full" runs/earth-nrlmsis-full-prepared
cd runs/earth-nrlmsis-full-prepared
atris-stage-phantoms .
```
