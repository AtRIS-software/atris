# Run on a server or workstation

**Previous step:** [Plan chunks and restarts](plan-chunks.md).

**Next step:** [Process the completed results](process-results.md).

Use this guide for an SSH session on a shared machine without a job scheduler.
For a scheduled cluster allocation, use the [HPC guide](../hpc.md).

## Prepare the session and inputs

Log in and enter your [prepared run directory](prepare-simulation.md), with
AtRIS and Geant4 available. See [UiO setup](use-atris-on-uio.md) for Ivan's
installation and resource policies. If transferring a prepared directory,
include the targets of its phantom links; `atris-stage-phantoms . --copy`
keeps them local.

The commands below use `FTFP_BERT_HP` and `response`; substitute your prepared
settings if they differ. Check `uptime` and `top` before choosing a thread count.

## Run a few chunks first

Start with a selected entry in the foreground:

```bash
export G4FORCENUMBEROFTHREADS=4
nice -n 10 atris-run . --entry 1 --physics-list FTFP_BERT_HP --mode response
```

Repeat with other plan entries to sample each species, then
[process and inspect them](process-results.md). Keep the SSH session open while
this foreground command runs. For a single chunk that must survive logout,
add `--entry N` to the background command below.

## Keep a chunked run running after logout

From the same run directory, launch the remaining plan in the background:

```bash
export G4FORCENUMBEROFTHREADS=4  # example: choose for this machine and current load
nohup nice -n 10 atris-run . --physics-list FTFP_BERT_HP --mode response >> atris-run.log 2>&1 < /dev/null &
```

`atris-run` does not background itself or set its own priority. Here, `nohup`
protects it from ordinary terminal hangup, `nice -n 10` lowers CPU scheduling
priority, and `&` returns the prompt. Chunks execute sequentially using the
selected Geant4 thread count.

### Inspect or stop the background runner

To inspect your own CPU and memory use, run:

```bash
top -u "${USER}"
```

Press `q` to leave `top`. While you are still in the shell that launched the
runner, `jobs -l` shows its shell job number. You can bring it back to the
foreground and then stop it with Ctrl+C:

```bash
jobs -l
fg %1
```

Replace `%1` with the job number shown by `jobs`. Shell job numbers belong to
the launching shell, so `fg` is not available after logging out and back in.

After reconnecting, use `top -u "${USER}"` to find the active process named
`AtRIS`; its PID is in the first column. To stop it from inside `top`, press
`k`, enter that PID, and accept signal 15. Alternatively, press `q` and run
`kill PID`, replacing `PID` with the number shown by `top`. The runner then
reports that chunk as failed and exits.

Overall progress is appended to `atris-run.log`; each chunk's detailed output
is written under `chunks/`. Watch the overall log with:

```bash
tail -f atris-run.log
```

Ctrl+C stops `tail`, not the background calculation. For restarting the runner
or checking completion, see [continuing and resuming](run-simulation.md#continue-the-run).

**Previous step:** [Plan chunks and restarts](plan-chunks.md).

**Next step:** [Process the completed results](process-results.md).
