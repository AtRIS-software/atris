#!/bin/bash
#SBATCH --job-name=atris
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=40
#SBATCH --time=01:00:00
#SBATCH --output=chunks/slurm-%A_%a.out
#SBATCH --error=chunks/slurm-%A_%a.err

set -eu
set -o pipefail

cd "$SLURM_SUBMIT_DIR"
export G4FORCENUMBEROFTHREADS="$SLURM_CPUS_PER_TASK"

awk -v line="$SLURM_ARRAY_TASK_ID" \
    'NR == line { print; found = 1 } END { if (!found) exit 1 }' chunks.txt |
while read -r simulation seed1 seed2; do
    run_name="${simulation}_${seed1}_${seed2}"
    complete="chunks/${run_name}.COMPLETE"

    if [[ -f "$complete" ]]; then
        echo "$run_name is already complete"
        exit 0
    fi

    "$ATRIS_EXECUTABLE" FTFP_BERT_HP "chunks/$run_name" -1 1
    touch "$complete"
done
