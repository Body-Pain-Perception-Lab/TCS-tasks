# Phase-Encoding Fourier Analysis — Cluster Package

## What this does

Computes voxelwise (or per-vertex) **coherence**, **amplitude**, and **phase** at the stimulus frequency for a thermal pRF experiment using triangular-wave stimulation across 5 thermode zones. This is a direct Python adaptation of vistasoft's `computeCorAnalSeries.m` (traveling-wave retinotopy pipeline).

Two modes:
- **Option A (`volume`)**: Run Fourier analysis on volumetric BOLD. Quick first-pass.
- **Option B (`surface`)**: Project BOLD to cortical surface first, then Fourier per-vertex. Better for topographic mapping — avoids blurring phase values across sulcal walls.

For each voxel/vertex the analysis produces:
- **Coherence** — signal-to-noise at stimulus frequency (0–1, higher = more reliable)
- **Amplitude** — BOLD response magnitude at stimulus frequency (% signal change)
- **Phase** — position within the stimulus cycle where voxel responds maximally (0–2π rad)
- **Preferred delta** — phase mapped to preferred temperature magnitude (0–17.5 °C)
- **Preferred direction** — warming (+1) or cooling (−1) tuning

## Files in this package

```
cluster_fourier/
├── fourier_analysis.py      # Core analysis (preprocessing, FFT, phase mapping, NIfTI I/O)
├── config.py                # Experiment parameters (TR, n_cycles, max_delta, etc.)
├── masks.py                 # Thermode zone masks (dependency of config)
├── run_batch.sh             # SLURM batch script
├── requirements.txt         # Python dependencies
└── INSTRUCTIONS.md          # This file
```

## Setup

### 1. Copy to cluster

```bash
scp -r cluster_fourier/ user@cluster:/path/to/project/
```

### 2. Create Python environment

```bash
module load python/3.10    # or your cluster's python module
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2b. FreeSurfer (required for Option B only)

```bash
module load freesurfer/7.4    # or your cluster's version
export SUBJECTS_DIR=/path/to/freesurfer/subjects
```

Subjects must be reconstructed with `recon-all` before running Option B.

### 3. Edit paths in `run_batch.sh`

Open `run_batch.sh` and set:
- `BIDS_DIR` — path to your BIDS-formatted data root
- `OUT_DIR` — where to write output NIfTI files
- Module load / venv activation commands for your cluster

### 4. Expected input data layout (BIDS)

```
BIDS_DIR/
└── sub-0001/
    └── ses-01/
        └── func/
            ├── sub-0001_ses-01_task-tprf_run-01_bold.nii.gz
            ├── sub-0001_ses-01_task-tprf_run-02_bold.nii.gz
            ├── sub-0001_ses-01_task-tprf_run-03_bold.nii.gz
            └── sub-0001_ses-01_task-tprf_run-04_bold.nii.gz
```

The 4 runs correspond to:
| Run | Condition | Direction |
|-----|-----------|-----------|
| 01  | NonTGI    | warm-first |
| 02  | NonTGI    | cool-first |
| 03  | TGI       | warm-first |
| 04  | TGI       | cool-first |

**Important:** Input should be preprocessed BOLD (motion-corrected, slice-timing corrected, optionally smoothed). Do NOT use raw data. The script handles dummy volume removal and detrending internally.

## Running

### Option A: Volume mode (quick first-pass)

Single run:
```bash
python3 fourier_analysis.py volume \
    --nifti /path/to/arf_sub-0001_ses-01_task-tprf_run-01_bold.nii.gz \
    --n-cycles 8 \
    --warm-first \
    --out-dir results/sub-0001/run-01/
```

All 4 runs via SLURM array:
```bash
sbatch run_batch.sh 0001
```

All 4 runs without SLURM:
```bash
bash run_batch.sh 0001
```

Multiple subjects:
```bash
for sub in 0001 0002 0003; do
    sbatch run_batch.sh "$sub"
done
```

### Option B: Surface mode (better for topographic mapping)

**Path 1 — From volume, with 2 mm surface smoothing (recommended):**
```bash
python3 fourier_analysis.py surface \
    --nifti /path/to/arf_sub-0001_ses-01_task-tprf_run-01_bold.nii.gz \
    --subject sub-0001 \
    --subjects-dir /path/to/freesurfer/subjects \
    --projfrac 0.5 \
    --smooth-fwhm 2 \
    --n-cycles 8 \
    --warm-first \
    --out-dir results/sub-0001/run-01/surf/
