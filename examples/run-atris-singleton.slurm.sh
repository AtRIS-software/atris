#!/bin/bash

# WARNING: This is a dangerous way to run a long AtRIS simulation on an HPC
# system. Each species runs as one uninterrupted calculation, so a timeout or
# failure loses that run and resubmission starts it again. The recommended,
# resumable workflow is examples/run-atris.slurm.sh.
#
# Submit this file from a prepared AtRIS run directory to run one proton and
# one alpha simulation without chunking. The run must use ordinary macros
# generated without atrismacrogen --runs so that each macro contains its seeds.
# The shell submitted to Slurm must already have ATRIS_EXECUTABLE and the Geant4
# environment set.

#SBATCH --job-name=atris-single
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=40
#SBATCH --time=01:00:00
# Keep this job's scheduler output in the run directory.
#SBATCH --output=slurm-%j.out
#SBATCH --error=slurm-%j.err

# Stop on failed commands and unset variables. If the proton run fails, the
# alpha run is not started.
set -eu

# SLURM_SUBMIT_DIR is the run directory from which sbatch was invoked.
cd "$SLURM_SUBMIT_DIR"

# Restrict Geant4 to the CPU cores allocated to this job.
export G4FORCENUMBEROFTHREADS="$SLURM_CPUS_PER_TASK"

# These runs execute sequentially and write the ordinary protons_* and alphas_*
# outputs directly. A resubmission starts them again and replaces files with the
# same names; there are no completion markers or partial-run recovery.
"$ATRIS_EXECUTABLE" FTFP_BERT_HP protons -1 1
"$ATRIS_EXECUTABLE" FTFP_BERT_HP alphas -1 1
