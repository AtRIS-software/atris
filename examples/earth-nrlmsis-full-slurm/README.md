# Full Earth atmosphere on Slurm

This is a ready-to-submit Slurm version of the
[full Earth example](../earth-nrlmsis-full/README.md). It uses one five-node
allocation as a persistent pool of 20 AtRIS workers, rather than submitting
one short Slurm job for every chunk.

The supplied simulation script assumes five nodes with 80 physical CPU cores
each. Four workers run on each node and every worker receives 20 cores:

```text
5 nodes x 4 workers/node x 20 cores/worker = 400 allocated cores
```

Change the `#SBATCH` account, partition, QoS, memory, and resource values as
required by the cluster. The general sizing and recovery model is described in
[Running AtRIS on an HPC system](../../docs/hpc.md).

## 1. Prepare the run directory

Run these commands on the login node from `<ATRIS_WORK>`. The prepared Earth
inputs are copied to a separate run directory so the committed example remains
unchanged.

```bash
source atris/setup_atris.sh
mkdir -p runs
cp -R "$ATRIS_ROOT/examples/earth-nrlmsis-full" \
  runs/earth-nrlmsis-full-slurm
cd runs/earth-nrlmsis-full-slurm

atris-stage-phantoms .
atris-scatter --chunks 60 --random-seed 12345
```

The full example contains 363,000 proton events and 239,580 alpha events.
Sixty chunks per species divides both totals exactly:

```text
protons: 363000 / 60 = 6050 events/chunk
alphas:  239580 / 60 = 3993 events/chunk
```

This creates 120 plan entries. The plan lists the 60 proton entries followed
by the 60 alpha entries; round-robin assignment therefore gives each of the 20
workers three proton chunks and three alpha chunks. The chunks are intended to
run much faster than the eight-hour allocation, so only one active chunk is at
risk if a worker is stopped. Confirm that assumption with a pilot chunk on the
target cluster. The default 30-minute safety window should exceed the slowest
chunk plus output-flush time; otherwise increase `--chunks` in a new clean run
directory and/or set a larger `ATRIS_STOP_BEFORE_END` before submission.

## 2. Submit the simulation pool

Submit from the run directory prepared above. Keep the shell in which
`setup_atris.sh` was sourced; Slurm normally exports that environment to the
compute nodes.

```bash
simulation_submission=$(sbatch --parsable \
  "$ATRIS_ROOT/examples/earth-nrlmsis-full-slurm/run-atris.slurm.sh")
simulation_job=${simulation_submission%%;*}
echo "$simulation_job"
```

The script requests:

| Resource | Value |
|---|---:|
| Nodes | 5 |
| AtRIS workers | 20 total, 4 per node |
| CPU cores | 20 per worker, 400 total |
| Hardware threads | disabled with `--hint=nomultithread` |
| Wall time | 8 hours |
| Safety window | stop starting chunks 30 minutes before allocation end |

Each worker is an `srun` task. AtRIS receives its 20 cores through
`G4FORCENUMBEROFTHREADS`. The Slurm wrapper translates each task's rank and the
allocation deadline into scheduler-neutral `atris-run` arguments; the worker
rank selects a disjoint round-robin share of `chunks.txt`. Completed chunks are
recorded by `chunks/*.COMPLETE`.

Monitor the allocation and worker log with:

```bash
squeue -j "$simulation_job"
tail -f "chunks/slurm-${simulation_job}.out"
find chunks -maxdepth 1 -name '*.COMPLETE' -type f | wc -l
wc -l chunks.txt
```

The two counts should both be 120 at completion. The submission command removes
the optional cluster suffix from `sbatch --parsable` output, leaving the
numeric ID used by `squeue`, dependencies, and log names.

When the allocation ends, verify the durable completion markers:

```bash
atris-run --check-complete
```

If this reports incomplete entries, submit the same simulation script again.
All completed entries are skipped, so only missing work is repeated. Do not
overlap two simulation allocations for the same run directory.

## 3. Gather and plot

After the completion check succeeds, submit the single-writer gather job:

```bash
gather_submission=$(sbatch --parsable \
  "$ATRIS_ROOT/examples/earth-nrlmsis-full-slurm/gather-atris.slurm.sh")
gather_job=${gather_submission%%;*}
echo "$gather_job"
```

It checks completeness again, then runs `atris-gather`, `atris-postprocess`,
and `atris-plot`. Logs are written to `chunks/gather-<job-id>.out` and `.err`.

If a simulation allocation is expected to finish all remaining work, the
gather can instead be queued immediately with an `afterok` dependency:

```bash
simulation_submission=$(sbatch --parsable \
  "$ATRIS_ROOT/examples/earth-nrlmsis-full-slurm/run-atris.slurm.sh")
simulation_job=${simulation_submission%%;*}
gather_submission=$(sbatch --parsable --dependency="afterok:${simulation_job}" \
  "$ATRIS_ROOT/examples/earth-nrlmsis-full-slurm/gather-atris.slurm.sh")
gather_job=${gather_submission%%;*}
```

The simulation job deliberately returns failure while any plan entries remain,
so `afterok` cannot release the gather job on partial output. For runs likely
to require several allocations, submit and verify the simulation pool until it
is complete, then submit the gather job without a dependency.

## 4. Extend the run if it has not converged

After the gather job finishes, inspect `protons.convergence.png` and
`alphas.convergence.png`. If more independent samples are required, append one
new proton and one new alpha chunk per worker:

```bash
atris-scatter --extend 20
wc -l chunks.txt
```

The plan grows from 120 to 160 entries. Existing outputs and completion markers
are unchanged. With 20 workers, every worker receives one new proton and one new
alpha chunk. This batch adds exactly:

```text
protons: 20 x 6050 = 121000 events; 484000 cumulative
alphas:  20 x 3993 =  79860 events; 319440 cumulative
```

No generator seed is required: every AtRIS seed pair is stored in `chunks.txt`
and new pairs are checked against the full plan. Add `--random-seed <integer>`
only if the extension itself must be reproducible.

Submit the simulation pool again:

```bash
simulation_submission=$(sbatch --parsable \
  "$ATRIS_ROOT/examples/earth-nrlmsis-full-slurm/run-atris.slurm.sh")
simulation_job=${simulation_submission%%;*}
echo "$simulation_job"
```

After it finishes, verify and gather the extended plan:

```bash
atris-run --check-complete
gather_submission=$(sbatch --parsable \
  "$ATRIS_ROOT/examples/earth-nrlmsis-full-slurm/gather-atris.slurm.sh")
gather_job=${gather_submission%%;*}
echo "$gather_job"
```

Repeat this extend, run, and gather cycle until the convergence criteria for the
scientific analysis are satisfied. Never extend the plan while a simulation or
gather job for that run directory is active.