```

This will:
1. Call `mri_vol2surf` to project the 4D BOLD onto lh and rh surfaces
2. Smooth the surface time series with a 2 mm geodesic Gaussian kernel (`mri_surf2surf --fwhm`)
3. Run the Fourier analysis per-vertex on each hemisphere
4. Save surface overlays (.mgz by default)

The smoothing is applied to the BOLD **time series** on the surface, BEFORE the Fourier analysis. This preserves phase information because we smooth the signal, not the circular phase map. The geodesic kernel respects cortical geometry and does not blur across sulci.

**Path 2 — From pre-computed surface time series:**

If you already projected the BOLD to the surface (e.g., using fMRIPrep or your own pipeline):
```bash
python3 fourier_analysis.py surface \
    --surface-ts lh.bold_surf.mgz rh.bold_surf.mgz \
    --n-cycles 8 \
    --warm-first \
    --out-dir results/sub-0001/run-01/surf/
```

**Resample to fsaverage (for group analysis):**
```bash
python3 fourier_analysis.py surface \
    --nifti arf_sub-0001_bold.nii.gz \
    --subject sub-0001 \
    --subjects-dir $SUBJECTS_DIR \
    --target-subject fsaverage \
    --n-cycles 8 \
    --out-dir results/sub-0001/run-01/fsavg/
```

**GIFTI output (for Connectome Workbench / HCP):**
```bash
python3 fourier_analysis.py surface \
    --nifti arf_sub-0001_bold.nii.gz \
    --subject sub-0001 \
    --subjects-dir $SUBJECTS_DIR \
    --output-format gii \
    --n-cycles 8 \
    --out-dir results/sub-0001/run-01/surf/
```

**Single hemisphere only:**
```bash
python3 fourier_analysis.py surface \
    --nifti arf_sub-0001_bold.nii.gz \
    --subject sub-0001 \
    --subjects-dir $SUBJECTS_DIR \
    --hemi lh \
    --n-cycles 8 \
    --out-dir results/sub-0001/run-01/surf/
```

## CLI options

### Common options (both modes)
```
--n-cycles N         Stimulus cycles per run (default: 8, from config)
--noise-band N       Noise band width: 0=all freqs (default), >0=bandpass ±N/2
--detrend N          Polynomial detrend order: 0=none, 1=linear, 2=quadratic (default: 1)
--dummy-volumes N    Dummy volumes to discard (default: 4, from config)
--warm-first         Warm-first stimulus order (default)
--cool-first         Cool-first stimulus order
--out-dir PATH       Output directory
```

### Volume mode only
```
--nifti PATH         4D NIfTI BOLD file (required)
```

### Surface mode only
```
--nifti PATH         4D NIfTI BOLD to project to surface (option 1)
--surface-ts FILES   Pre-computed surface time series (option 2, e.g., lh.bold.mgz rh.bold.mgz)
--subject ID         FreeSurfer subject ID (required with --nifti)
--subjects-dir PATH  FreeSurfer SUBJECTS_DIR (or set env var)
--reg-file PATH      Registration file (.dat/.lta); omit for --regheader
--target-subject ID  Resample to target surface (e.g., fsaverage)
--projfrac FLOAT     Cortical depth: 0=white, 0.5=mid, 1=pial (default: 0.5)
--hemi lh rh         Hemispheres to process (default: both)
--smooth-fwhm FLOAT  Surface smoothing FWHM in mm (default: 0 = none)
                     Applied to BOLD time series BEFORE Fourier analysis.
                     Recommended: 2 mm (topographic mapping), 4 mm (first pass)
