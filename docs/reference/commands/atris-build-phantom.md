# atris-build-phantom

Run a bounded number of batches in a water-sphere calibration prepared with
`atris_tools.phantom_builder.PhantomBuilder`, or refresh its exports.
See [building phantoms](../../running-atris/build-phantoms.md) for the procedure.

The command opens a `PhantomBuilder` with `PhantomBuilder.open(run_directory)`
and calls its `run()` method with the requested batches, threads and adaptive
selection. With `--postprocess-only`, it gathers and saves completed statistics
and draws the diagnostics.

**Inputs:** `phantom-build.json`, its hash-verified `simulation.psf`, and
`batches.json` in the run directory. Running transport also requires the installed
`atris-run` command and native `AtRIS` executable on `PATH`.

**Outputs:** numbered `batches/batch-*` directories containing geometry, macros,
seeds and native chunk output; appended batch records; and refreshed named files
in the run directory: `<name>_response.txt`, `<name>_counting.txt`,
`<name>_sampling.root`, `<name>_diagnostics.png`,
`<name>_sampling-precision.png`, and `<name>_sampling-state.json`.
The command does not create or change `phantoms.txt`. Select completed tables
explicitly using [phantom selection and staging](../../running-atris/prepare-simulation.md#optionally-select-phantoms).

Batch records store the requested event ceiling as `events` and the actual
completed primary count as `completed_events`. Time-shortened batches contribute
both their saved statistics and measured throughput. Forecasts use completed
counts from matching species, energy ranges and thread counts; the time budget
caps predicted accumulation. Interrupted-clock measurements are excluded.

**Overwrite behaviour:** completed batch outputs and inputs are retained. A
pending batch is rerun with unchanged inputs after archiving its partial
ROOT/log/FAILED files to `interrupted-*`. Batch records and generated exports
are replaced atomically. Different build settings require another directory.
The process lock prevents simultaneous builders in the same directory.

## Arguments and options

`--time-limit` sets the event-loop budget per batch in seconds, passed to native
transport as `ATRIS_TIME_LIMIT`. Python uses `builder.run(time_limit_s=60)` for a
one-minute budget. Omitting it leaves batches event-limited. Each batch records
`time_limit_seconds`, `completed_events`, `event_loop_seconds` and `wall_seconds`;
the latter includes
launch, initialization and output writing. Interrupted batches resume their
saved inputs with the budget supplied to the new invocation.

The following is the command's `--help` output for this revision.

```text
usage: atris-build-phantom [-h] [--version] [--batches BATCHES] [--adaptive]
                           [--threads THREADS] [--time-limit TIME_LIMIT]
                           [--postprocess-only]
                           run_directory

Run or inspect a prepared spherical phantom build.

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
