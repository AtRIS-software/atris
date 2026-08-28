#!/bin/bash

# Full-Earth AtRIS simulation pool for nodes with 80 physical CPU cores.
# Twenty long-lived workers share five nodes; each worker receives 20 cores and
# runs its own disjoint share of chunks.txt until that share is complete.

#SBATCH --job-name=atris-earth
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

# Reuse the generic worker-pool wrapper. Its own #SBATCH lines are comments
# here because this file is already running inside the allocation above.
exec bash "$ATRIS_ROOT/examples/run-atris.slurm.sh"
