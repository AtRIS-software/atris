# atris-scatter

Create or extend a plan of independently seeded proton and alpha chunks.

```bash
atris-scatter . --chunks 20 --random-seed 42
atris-scatter . --extend 10 --random-seed 43
```

The directory defaults to `.`. Exactly one of `--chunks` and `--extend` is
required. Both counts are **per species** and must be at least one.

Initial inputs are `protons.mac` and `alphas.mac`; outputs are `chunks.txt`,
the two `.chunk.mac` files, and an empty `chunks/` directory. Creation refuses
existing plans/chunk macros or a nonempty chunk directory. Extension requires
an existing valid plan, chunk directory, and chunk macros. It appends new work
using the established chunk sizes rather than dividing the original total again.

See [Scatter/gather files](../chunks.md) for rounding, seeds, validation,
completion markers, and extension semantics.

## Arguments and options

The following is the command's `--help` usage and options for this revision
(the descriptive epilogue is omitted; behavior is covered above and in the
[chunk reference](../chunks.md)).

```text
usage: atris-scatter [-h] (--chunks COUNT | --extend COUNT) [--random-seed SEED]
                     [-q | -v] [--version]
                     [RUN_DIRECTORY]

Split the proton and alpha event totals in ordinary AtRIS macros into independently
seeded, restartable chunks.

positional arguments:
  RUN_DIRECTORY       Prepared run directory (default: current directory).

optional arguments:
  -h, --help          show this help message and exit
  --chunks COUNT      Create a new plan with COUNT proton chunks and COUNT alpha
                      chunks.
  --extend COUNT      Append COUNT new chunks for each species to an existing plan,
                      increasing the total simulated events.
  --random-seed SEED  Seed used to generate reproducible, unique Geant4 seed pairs for
                      the plan (default: random).
  -q, --quiet         Suppress normal progress; show warnings and errors only.
  -v, --verbose       Include detailed per-file, per-request, or per-chunk progress.
  --version           Show the AtRIS and atris-tools versions and exit.

```

Implementation: `atris_tools/scatter.py`.
