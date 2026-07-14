#!/bin/bash -l
#SBATCH --job-name=atris-bare
#SBATCH --partition=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=40
#SBATCH --mem=96G
#SBATCH --time=48:00:00
#SBATCH --output=run_atris_bare.slurm.sh.stdout
#SBATCH --error=run_atris_bare.slurm.sh.stderr

set -euo pipefail

module purge
module load GCC/11.2.0

RUN_DIR="${SLURM_SUBMIT_DIR:-$PWD}"

: "${ATRIS_ROOT:?Set ATRIS_ROOT before submitting this job.}"
: "${ATRIS_EXECUTABLE:?Set ATRIS_EXECUTABLE before submitting this job.}"

if [[ -z "${GEANT4_SH:-}" && -z "${GEANT4_INSTALL:-}" ]]; then
  echo "Set GEANT4_SH or GEANT4_INSTALL before submitting this job." >&2
  exit 1
fi

cd "$RUN_DIR"
python3 -u "$ATRIS_ROOT/run_atris_bare.py" --run-profile full --threads "${SLURM_CPUS_PER_TASK:-1}"
