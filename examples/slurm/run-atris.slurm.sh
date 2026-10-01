#!/bin/bash

# AtRIS simulation pool for nodes with 80 physical CPU cores.
# Twenty long-lived workers share five nodes; each worker receives 20 cores and
# runs its own disjoint share of chunks.txt until that share is complete.

#SBATCH --job-name=atris
#SBATCH --nodes=5
#SBATCH --ntasks=20
#SBATCH --ntasks-per-node=4
#SBATCH --cpus-per-task=20
#SBATCH --hint=nomultithread
#SBATCH --time=08:00:00
#SBATCH --export=ALL
#SBATCH --output=chunks/slurm-%j.out
#SBATCH --error=chunks/slurm-%j.err

set -eu
set -o pipefail

# setup_atris.sh defines ATRIS_ROOT and places the AtRIS commands on PATH.
# Slurm exports that prepared submission environment to the batch job by
# default. Increase this if a measured slow chunk needs more than 30 minutes.
: "${ATRIS_ROOT:?Run 'source atris/setup_atris.sh' before sbatch}"
export ATRIS_STOP_BEFORE_END="${ATRIS_STOP_BEFORE_END:-1800}"

cd "${SLURM_SUBMIT_DIR:-$PWD}"

# Give every AtRIS process exactly the cores assigned to its Slurm task.
export G4FORCENUMBEROFTHREADS="$SLURM_CPUS_PER_TASK"

# Launch one long-lived worker per Slurm task. Each worker receives a disjoint
# round-robin share of chunks.txt and stops before the allocation deadline.
srun \
    --ntasks="$SLURM_NTASKS" \
    --cpus-per-task="$SLURM_CPUS_PER_TASK" \
    --cpu-bind=cores \
    --kill-on-bad-exit=0 \
    --label \
    bash -c '
        exec atris-run \
            --worker-index "${SLURM_PROCID:?Missing Slurm task rank}" \
            --worker-count "${SLURM_NTASKS:?Missing Slurm task count}" \
            --deadline "${SLURM_JOB_END_TIME:?Missing Slurm job deadline}" \
            --stop-before-end "$ATRIS_STOP_BEFORE_END"
    '

# A safety stop is not final success. Return failure while any entries remain
# so an afterok gather job cannot consume partial output.
atris-run --check-complete