--output-format      mgz (default) or gii (GIFTI)
```

### Smoothing notes

- Smoothing is **geodesic** (along the cortical surface), not volumetric
- It is applied to the **time series**, not the phase map — this preserves phase
- Phase is a circular quantity: direct smoothing of phase maps is invalid
  (averaging phase 0.1 and 6.1 rad gives 3.1 rad, which is wrong)
- Coherence and amplitude maps can be smoothed post-hoc if needed, but phase cannot
- `run_batch.sh` defaults to 2 mm FWHM for surface mode (edit `SMOOTH_FWHM` variable)

## Output files

### Option A — Volume outputs
```
results/sub-0001/run-01/
├── arf_sub-0001_..._bold_coherence.nii.gz       # Coherence map (0–1)
├── arf_sub-0001_..._bold_amplitude.nii.gz       # Amplitude map (% signal change)
├── arf_sub-0001_..._bold_phase.nii.gz           # Phase map (0–2π radians)
├── arf_sub-0001_..._bold_pref_delta.nii.gz      # Preferred temperature delta (°C)
├── arf_sub-0001_..._bold_pref_direction.nii.gz  # +1=warming, -1=cooling
└── arf_sub-0001_..._bold_coranal.npz            # All arrays + mask in numpy format
```

### Option B — Surface outputs (per hemisphere)
```
results/sub-0001/run-01/surf/
├── lh.arf_sub-0001_..._bold_surf.mgz            # Intermediate: surface time series
├── lh.arf_sub-0001_..._bold_coherence.mgz        # Coherence overlay
├── lh.arf_sub-0001_..._bold_amplitude.mgz        # Amplitude overlay
├── lh.arf_sub-0001_..._bold_phase.mgz            # Phase overlay
├── lh.arf_sub-0001_..._bold_pref_delta.mgz       # Preferred delta overlay
├── lh.arf_sub-0001_..._bold_pref_direction.mgz   # Direction overlay
├── lh.arf_sub-0001_..._bold_coranal.npz          # All arrays + vertex mask
├── rh.arf_sub-0001_..._bold_surf.mgz             # (same for rh)
├── rh.arf_sub-0001_..._bold_coherence.mgz
├── ...
```

Viewing surface results in freeview:
```bash
freeview -f $SUBJECTS_DIR/sub-0001/surf/lh.inflated:overlay=lh.arf_..._coherence.mgz:overlay_threshold=0.3,0.8
```

## Key parameters from config.py

| Parameter | Value | Meaning |
|-----------|-------|---------|
| TR | 1.5 s | Repetition time |
| dummy_volumes | 4 | Discarded at start |
| cycles_per_block | 8.5 | 8 full + 1 half cycle |
| cycle_duration | 70 s | Full triangle cycle (0.0143 Hz) |
| max_delta | 17.5 °C | Peak temperature deviation from baseline |
| baseline_temp | 30 °C | Thermode baseline |

## Interpreting results

1. **Threshold by coherence**: only trust voxels with `co > 0.3` (or use an F-test at the stimulus frequency)
2. **Phase map**: colour-code phase 0–2π to visualise thermal preference gradients across cortex
3. **Preferred delta**: directly interpretable — a voxel with `pref_delta = 15°C` responds best when the temperature is 15°C away from baseline
4. **Direction**: separates warming-tuned vs cooling-tuned voxels

## Algorithm summary

```
Option A (volume):

  Raw BOLD (4D NIfTI)
      ├─ Discard dummy volumes
      ├─ Brain mask (mean > 10% of median)
      ▼
  percent_tseries()                    ← vistasoft percentTSeries.m
      ├─ Divide by voxel temporal mean
      ├─ Linear detrend
      ├─ Subtract mean, ×100 → % signal change
      ▼
  compute_coranal()                    ← vistasoft computeCorAnalSeries.m
      ├─ FFT (np.fft.rfft)
      ├─ Amplitude = 2·|FFT[n_cycles]| / N
      ├─ Coherence = |FFT[signal]| / √(Σ|FFT[noise]|²)
      ├─ Phase = -(π/2) - angle(FFT[n_cycles]), wrapped to [0, 2π]
      ▼
  phase_to_thermal_pref()              ← adapted from vistasoft polarAngle.m
      ├─ Phase [0,π) → ascending ramp → preferred delta
      ├─ Phase [π,2π) → descending ramp → preferred delta
      ▼
  Save NIfTI volumes + .npz


Option B (surface):

  Raw BOLD (4D NIfTI)
      ▼
  mri_vol2surf                         ← project to cortical surface
      ├─ Per hemisphere (lh, rh)
      ├─ Sample at midthickness (projfrac=0.5)
      ▼
  mri_surf2surf --fwhm 2              ← geodesic smoothing (optional)
      ├─ Smooth BOLD time series on surface
      ├─ Respects cortical geometry (no cross-sulcal blurring)
      ├─ Preserves phase (smooths signal, not circular phase values)
      ▼
  percent_tseries()
      ▼
  compute_coranal()
      ▼
  phase_to_thermal_pref()
      ▼
  Save surface overlays (.mgz or .func.gii) + .npz
```
