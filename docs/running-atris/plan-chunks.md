# Plan chunks and restarts

**Previous step:** [Prepare the simulation](prepare-simulation.md).

**Next step:** [Run the chunk plan](run-simulation.md).

A chunk is an independently seeded batch of primary histories using the same
planet, source, phantoms, and physics as the rest of the run. Chunking lets you
retain completed work after an interruption and inspect results while the
calculation continues. It divides histories, not the planet into spatial regions.

Start with the species inputs from [simulation preparation](prepare-simulation.md).
The total event count is already specified; this step partitions the work for
local, server, or HPC execution. Each worker runs one chunk at a time, and each
AtRIS process can use several Geant4 threads.

## Create a plan once

From a fresh prepared run directory:

```bash
atris-scatter . --chunks 20 --random-seed 12345
```

Twenty is an illustrative count per species, not a recommended size for every
simulation. Choose the count using measured chunk runtimes below. The command
creates `chunks.txt`, species `.chunk.mac` files, and `chunks/`; it does not run
particles. See [the chunk reference](../reference/chunks.md) for event rounding
and file details. Do not scatter again on an existing plan.

## Choose a practical chunk size

There is no checkpoint inside an AtRIS chunk. If a worker is killed during a
chunk, that chunk restarts from the beginning. Previously completed chunks stay
safe.

Chunk size is a compromise between repeated startup/output overhead and the
amount of work at risk. Every chunk starts a new AtRIS process, initializes the
geometry and physics, and writes its results before it can be marked complete.
Initialization and final output include serial, single-processor work; adding
Geant4 transport threads does not speed up those parts. Very small chunks
repeat this overhead frequently and can leave most allocated cores idle during
startup and writing.

Larger chunks spend a greater fraction of their time transporting particles,
but an interruption can discard more computation: the active chunk must be
rerun, even if some output files have already appeared. Smaller chunks make
completed results durable more often and reduce that exposure, at the cost of
more frequent process restarts and writes. Completed chunks remain reusable;
there is no recovery partway through an unfinished chunk.

Measure the full cycle on the target machine, including initialization and
final writing, rather than timing only event transport. Compare a few event
counts and choose a chunk size that keeps this overhead modest while limiting
lost work to an acceptable interval. With several workers, one active chunk
per worker is at risk if the entire allocation stops.

Use a short pilot to measure typical and slow-tail chunk times. Then choose:

- a chunk runtime much shorter than the available run time, so every worker
  normally completes many chunks;
- for Slurm, `ATRIS_STOP_BEFORE_END` longer than a slow chunk plus output-flush margin;
- enough events per chunk to amortize AtRIS startup and fixed histogram I/O.

For example, chunks lasting tens of minutes may be appropriate for a multi-hour
run, but measure rather than assuming this is a suitable duration.

Benchmark several thread counts using `G4FORCENUMBEROFTHREADS` (or the matching
`--cpus-per-task` allocation on Slurm). Compare throughput across the available
machine, not just the duration of one chunk. Several smaller concurrent workers
may produce more results per hour than one process using every core.

The event count of an existing chunk cannot be changed safely because every
plan entry shares its species' chunk macro. Changing chunk size or simulation
configuration therefore requires a new clean run directory.


## Launch and resume

Continue with [Run the simulation](run-simulation.md) and the instructions for
your execution environment. First run a few selected entries, gather and inspect
them, and decide whether to continue the remaining plan. Each method uses the
plan prepared here, so those first chunks are retained if you continue.
Completed chunks have `.COMPLETE` markers; rerunning skips these and repeats
unfinished chunks. Never launch overlapping workers for the same entries.

As soon as a chunk finishes, you can [gather and inspect its results](process-results.md)
while the remaining chunks continue running. Gather the raw histograms before
normalizing them. ROOT interface and step ntuples remain per chunk and are not
merged by gathering.

Preserve the inputs, plan, and software versions with the results. Unique seed
pairs distinguish the chunks, but identical seeds alone do not reproduce a run
across changed software, physics, or execution settings.

## Extend a run

If the response needs more Monte Carlo statistics, stop all runners before
appending another batch. For example:

```bash
atris-scatter . --extend 20
```

This adds 20 chunks per species at the existing per-chunk event count. Choose
the additional count for the statistics and runtime needed. Existing seeds,
macros, outputs, and completion markers are retained; the new entries receive
unique seed pairs. Resume with the same execution command or scheduler script.

Gather and inspect the additional completed chunks to reassess convergence.
Do not extend a run with changed geometry, source, phantoms, physics, or chunk
size: those changes require a separate run directory. See the
[plan format and extension rules](../reference/chunks.md#creation-and-extension)
for exact file behavior.

**Previous step:** [Prepare the simulation](prepare-simulation.md).

**Next step:** [Run the chunk plan](run-simulation.md).
