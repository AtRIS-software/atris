# Process and inspect results

**Previous step:** [Run the simulation](run-simulation.md).

Work in the run directory containing the prepared inputs and chunk outputs.
These commands apply to local, server, and HPC runs. Use them after your first
few chunks, before deciding whether to continue the full run. Repeat them as
more chunks finish; they also work while other chunks are running.

## Gather completed chunks

```bash
atris-gather .
```

Gathering includes only planned chunks with a `.COMPLETE` marker and ignores
unfinished chunks. It combines their raw histograms into the species CSVs at
the run root. Run one gather process at a time for that directory, and let it
finish before post-processing the aggregate.

`atris-run . --check-complete` tells you whether the entire plan has finished.
A successful completion check is not required to inspect the completed subset.

## Normalize and plot

After gathering, run these commands in order:

```bash
atris-postprocess .
atris-plot .
```

Post-processing needs `simulation.psf`, the species inputs, and optional
`phantoms.txt` alongside the gathered histograms. It produces an ionization
response table (`.ioni`) for each available species and, when phantoms are
selected, `.doseN`, `.equiN`, and `.ratesN` tables.

Plotting creates species result images such as `protons.png` and `alphas.png`,
plus phantom result images when applicable. It also plots available model,
source, and phantom inputs. It does not gather or normalize data itself.
For a complete worked set of filenames and input/output tables, see the
[workflow tutorial](../tutorials/files-through-workflow.md#8-process-response-tables-and-plots).

## Interpret and update the results

The processed tables describe responses per simulated primary, resolved by
primary energy. They are not physical rates until an appropriate incident
spectrum and intensity are applied. See
[normalization and uncertainty](../background/normalization-and-uncertainty.md)
for interpretation and [Output files](../reference/outputs.md) for column
definitions, units, and formulas.

Unsampled energy bins have no response estimate and may contain undefined
values. Inspect the sampling before interpreting the plots. The gathered
`.convergence.csv` files describe ionization convergence across completed
chunks; their [definitions and limits](../reference/chunks.md#convergence-csv)
are given in Reference.

As more chunks finish, repeat `atris-gather`, `atris-postprocess`, and
`atris-plot` in that order. This updates the aggregate, response tables, and
plots to include the newly completed work. Retain the chunk outputs, plan,
and completion markers so gathering and resumption remain possible.

## Decide whether to continue

Review the first plots and logs before launching the remaining plan:

- **Inputs:** do the atmospheric profiles, composition, source energies, and
  optional phantom curves match the model you intended?
- **Responses:** are the expected species and phantom products present, and do
  their altitude and energy axes make sense? Distinguish unsampled bins from
  unexpected missing files, input-mismatch warnings, or failed chunks.
- **Cost:** does the measured chunk runtime and output size make the remaining
  calculation practical? Include initialization and writing in that timing.

If the setup looks right, [continue the existing plan](run-simulation.md#continue-the-run).
The initial chunks already contribute to the calculation; do not scatter again
or repeat completed work. Sparse early results are expected and need more
sampling before scientific interpretation.

If the model, source, phantoms, physics, output mode, or chunk size needs
changing, stop any active runners and [prepare a fresh run directory](prepare-simulation.md).
Keep the old inputs and results together so outputs from different setups are
not mixed. If the first results show that the run is not worth pursuing, leave
the remaining chunks unrun.

Completing a plan and reaching adequate statistics are separate decisions.
Continue inspecting the accumulating results and assess convergence for the
quantities you need.

## Need more statistics?

[Extend the chunk plan](plan-chunks.md#extend-a-run) after stopping the runners,
then resume with the same execution method. Gather and inspect each new
completed batch. Changing the model, source, or physics requires a separate run.

For submitting processing through Slurm, see
[Process results in a Slurm job](../hpc.md#process-results-in-a-slurm-job).

**Previous step:** [Run the simulation](run-simulation.md).
