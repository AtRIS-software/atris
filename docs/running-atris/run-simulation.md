# Run the simulation

**Previous step:** [Plan chunks and restarts](plan-chunks.md).

**Next step:** [Process and inspect results](process-results.md).

Start in the prepared run directory with `chunks.txt` and the species
`.chunk.mac` files. Use the physics list and output mode selected during
[preparation](prepare-simulation.md).

| Execution environment | Job setup |
| --- | --- |
| [Local computer](run-locally.md) | Choose threads and run in a terminal |
| [Server or workstation](run-on-server.md) | Run over SSH, set priority, and survive logout |
| [HPC cluster](../hpc.md) | Request resources, launch workers, and handle wall-time limits |

## Run a few chunks first

Use your environment's launch command with `--entry N` to run one selected line
of `chunks.txt`, numbered from one. Include each particle species in the initial
sample. Then [process and inspect the results](process-results.md).
The [Earth tutorial](../tutorials/run-earth-simulation.md#1-plan-and-run-chunks)
provides a concrete example.

## Continue the run

After inspection, use the full-plan launch command from your environment's
guide. The runner skips chunks with `.COMPLETE` markers and starts unfinished
chunks from the beginning. This also resumes an interrupted run; wait for the
previous runner and its AtRIS child to exit before restarting it. Concurrent
workers must have non-overlapping assignments.

To check whether the entire plan has finished:

```bash
atris-run . --check-complete
```

This checks completion markers, not statistical convergence. You can
[inspect completed chunks](process-results.md) while the remaining work runs.

```{toctree}
:hidden:

run-locally
run-on-server
../hpc
```

**Previous step:** [Plan chunks and restarts](plan-chunks.md).

**Next step:** [Process and inspect results](process-results.md).
