#!/bin/bash

# This is the recommended Slurm wrapper for AtRIS. It divides the work into
# independently seeded array tasks so completed work survives timeouts and
# failed tasks can be resubmitted. Submit it from a prepared run directory
# containing chunks.txt, the shared proton/alpha inputs, and the chunks/
# directory created by atrismacrogen --runs. Before using either execution
# mode, set ATRIS_EXECUTABLE and load the Geant4 environment.
#
# Outside Slurm, run this file with Bash from the run directory. With no
# argument it processes every plan entry sequentially; an optional one-based
# line number processes only that entry.

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

# Use the Slurm submission directory in a batch job and the current directory
# when invoked directly with Bash.
cd "${SLURM_SUBMIT_DIR:-$PWD}"

# Under Slurm, restrict Geant4 to the cores allocated to this array task. A
# direct Bash run keeps the user's existing setting or AtRIS's all-core default.
if [[ -n "${SLURM_CPUS_PER_TASK:-}" ]]; then
    export G4FORCENUMBEROFTHREADS="$SLURM_CPUS_PER_TASK"
fi

# Slurm array indices and optional Bash arguments are one-based chunks.txt line
# numbers. Without either, pass every plan entry to the sequential loop.
task_id="${SLURM_ARRAY_TASK_ID:-${1:-}}"
if [[ -n "$task_id" ]]; then
    awk -v line="$task_id" \
        'NR == line { print; found = 1 } END { if (!found) exit 1 }' chunks.txt
else
    awk '{ print }' chunks.txt
fi |
while read -r simulation seed1 seed2; do
    # AtRIS extracts the seeds from this output prefix while reading the shared
    # species-named .mac, .gdml, and .bins files from the run directory.
    run_name="${simulation}_${seed1}_${seed2}"
    complete="chunks/${run_name}.COMPLETE"

    # Skip successful earlier attempts while continuing through a direct Bash
    # run that may contain other unfinished entries.
    if [[ -f "$complete" ]]; then
        echo "$run_name is already complete"
        continue
    fi

    "$ATRIS_EXECUTABLE" FTFP_BERT_HP "chunks/$run_name" -1 1

    # set -e reaches this line only after AtRIS exits successfully. Failed or
    # timed-out chunks therefore remain unmarked and are retried on resubmission.
    touch "$complete"
done
