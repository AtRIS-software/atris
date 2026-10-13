# atris-build-phantom

Run a bounded number of batches in a water-sphere calibration prepared with
`atris_tools.phantom_builder.PhantomBuild.prepare`, or refresh its exports.
See [building phantoms](../../running-atris/build-phantoms.md) for the procedure.

**Inputs:** `phantom-build.json`, its hash-verified `simulation.psf`, and
`batches.json` in the run directory. Running transport also requires the installed
`atris-run` command and native `AtRIS` executable on `PATH`.

**Outputs:** numbered `batches/batch-*` directories containing geometry, macros,
seeds and native chunk output; appended batch records; and refreshed `export/`
response/counting tables, sampling NPZ/JSON, `phantoms.txt`, `diagnostics.png`,
`sampling-precision.png`, and `sampling-state.json`.

**Overwrite behaviour:** completed batch outputs and inputs are retained. A
pending batch is rerun with unchanged inputs after archiving its partial
ROOT/log/FAILED files to `interrupted-*`. Batch records and generated exports
are replaced atomically. Different build settings require another directory.
The process lock prevents simultaneous builders in the same directory.

## Arguments and options

`--time-limit` sets the event-loop budget per batch in seconds, passed to native
transport as `ATRIS_TIME_LIMIT`. Python uses `builder.run(time_limit=60)` for a
one-minute budget. Omitting it leaves batches event-limited. Each batch records
`time_limit_seconds`, `completed_events` and `wall_seconds`; the latter includes
launch, initialization and output writing. Interrupted batches resume their
saved inputs with the budget supplied to the new invocation. Time-shortened
batches contribute their saved statistics but are excluded from count-based
runtime fits (`fit_timing=false`).

The following is the command's `--help` output for this revision.

```text
usage: atris-build-phantom [-h] [--version] [--batches BATCHES] [--adaptive]
                           [--threads THREADS] [--time-limit TIME_LIMIT]
                           [--postprocess-only]
                           run_directory

Run or inspect a prepared water-sphere phantom build.

positional arguments:
  run_directory

options:
  -h, --help            show this help message and exit
  --version             Show the AtRIS and atris-tools versions and exit.
  --batches BATCHES     Maximum new/resumed batches to run (default: 1).
  --adaptive            Refine energy uncertainty with exploration and
                        coverage turns.
  --threads THREADS     Geant4 transport threads (default: 1).
  --time-limit TIME_LIMIT
                        Event-loop time limit per batch in seconds (default:
                        event-limited).
  --postprocess-only    Read completed chunks and refresh exports/diagnostics
                        without transport.
```

Implementation: `atris_tools/phantom_builder.py`.
