#!/bin/bash
#SBATCH --job-name=thermal_fourier
#SBATCH --output=logs/fourier_%A_%a.out
#SBATCH --error=logs/fourier_%A_%a.err
#SBATCH --time=01:00:00
#SBATCH --mem=16G
#SBATCH --cpus-per-task=4
#SBATCH --array=1-4

# ============================================================
# Batch script for phase-encoding Fourier analysis
# Supports both volume (Option A) and surface (Option B) modes
# Runs all 4 blocks for a single subject as a SLURM array job
# ============================================================
#
# Usage:
#   sbatch run_batch.sh <subject_id> [volume|surface]
#
# Examples:
#   sbatch run_batch.sh 0001               # default: volume mode
#   sbatch run_batch.sh 0001 volume        # explicit volume mode
#   sbatch run_batch.sh 0001 surface       # surface mode (requires FreeSurfer)
#
# Without SLURM:
#   bash run_batch.sh 0001                 # runs all 4 sequentially, volume
#   bash run_batch.sh 0001 surface         # runs all 4 sequentially, surface

set -euo pipefail

SUB="${1:?Usage: sbatch run_batch.sh <subject_id> [volume|surface]}"
MODE="${2:-volume}"
SES="01"

# --- Paths (edit these for your cluster) ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIDS_DIR="/path/to/bids"                    # <-- EDIT: BIDS root directory
OUT_DIR="/path/to/derivatives/fourier"      # <-- EDIT: output directory

# --- FreeSurfer paths (Option B only) ---
# export SUBJECTS_DIR="/path/to/freesurfer/subjects"  # <-- EDIT
# TARGET_SUBJECT="fsaverage"                          # <-- EDIT (or leave empty for native)
TARGET_SUBJECT=""
PROJFRAC="0.5"
SMOOTH_FWHM="2"                                       # surface smoothing in mm (0=none)

mkdir -p "${OUT_DIR}/sub-${SUB}" logs

# --- Block definitions ---
# Run 1: NonTGI warm-first
# Run 2: NonTGI cool-first
# Run 3: TGI warm-first
# Run 4: TGI cool-first
# NOTE: --warm-first is the default, so we only need --cool-first for runs 2 and 4
DIRECTIONS=("" "--cool-first" "" "--cool-first")

# --- Determine which runs to process ---
if [ -n "${SLURM_ARRAY_TASK_ID:-}" ]; then
    RUNS=("${SLURM_ARRAY_TASK_ID}")
else
    RUNS=(1 2 3 4)
fi

# --- Load environment (edit for your cluster) ---
# module load python/3.10
# source /path/to/venv/bin/activate
# module load freesurfer/7.4    # <-- needed for surface mode

# --- Run analysis ---
for RUN in "${RUNS[@]}"; do
    RUN_FMT=$(printf "%02d" "$RUN")
    # --- File naming ---
    # Adjust the pattern below to match your actual file names.
    # Common patterns:
    #   BIDS raw:         sub-0001_ses-01_task-tprf_run-01_bold.nii.gz
    #   SPM preprocessed: arf_sub-0001_ses-01_task-tprf_run-01_bold.nii
    #   fMRIPrep:         sub-0001_ses-01_task-tprf_run-01_space-T1w_bold.nii.gz
    NIFTI="${BIDS_DIR}/sub-${SUB}/ses-${SES}/func/arf_sub-${SUB}_ses-${SES}_task-tprf_run-${RUN_FMT}_bold.nii"

    if [ ! -f "${NIFTI}" ]; then
        echo "WARNING: ${NIFTI} not found, skipping run ${RUN_FMT}"
        continue
    fi

    IDX=$((RUN - 1))
    DIR_FLAG="${DIRECTIONS[$IDX]}"

    if [ "${MODE}" = "surface" ]; then
        RUN_OUT="${OUT_DIR}/sub-${SUB}/run-${RUN_FMT}/surf"

        # Build surface-specific args
        SURF_ARGS=(
            --subject "sub-${SUB}"
            --projfrac "${PROJFRAC}"
        )
        if [ -n "${SUBJECTS_DIR:-}" ]; then
            SURF_ARGS+=(--subjects-dir "${SUBJECTS_DIR}")
        fi
        if [ -n "${TARGET_SUBJECT}" ]; then
            SURF_ARGS+=(--target-subject "${TARGET_SUBJECT}")
        fi

        echo "=== Sub-${SUB} Run-${RUN_FMT} SURFACE (${DIR_FLAG:-warm-first}, sm=${SMOOTH_FWHM}mm) ==="
        python3 "${SCRIPT_DIR}/fourier_analysis.py" surface \
            --nifti "${NIFTI}" \
            "${SURF_ARGS[@]}" \
            --smooth-fwhm "${SMOOTH_FWHM}" \
            --n-cycles 8 \
            --detrend 1 \
            ${DIR_FLAG} \
            --out-dir "${RUN_OUT}"
    else
        RUN_OUT="${OUT_DIR}/sub-${SUB}/run-${RUN_FMT}"

        echo "=== Sub-${SUB} Run-${RUN_FMT} VOLUME (${DIR_FLAG:-warm-first}) ==="
        python3 "${SCRIPT_DIR}/fourier_analysis.py" volume \
            --nifti "${NIFTI}" \
            --n-cycles 8 \
            --detrend 1 \
            ${DIR_FLAG} \
            --out-dir "${RUN_OUT}"
    fi

    echo "Done: run ${RUN_FMT}"
done

echo "All done for sub-${SUB} (mode: ${MODE})"
