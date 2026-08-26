#!/bin/bash

# Submit this file as an array job from a prepared AtRIS run directory. The
# directory must contain chunks.txt, the shared proton/alpha inputs, and the
# chunks/ directory created by atrismacrogen --runs. The shell submitted to
# Slurm must already have ATRIS_EXECUTABLE and the Geant4 environment set.

#SBATCH --job-name=atris
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=40
#SBATCH --time=01:00:00
# Keep each array task's scheduler output beside its simulation output.
#SBATCH --output=chunks/slurm-%A_%a.out
#SBATCH --error=chunks/slurm-%A_%a.err

# Stop on failed commands, unset variables, and failures inside pipelines.
set -eu
set -o pipefail

# SLURM_SUBMIT_DIR is the run directory from which sbatch was invoked.
cd "$SLURM_SUBMIT_DIR"

# Restrict Geant4 to the CPU cores allocated to this array task.
export G4FORCENUMBEROFTHREADS="$SLURM_CPUS_PER_TASK"

# Array indices are one-based and map directly to lines in chunks.txt. awk
# fails the task when an index does not have a corresponding plan entry.
awk -v line="$SLURM_ARRAY_TASK_ID" \
    'NR == line { print; found = 1 } END { if (!found) exit 1 }' chunks.txt |
while read -r simulation seed1 seed2; do
    # AtRIS extracts the seeds from this output prefix while reading the shared
    # species-named .mac, .gdml, and .bins files from the run directory.
    run_name="${simulation}_${seed1}_${seed2}"
    complete="chunks/${run_name}.COMPLETE"

    # A successful earlier attempt needs no work when the array is resubmitted.
    if [[ -f "$complete" ]]; then
        echo "$run_name is already complete"
        exit 0
    fi

    "$ATRIS_EXECUTABLE" FTFP_BERT_HP "chunks/$run_name" -1 1

    # set -e reaches this line only after AtRIS exits successfully. Failed or
    # timed-out chunks therefore remain unmarked and are retried on resubmission.
    touch "$complete"
done
