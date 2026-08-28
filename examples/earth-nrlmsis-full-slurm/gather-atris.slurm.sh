#!/bin/bash

# Gather and analyse a completed full-Earth run. This deliberately uses one
# small task: gathering is a single-writer operation and must not run in
# parallel with the simulation pool.

#SBATCH --job-name=atris-gather
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=01:00:00
#SBATCH --mem=8G
#SBATCH --export=ALL
#SBATCH --output=chunks/gather-%j.out
#SBATCH --error=chunks/gather-%j.err

set -eu
set -o pipefail

cd "${SLURM_SUBMIT_DIR:-$PWD}"

# Refuse to aggregate a partial run. If this fails, resubmit the simulation
# pool; completed markers ensure only unfinished chunks are run.
atris-run --check-complete
atris-gather
atris-postprocess
MPLBACKEND=Agg atris-plot
