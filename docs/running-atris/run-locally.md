# Run on a local computer

**Previous step:** [Plan chunks and restarts](plan-chunks.md).

**Next step:** [Process the completed results](process-results.md).

Start in the run directory containing the [prepared chunk plan](plan-chunks.md),
with AtRIS and Geant4 available. The runner preserves completed outputs.
Use the physics list and output mode chosen during preparation; this example
uses `FTFP_BERT_HP` and `response`.


## Run a few chunks first

Run the first entry of the prepared plan:

```bash
export G4FORCENUMBEROFTHREADS=4
atris-run . --entry 1 --physics-list FTFP_BERT_HP --mode response
```

Four threads are an example; choose a count suitable for your computer.
`--entry` selects a one-based line of `chunks.txt`. Repeat with other entries
to include each particle species; the
[workflow tutorial](../tutorials/files-through-workflow.md#6-plan-and-run-chunks)
shows the entries for its proton and alpha chunks. Each command exits after
the selected chunk and writes its log and outputs under `chunks/`.

[Gather, process, and inspect](process-results.md) these chunks before launching
the rest. Check the setup, initial responses, and runtime, then
[decide whether to continue](process-results.md#decide-whether-to-continue).

## Continue and monitor

If the setup looks right, run all remaining chunks:

```bash
atris-run . --physics-list FTFP_BERT_HP --mode response
```

The runner skips completed chunks and executes the remaining entries sequentially
in the foreground. It reports progress and reads the phantom selection from
`phantoms.txt`; without that file it uses no phantoms. Continue gathering and
inspecting as more chunks finish.

To resume after an interruption, wait until the previous runner and its AtRIS
child have exited, then repeat `atris-run` with the same settings. Completed
chunks are skipped; unfinished chunks restart from the beginning.

## Confirm completion

```bash
atris-run . --check-complete
```

This checks whether the entire plan has finished. You can already
[gather and inspect results](process-results.md) once a chunk finishes, using
another terminal in the run directory while the runner continues.
For diagnosing an individual executable failure, see the
[direct executable reference](../reference/executable.md).

**Previous step:** [Plan chunks and restarts](plan-chunks.md).

**Next step:** [Process the completed results](process-results.md).
