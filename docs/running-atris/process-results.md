# Process and inspect results

**Previous step:** [Run the simulation](run-simulation.md).

Work in the run directory containing the prepared inputs and chunk outputs.
The same commands apply after your first chunks and as more finish, including
while other chunks are running.

## Gather completed chunks

```bash
atris-gather .
```

`atris-gather` adds the histograms from completed chunks, identified by their
`.COMPLETE` markers. It writes combined results for each particle species in
the run directory, using the same CSV or ROOT format as the chunks.
Unfinished chunks are ignored.

Run one gather process at a time for that directory, and let it finish before
processing the combined results.

## Normalize and plot

After gathering, run these commands in order:

```bash
atris-postprocess .
atris-plot .
```

Post-processing needs `simulation.psf`, the species inputs, and optional
`phantoms.txt` alongside the gathered histograms. It produces ionizing and
total energy-deposition response tables (`.ioni` and `.edep`) for each
available species and, when phantoms are selected, `.doseN`, `.equiN`, and
`.ratesN` tables. See [output compatibility](../reference/outputs.md#processed-response-tables)
when processing older files.

Plotting creates species result images such as `protons.png` and `alphas.png`,
plus phantom result images when applicable. It also plots available model,
source, and phantom inputs. It does not gather or normalize data itself.
For a complete worked set of filenames and input/output tables, see the
[workflow tutorial](../tutorials/run-earth-simulation.md#3-process-response-tables-and-plots).

## Interpret and update the results

The processed tables describe the average response to one incoming particle,
for each energy bin. To calculate rates such as ion pairs per second, combine
these responses with a spectrum describing how many particles arrive at each
energy. See
[normalization and uncertainty](../background/normalization-and-uncertainty.md)
for interpretation and [Output files](../reference/outputs.md) for column
definitions, units, and formulas.

For a worked continuation of the Earth example, use the Jupyter notebook
[Fold the Earth responses with a cosmic-ray spectrum](../tutorials/earth-spectrum-folding.ipynb)
at `docs/tutorials/earth-spectrum-folding.ipynb`. It uses protons and one water
phantom to work through ionization and absorbed dose rates for an incident spectrum.
[View notebook](../tutorials/earth-spectrum-folding.ipynb) or download
{download}`earth-spectrum-folding.ipynb <../tutorials/earth-spectrum-folding.ipynb>`.

Unsampled energy bins have no response estimate and may contain undefined
values. Inspect the sampling before interpreting the plots. Use the [ionization convergence diagnostics](../reference/chunks.md#convergence-csv)
to track the sampling as chunks accumulate.

As more chunks finish, repeat `atris-gather`, `atris-postprocess`, and
`atris-plot` in that order. This updates the aggregate, response tables, and
plots to include the newly completed work.

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

The first results may suggest changes to the setup before continuing. You can
revise it in the same directory or use another directory if you want to retain
the earlier run. Changing inputs does not automatically invalidate old chunk
outputs, completion markers, or gathered results; those still represent the
earlier setup. Account for that when rerunning and gathering so incompatible
results are not combined.

Completing a plan and reaching adequate statistics are separate decisions.
Continue inspecting the accumulating results and assess convergence for the
quantities you need.

## Need more statistics?

[Extend the chunk plan](plan-chunks.md#extend-a-run) to add more samples.
For changes to the physical setup, see [the considerations above](#decide-whether-to-continue).

For submitting processing through Slurm, see
[Process results in a Slurm job](../hpc.md#process-results-in-a-slurm-job).

**Previous step:** [Run the simulation](run-simulation.md).
