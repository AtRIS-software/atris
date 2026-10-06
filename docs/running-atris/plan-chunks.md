# Plan chunks and restarts

**Previous step:** [Prepare the simulation](prepare-simulation.md).

**Next step:** [Run the chunk plan](run-simulation.md).

A **chunk** is a batch of simulated particles with its own random seeds. Each
incoming particle and the secondaries it produces form one event. All chunks
use the same planet model, particle source, phantom tables, and physics.

Each running copy of `atris-run`, called a worker, handles one chunk at a time.
The AtRIS process it starts can use several CPU threads.

## Create a chunk plan

From the prepared run directory:

```bash
atris-scatter . --chunks 3000 --random-seed 12345
```

This divides the requested events into 3000 chunks per species. `chunks.txt`
lists the chunks and their random seeds, the species `.chunk.mac` files set
the events per chunk, and `chunks/` holds their outputs. See the
[chunk reference](../reference/chunks.md) for rounding and file formats.

## Choose a practical chunk size

Every chunk initializes a new AtRIS process and writes its results at the end.
Parts of initialization and writing use a single processor, so adding threads
does not shorten them. Small chunks repeat this work more often. Larger chunks
spend a greater share of their time simulating particles, but take longer to
repeat if interrupted. Completed chunks are retained; only unfinished chunks
restart from the beginning.

Measure a few complete chunk cycles, including startup and writing, to find a
useful balance between overhead and recovery time. On Slurm, allow a
[safety window](../hpc.md#wall-time-and-completion) long enough for a slow chunk
to finish. The [runtime discussion](../background/what-determines-runtime.md)
explains how layers, particle cascades, phantoms, and threads affect these costs.

Compare throughput at several thread counts using `G4FORCENUMBEROFTHREADS`.
Several smaller concurrent workers may complete more work per hour than one
process using every core.

All entries of a species share one chunk macro. Editing it affects future
execution; completed chunks retain their original event counts and settings.

## Launch and resume

Use the [execution guide](run-simulation.md) for your machine to launch selected
entries or resume the plan.

## Extend a run

To add more samples:

```bash
atris-scatter . --extend 3000
```

This appends 3000 chunks per species at the existing per-chunk event count,
with new seed pairs. Existing macros and results remain. You can extend the
plan while runners are active: they finish the assignment read at startup,
and their next invocation sees the added entries.

Extension adds sampling to the existing setup. If you have revised the physical
inputs, [account for earlier outputs](process-results.md#decide-whether-to-continue)
before combining results. See [extension rules](../reference/chunks.md#creation-and-extension)
for exact file behaviour.

**Previous step:** [Prepare the simulation](prepare-simulation.md).

**Next step:** [Run the chunk plan](run-simulation.md).
