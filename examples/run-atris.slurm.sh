#!/bin/bash

# This is a suggested Slurm wrapper for AtRIS. One allocation launches a
# pool of long-lived workers across its nodes. Each worker repeatedly runs a
# disjoint shard of independently seeded chunks, so completed work survives
# timeouts and failed allocations can be resubmitted. Submit it from a prepared
# run directory containing chunks.txt, the shared proton/alpha inputs, and the
# chunks/ directory created by atris-scatter. Before submitting or invoking
# this wrapper, prepare the shell with `source atris/setup_atris.sh` as
# described in README.md.
#
# Outside Slurm, run this file with Bash from the run directory. With no
# argument it processes every plan entry sequentially; an optional one-based
# line number processes only that entry.

#SBATCH --job-name=atris
#SBATCH --nodes=1
# Four workers share this example node, and each AtRIS process gets four cores.
# Override nodes, tasks, tasks per node, CPUs per task, and time when submitting
# to match the cluster and measured chunk runtime.
#SBATCH --ntasks=4
#SBATCH --ntasks-per-node=4
#SBATCH --cpus-per-task=4
#SBATCH --time=04:00:00
# AtRIS output goes to one log per chunk; this file records worker progress.
#SBATCH --output=chunks/slurm-%j.out
#SBATCH --error=chunks/slurm-%j.err

# Stop on failed commands, unset variables, and failures inside pipelines.
set -eu
set -o pipefail

# Use the Slurm submission directory in a batch job and the current directory
# when invoked directly with Bash.
cd "${SLURM_SUBMIT_DIR:-$PWD}"

if [[ -n "${SLURM_JOB_ID:-}" ]]; then
    # Give every AtRIS process exactly the cores assigned to its Slurm task.
    export G4FORCENUMBEROFTHREADS="$SLURM_CPUS_PER_TASK"

    # Keep all Slurm-specific environment handling in this wrapper. Each srun
    # task translates its rank, task count, and allocation end into the generic
    # atris-run arguments. Override the safety interval with a measured
    # slow-tail chunk duration plus output-flush margin.
    export ATRIS_STOP_BEFORE_END="${ATRIS_STOP_BEFORE_END:-900}"
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

    # A wall-time safety stop is not final success. Fail the allocation while
    # any entries remain so an afterok gather job cannot consume partial output.
    atris-run --check-complete
elif [[ $# -gt 0 ]]; then
    atris-run --entry "$1"
else
    atris-run
fi
