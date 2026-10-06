# Run on a local computer

**Previous step:** [Plan chunks and restarts](plan-chunks.md).

**Next step:** [Process the completed results](process-results.md).

Work inside the prepared run directory. These commands use `FTFP_BERT_HP` and
`response`; substitute your settings if they differ.

## Run a few chunks first

Choose a thread count suitable for your computer and run a selected entry:

```bash
export G4FORCENUMBEROFTHREADS=4
atris-run . --entry 1 --physics-list FTFP_BERT_HP --mode response
```

Repeat with other entries as needed, then
[inspect the results](process-results.md). The
[Earth tutorial](../tutorials/run-earth-simulation.md#1-plan-and-run-chunks)
shows the entry numbers for its proton and alpha chunks.

## Continue and monitor

Run the remaining plan in the foreground:

```bash
atris-run . --physics-list FTFP_BERT_HP --mode response
```

Progress appears in the terminal; detailed per-chunk logs are under `chunks/`.
See [continuing and resuming](run-simulation.md#continue-the-run) for completion
checks and restart behaviour, or the [executable reference](../reference/executable.md)
to diagnose an individual executable failure.

**Previous step:** [Plan chunks and restarts](plan-chunks.md).

**Next step:** [Process the completed results](process-results.md).
