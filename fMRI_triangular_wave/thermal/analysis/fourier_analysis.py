#!/usr/bin/env python3
"""
Fourier-based phase-encoding analysis for the thermal pRF experiment.

Adapted from vistasoft/mrBOLD computeCorAnalSeries.m (Wandell Lab, Stanford).
Computes coherence, amplitude, and phase at the stimulus frequency for each
voxel or surface vertex, using the same algorithm as the classic traveling-wave
retinotopy pipeline.

Two analysis modes:
    Option A (volume):  Run Fourier on volumetric BOLD, project results to surface later.
    Option B (surface): Project BOLD to surface first, run Fourier per-vertex.

Pipeline comparison:
    vistasoft (MATLAB)                      This module (Python)
    ─────────────────────                   ────────────────────
    percentTSeries()                        percent_tseries()
      → loadtSeries, divide by mean          → divide by mean, detrend
      → detrendTSeries (highpass/linear)      → polynomial or highpass detrend
      → subtract mean, ×100                   → subtract mean, ×100
    computeCorAnalSeries()                  compute_coranal()
      → fft(ptSeries)                         → np.fft.rfft(pt_series)
      → amp = 2*|ft[nCycles+1]|/N             → same
      → co  = |ft[f]| / sqrt(Σ|ft[noise]|²)  → same
      → ph  = -(π/2) - angle(ft[f])          → same
    GetNoiseBand / CreateNoiseIndices       create_noise_indices()
      → noiseBand=0: all freqs                → noise_band=0: all freqs
      → scalar: bandpass ±N around signal      → scalar: bandpass ±N
      → vector: explicit offsets               → array: explicit offsets
    polarAngle / eccentricity               (not needed — 1D thermal dimension)
    corAnal.mat                             save as .npz / .nii.gz / .tsv / .mgz / .gii

Usage:
    # Option A — volumetric analysis:
    python fourier_analysis.py volume --nifti bold.nii.gz --n-cycles 8 --out-dir results/

    # Option B — surface analysis (project BOLD, then Fourier per-vertex):
    python fourier_analysis.py surface --nifti bold.nii.gz --subject fsaverage \
        --subjects-dir /path/to/freesurfer --n-cycles 8 --out-dir results/

    # Option B — if you already have surface time series:
    python fourier_analysis.py surface --surface-ts lh.bold.mgz --n-cycles 8 --out-dir results/

    # As a library:
    from fourier_analysis import percent_tseries, compute_coranal
    co, amp, ph = compute_coranal(data_2d, n_cycles=8)

Requires: numpy, scipy
Optional: nibabel (for NIfTI/MGZ/GIFTI I/O), FreeSurfer (for mri_vol2surf)
"""

import os
import sys

# Parent thermal/ dir holds config module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
from scipy.signal import detrend as scipy_detrend

from config_v2 import CONFIG


# ---------------------------------------------------------------------------
# Step 1: Preprocessing — percent signal change
# ---------------------------------------------------------------------------
# vistasoft equivalent: percentTSeries.m
#
# Original MATLAB pipeline:
#   1. Load raw tSeries (time × voxels)
#   2. Divide by temporal mean per voxel (inhomogeneity correction, case 1)
#   3. Detrend (highpass or polynomial)
#   4. Subtract the mean → multiply by 100 → percent signal change
#
# We replicate the default behavior: inhomoCorrection=1, detrend=1 (linear),
# then mean-subtract and scale to percent.
# ---------------------------------------------------------------------------

def percent_tseries(data, detrend_order=1, frames_to_use=None):
    """Convert raw BOLD time series to percent signal change.

    Replicates vistasoft percentTSeries.m with inhomoCorrection=1 (divide
    by voxel mean) and linear detrending.

    Parameters
    ----------
    data : np.ndarray, shape (n_timepoints, n_voxels)
        Raw BOLD signal. Columns are voxels, rows are time points.
    detrend_order : int
        Polynomial order for detrending.
        0 = remove mean only (vistasoft detrend=0 equivalent)
        1 = linear detrend   (vistasoft detrend=-1 equivalent, common default)
        2 = quadratic removal (vistasoft detrend=2 equivalent)
    frames_to_use : array-like or None
        Subset of frame indices to keep (e.g., drop dummy volumes).
        Corresponds to vistasoft's framesToUse option.

    Returns
    -------
    pt_series : np.ndarray, same shape as (selected) data
        Percent signal change time series, mean-zero.

    Notes
    -----
    vistasoft MATLAB code (percentTSeries.m, lines 120-162):
        dc = nanmean(tSeries);           % temporal mean per voxel
        dc(dc==0) = Inf;                 % guard divide-by-zero
        ptSeries = tSeries ./ dc;        % divide by mean
        ptSeries = detrendTSeries(ptSeries, ...);  % remove trend
        ptSeries = ptSeries - mean(ptSeries);       % zero-mean
        ptSeries = 100 * ptSeries;                  % percent
    """
    data = np.asarray(data, dtype=np.float64)

    # Optionally select a subset of frames (e.g., exclude dummy volumes)
    if frames_to_use is not None:
        data = data[frames_to_use]

    # --- Inhomogeneity correction: divide by temporal mean per voxel ---
    # vistasoft case 1: dc = nanmean(tSeries); ptSeries = tSeries ./ dc
    dc = np.nanmean(data, axis=0)
    dc[dc == 0] = np.inf  # prevent divide-by-zero (matches MATLAB Inf trick)
    pt_series = data / dc

    # --- Detrend ---
    # vistasoft calls detrendTSeries which supports highpass (1), linear (-1),
    # quadratic (2). We use scipy's polynomial detrend for simplicity.
    if detrend_order > 0:
        # scipy_detrend with type='linear' removes linear trend;
        # for higher orders we fit and subtract a polynomial
        if detrend_order == 1:
            pt_series = scipy_detrend(pt_series, axis=0, type='linear')
        else:
            # Polynomial detrend: fit and subtract poly of given order
            n_tp = pt_series.shape[0]
            t = np.arange(n_tp, dtype=np.float64)
            for v in range(pt_series.shape[1]):
                coeffs = np.polyfit(t, pt_series[:, v], detrend_order)
                pt_series[:, v] -= np.polyval(coeffs, t)

    # --- Subtract mean and convert to percent ---
    # vistasoft: ptSeries = ptSeries - mean(ptSeries); ptSeries = 100*ptSeries
    pt_series -= np.mean(pt_series, axis=0)
    pt_series *= 100.0

    return pt_series


# ---------------------------------------------------------------------------
# Step 2: Noise band definition
# ---------------------------------------------------------------------------
# vistasoft equivalents: GetNoiseBand.m + CreateNoiseIndices.m
#
# The noise band determines which FFT bins form the denominator of the
# coherence metric. Options:
#   noise_band = 0        → use ALL positive-frequency bins (default)
#   noise_band = scalar   → bandpass: bins within ±scalar of signal frequency
#   noise_band = array    → explicit offsets from signal frequency
#
# Coherence = |ft[signal]| / sqrt(Σ|ft[noise]|²)
# ---------------------------------------------------------------------------

def create_noise_indices(n_freqs, n_cycles, noise_band=0):
    """Create frequency-bin indices for noise power estimation.

    Replicates vistasoft CreateNoiseIndices.m.

    Parameters
    ----------
    n_freqs : int
        Number of positive-frequency FFT bins (including DC).
        For rfft this is N//2 + 1.
    n_cycles : int
        Number of stimulus cycles. The signal lives at bin index n_cycles.
    noise_band : int, float, or array-like
        Controls which bins are noise:
        - 0 (default): all bins [0, n_freqs)
        - scalar > 0: bandpass of ±noise_band//2 bins around signal
        - array: explicit offsets from signal bin

    Returns
    -------
    indices : np.ndarray of int
        Valid FFT bin indices for noise power calculation.

    Notes
    -----
    vistasoft MATLAB code (CreateNoiseIndices.m):
        if noiseBand == 0:
            noiseIndices = 1:nAmps           % all bins (1-indexed)
        elseif scalar:
            nB = fix(noiseBand/2)
            noiseIndices = 1 + nCycles + (-nB:nB)
        elseif vector:
            noiseIndices = 1 + nCycles + noiseBand  % explicit offsets

    Python uses 0-indexed arrays, so signal is at index n_cycles (not n_cycles+1).
    """
    noise_band = np.atleast_1d(np.asarray(noise_band)).ravel()

    if noise_band.size == 1 and noise_band[0] == 0:
        # Default: use entire positive-frequency spectrum
        indices = np.arange(n_freqs)
    elif noise_band.size == 1:
        # Bandpass: ±half-width around signal frequency
        half_w = int(noise_band[0]) // 2
        indices = n_cycles + np.arange(-half_w, half_w + 1)
    else:
        # Explicit offsets from signal frequency
        indices = n_cycles + noise_band.astype(int)

    # Clamp to valid range [0, n_freqs)
    indices = indices[(indices >= 0) & (indices < n_freqs)]
    return indices


# ---------------------------------------------------------------------------
# Step 3: Core Fourier analysis — coherence, amplitude, phase
# ---------------------------------------------------------------------------
# vistasoft equivalent: computeCorAnalSeries.m
#
# This is the heart of the traveling-wave / phase-encoding analysis.
# For each voxel:
#   1. FFT the percent-signal time series
#   2. Amplitude at stimulus frequency = 2 * |FFT[n_cycles]| / N
#   3. Coherence = |FFT[signal]| / sqrt(Σ|FFT[noise]|²)
#   4. Phase = -(π/2) - angle(FFT[n_cycles]), wrapped to [0, 2π]
#
# The phase tells you WHERE in the stimulus cycle the voxel responds best.
# In retinotopy: phase → preferred polar angle or eccentricity.
# In our thermal experiment: phase → preferred temperature magnitude.
# ---------------------------------------------------------------------------

def compute_coranal(pt_series, n_cycles, noise_band=0):
    """Compute coherence, amplitude, and phase at the stimulus frequency.

    Direct translation of vistasoft computeCorAnalSeries.m.

    Parameters
    ----------
    pt_series : np.ndarray, shape (n_timepoints, n_voxels)
        Preprocessed percent-signal-change time series (output of
        percent_tseries). Must already be detrended & mean-subtracted.
    n_cycles : int
        Number of stimulus cycles in the scan. The stimulus frequency
        is n_cycles / (n_timepoints * TR) Hz. The FFT bin for the
        signal is at index n_cycles.
    noise_band : int, float, or array-like
        Passed to create_noise_indices(). Default 0 = all frequencies.

    Returns
    -------
    co : np.ndarray, shape (n_voxels,)
        Coherence at stimulus frequency (0–1 range, though can exceed 1
        for very strong signals with bandpass noise).
    amp : np.ndarray, shape (n_voxels,)
        Amplitude at stimulus frequency (in percent signal change units).
    ph : np.ndarray, shape (n_voxels,)
        Phase at stimulus frequency (radians, 0 to 2π).

    Notes
    -----
    vistasoft MATLAB code (computeCorAnalSeries.m, lines 44-80):

        ft = fft(ptSeries);                               % full FFT
        ft = ft(1:1+fix(size(ft,1)/2), :);                % positive freqs
        scaledAmp = abs(ft);                               % magnitude
        amp = 2*(scaledAmp(nCycles+1,:))/size(ptSeries,1); % true amplitude
        noiseIndices = CreateNoiseIndices(scaledAmp, nCycles, noiseBand);
        sqrtsummagsq = sqrt(sum(scaledAmp(noiseIndices,:).^2));
        co = scaledAmp(nCycles+1,:) ./ sqrtsummagsq;      % coherence
        ph = -(pi/2) - angle(ft(nCycles+1,:));             % phase
        ph(ph<0) = ph(ph<0) + 2*pi;                       % wrap to [0,2π]

    Key difference: MATLAB uses fft + manual truncation to positive freqs;
    we use np.fft.rfft which returns only the positive frequencies directly.
    The indexing is equivalent: MATLAB ft(nCycles+1) ↔ Python rfft[n_cycles].
    """
    n_tp, n_vox = pt_series.shape

    # --- FFT ---
    # vistasoft: ft = fft(ptSeries); ft = ft(1:1+fix(size(ft,1)/2), :)
    # Python equivalent: rfft returns only positive frequencies [0..N//2]
    ft = np.fft.rfft(pt_series, axis=0)  # shape: (N//2 + 1, n_voxels)
    n_freqs = ft.shape[0]

    # --- Magnitude spectrum ---
    # vistasoft: scaledAmp = abs(ft)
    scaled_amp = np.abs(ft)

    # --- Amplitude at stimulus frequency ---
    # vistasoft: amp = 2*(scaledAmp(nCycles+1,:))/size(ptSeries,1)
    # The factor 2/N converts the one-sided FFT magnitude to peak amplitude
    # of the underlying sinusoid.
    amp = 2.0 * scaled_amp[n_cycles, :] / n_tp

    # --- Noise indices ---
    # vistasoft: noiseIndices = CreateNoiseIndices(scaledAmp, nCycles, noiseBand)
    noise_idx = create_noise_indices(n_freqs, n_cycles, noise_band)

    # --- Coherence ---
    # vistasoft: sqrtsummagsq = sqrt(sum(scaledAmp(noiseIndices,:).^2))
    #            co = scaledAmp(nCycles+1,:) ./ sqrtsummagsq
    noise_power = np.sqrt(np.sum(scaled_amp[noise_idx, :] ** 2, axis=0))
    # Guard against divide-by-zero (vistasoft: warning off divideByZero)
    noise_power[noise_power == 0] = np.inf
    co = scaled_amp[n_cycles, :] / noise_power

    # --- Phase ---
    # vistasoft: ph = -(pi/2) - angle(ft(nCycles+1,:))
    #            ph(ph<0) = ph(ph<0) + 2*pi
    #
    # The -(π/2) offset converts from cosine phase (FFT convention) to
    # sine phase, since the traveling-wave stimulus is typically described
    # as a sine function: sin(ωt − φ). The minus sign accounts for the
    # convention that positive phase shift means the response is delayed.
    ph = -(np.pi / 2) - np.angle(ft[n_cycles, :])
    ph[ph < 0] += 2 * np.pi

    return co, amp, ph


# ---------------------------------------------------------------------------
# Step 4: Phase-to-thermal-magnitude mapping
# ---------------------------------------------------------------------------
# vistasoft equivalents: polarAngle.m / eccentricity.m
#
# In retinotopy, phase maps to 2D visual field position (polar angle or
# eccentricity). The mapping is 1:1 because each visual position is
# stimulated exactly ONCE per cycle (e.g., rotating wedge).
#
# In our thermal experiment, the stimulus is a BIPOLAR triangular wave:
#     0 → +max_delta → 0 → −max_delta → 0   (one 80s cycle)
#
# This differs from retinotopy in a key way: each temperature MAGNITUDE
# is reached TWICE per cycle — once during the warming ramp and once
# during the cooling ramp. The FFT phase at the fundamental (0.0125 Hz)
# therefore encodes BOTH the preferred magnitude AND the preferred
# direction (warming vs cooling).
#
# This works because thermal neurons are typically direction-selective:
# warm-sensitive neurons fire during the warming ramp, cold-sensitive
# neurons fire during the cooling ramp. The phase disambiguates them.
#
# For a warm zone (mask = +1), one 80s bipolar cycle:
#   Quarter 1 [0, π/2):    warming  30 → 47.5°C  (ascending)
#   Quarter 2 [π/2, π):    cooling  47.5 → 30°C   (descending to baseline)
#   Quarter 3 [π, 3π/2):   cooling  30 → 12.5°C   (descending below baseline)
#   Quarter 4 [3π/2, 2π):  warming  12.5 → 30°C   (ascending to baseline)
#
# So phase maps to a SIGNED preferred delta:
#   phase = 0     → delta =  0       (baseline, about to warm)
#   phase = π/2   → delta = +max     (peak warm)
#   phase = π     → delta =  0       (baseline, about to cool)
#   phase = 3π/2  → delta = -max     (peak cold)
# ---------------------------------------------------------------------------

def phase_to_thermal_pref(ph, max_delta, warm_first=True):
    """Convert Fourier phase to preferred temperature delta (signed).

    Maps FFT phase through the bipolar triangular waveform to recover:
    - The SIGNED preferred temperature delta (positive = above baseline,
      negative = below baseline)
    - The magnitude (absolute distance from baseline)
    - The direction (+1 warming, -1 cooling)

    Unlike retinotopy where phase maps 1:1 to position, in thermotopy
    the same temperature magnitude occurs twice per cycle (once warming,
    once cooling). The phase at the fundamental frequency (0.0125 Hz)
    distinguishes these because the full bipolar cycle has period 80s.

    Parameters
    ----------
    ph : np.ndarray
        Phase values in radians [0, 2π] from compute_coranal().
    max_delta : float
        Peak temperature delta (°C) of the bipolar triangular waveform.
    warm_first : bool
        If True, waveform starts at baseline and ramps up first
        (0 → +max → 0 → -max → 0).
        If False, cool-first (0 → -max → 0 → +max → 0),
        implemented as a π phase shift.

    Returns
    -------
    pref_delta_signed : np.ndarray
        Preferred temperature delta (°C), signed.
        Positive = voxel prefers above-baseline temperatures (warm phase).
        Negative = voxel prefers below-baseline temperatures (cold phase).
        Range: [-max_delta, +max_delta].
    pref_magnitude : np.ndarray
        Absolute preferred delta magnitude (°C).
        Range: [0, max_delta].
    pref_direction : np.ndarray
        +1 = voxel responds during warming phase (above baseline).
        -1 = voxel responds during cooling phase (below baseline).

    Notes
    -----
    The bipolar triangle waveform (from waveform.py) is:
        phase_frac = t / period                     # [0, 1)
        shifted = (phase_frac + 0.25) % 1.0
        delta = max_delta * (1 - 2*|2*shifted - 1|)

    We apply the same function to FFT phase (normalised to [0, 1)):
        phase_frac = ph / (2π)

    For a warm zone (mask = +1), the zone temperature is:
        T(t) = baseline + delta(t)

    So pref_delta_signed > 0 means the voxel prefers temperatures ABOVE
    baseline (warm phase), and pref_delta_signed < 0 means it prefers
    temperatures BELOW baseline (cold phase).
    """
    ph = np.asarray(ph, dtype=np.float64)

    # Adjust for cool-first: the waveform is shifted by half a cycle
    # cool-first: 0 → -max → 0 → +max → 0  (π phase shift)
    if not warm_first:
        ph = (ph + np.pi) % (2 * np.pi)

    # Map phase through the BIPOLAR triangle waveform
    # This is the same formula as waveform.py:generate_delta_waveform
    phase_frac = ph / (2 * np.pi)  # normalise to [0, 1)
    shifted = (phase_frac + 0.25) % 1.0
    pref_delta_signed = max_delta * (1.0 - 2.0 * np.abs(2.0 * shifted - 1.0))

    # Derived quantities
    pref_magnitude = np.abs(pref_delta_signed)
    pref_direction = np.sign(pref_delta_signed)
    # Voxels at exactly baseline (delta=0) get direction=0
    # This is fine — they respond at the baseline crossing

    return pref_delta_signed, pref_magnitude, pref_direction


# ---------------------------------------------------------------------------
# Step 4b: Stimulation-window trimming
# ---------------------------------------------------------------------------
# In standard retinotopy, the stimulus runs the ENTIRE scan — no baselines.
# n_cycles exactly equals the number of stimulus cycles and the signal
# falls on an integer FFT bin.
#
# In our experiment, there are 30s baseline buffers before and after the
# stimulation period. If we FFT the entire scan (baselines included),
# n_cycles=8 doesn't land exactly on the stimulus frequency:
#   stimulus period = 80s → freq = 0.0125 Hz
#   FFT bin 8 with 740s scan → freq = 8/740 = 0.0108 Hz  ← MISMATCH
#
# Solution: trim the time series to the stimulation window only.
# With 680s of stimulation (8.5 cycles × 80s), n_cycles=8 gives:
#   freq = 8/680 = 0.01176 Hz  (still not exact due to 8.5 cycles)
#
# The mismatch is small (~6% of a bin width) and causes minor spectral
# leakage. For most purposes this is acceptable. For maximum precision,
# trim to exactly 8 complete cycles (640s).
# ---------------------------------------------------------------------------

def compute_stim_frames(config, n_tp_after_dummies, trim_to_n_cycles=None):
    """Compute the frame range corresponding to the stimulation window.

    Parameters
    ----------
    config : dict
        Experiment configuration with keys:
        'baseline_buffer', 'cycle_duration', 'cycles_per_block', 'TR'.
    n_tp_after_dummies : int
        Total number of time points after dummy volume removal.
    trim_to_n_cycles : int or None
        If set, trim to exactly this many complete cycles (e.g., 8).
        If None, include the full stimulation period (including partial
        cycles like the extra 0.5 cycle).

    Returns
    -------
    stim_frames : np.ndarray of int
        Indices of frames within the stimulation window.
    n_stim_frames : int
        Number of frames in the stimulation window.
    """
    TR = config['TR']
    baseline_s = config['baseline_buffer']

    if trim_to_n_cycles is not None:
        stim_dur_s = trim_to_n_cycles * config['cycle_duration']
    else:
        stim_dur_s = config['cycles_per_block'] * config['cycle_duration']

    # Baseline buffer is relative to start of scan (after dummies)
    stim_start_frame = int(np.round(baseline_s / TR))
    stim_end_frame = int(np.round((baseline_s + stim_dur_s) / TR))
    stim_end_frame = min(stim_end_frame, n_tp_after_dummies)

    stim_frames = np.arange(stim_start_frame, stim_end_frame)
    return stim_frames, len(stim_frames)


# ---------------------------------------------------------------------------
# Step 5: Full pipeline — load NIfTI, preprocess, analyse, save
# ---------------------------------------------------------------------------

def run_phase_encoding_analysis(nifti_path, n_cycles, config=None,
                                noise_band=0, detrend_order=1,
                                dummy_volumes=None, warm_first=True,
                                out_dir=None):
    """Run the full phase-encoding analysis pipeline on a NIfTI file.

    Parameters
    ----------
    nifti_path : str
        Path to 4D NIfTI BOLD file.
    n_cycles : int
        Number of stimulus cycles in the run.
    config : dict, optional
        Experiment config. Uses CONFIG from config.py if None.
    noise_band : int or array-like
        Noise band setting (see create_noise_indices).
    detrend_order : int
        Polynomial detrend order (1=linear, 2=quadratic).
    dummy_volumes : int or None
        Number of dummy volumes to discard. Uses config if None.
    warm_first : bool
        Whether this run used warm-first stimulus ordering.
    out_dir : str or None
        Output directory. Uses same directory as input if None.

    Returns
    -------
    results : dict
        Keys: 'co', 'amp', 'ph', 'pref_delta', 'pref_direction',
              'affine', 'header', 'mask'
    """
    import nibabel as nib

    if config is None:
        config = CONFIG
    if dummy_volumes is None:
        dummy_volumes = config.get('dummy_volumes', 0)
    if out_dir is None:
        out_dir = os.path.dirname(nifti_path)

    max_delta = config['max_delta']

    # --- Load NIfTI ---
    print(f'Loading {nifti_path}...')
    img = nib.load(nifti_path)
    data_4d = img.get_fdata()  # (X, Y, Z, T)
    affine = img.affine
    header = img.header

    nx, ny, nz, n_tp = data_4d.shape
    print(f'  Shape: {data_4d.shape}, {n_tp} volumes')

    # --- Discard dummy volumes ---
    # vistasoft: framesToUse option in computeCorAnalSeries
    if dummy_volumes > 0:
        print(f'  Discarding {dummy_volumes} dummy volumes')
        data_4d = data_4d[:, :, :, dummy_volumes:]
        n_tp = data_4d.shape[3]

    # --- Create brain mask (non-zero voxels) ---
    mean_vol = np.mean(data_4d, axis=3)
    mask = mean_vol > (0.1 * np.percentile(mean_vol[mean_vol > 0], 50))
    n_vox = np.sum(mask)
    print(f'  Brain mask: {n_vox} voxels')

    # --- Reshape to 2D: (time × voxels) ---
    # vistasoft processes slice-by-slice; we vectorise across all masked voxels
    data_2d = data_4d[mask].T  # (n_tp, n_vox)

    # --- Trim to stimulation window ---
    # In standard retinotopy, the stimulus fills the entire scan so
    # n_cycles matches exactly. Here we have baseline buffers, so we
    # trim to the stimulation period to align the FFT bin with the
    # actual stimulus frequency (0.0125 Hz = 1/80s).
    stim_frames, n_stim = compute_stim_frames(
        config, n_tp, trim_to_n_cycles=n_cycles)
    print(f'  Trimming to stimulation window: frames {stim_frames[0]}-'
          f'{stim_frames[-1]} ({n_stim} volumes, '
          f'{n_stim * config["TR"]:.1f}s)')
    stim_freq = n_cycles / (n_stim * config['TR'])
    print(f'  Stimulus frequency: {stim_freq:.6f} Hz '
          f'(period = {1/stim_freq:.1f}s)')
    data_2d = data_2d[stim_frames]

    # --- Step 1: Preprocessing (percent signal change) ---
    print('  Preprocessing (percent tSeries)...')
    pt_series = percent_tseries(data_2d, detrend_order=detrend_order)

    # --- Step 2–3: Fourier analysis ---
    print(f'  Fourier analysis (n_cycles={n_cycles})...')
    co, amp, ph = compute_coranal(pt_series, n_cycles, noise_band=noise_band)

    # --- Step 4: Phase-to-thermal mapping (bipolar waveform) ---
    pref_signed, pref_mag, pref_dir = phase_to_thermal_pref(
        ph, max_delta, warm_first)

    # --- Write output volumes ---
    print(f'  Saving results to {out_dir}/')
    os.makedirs(out_dir, exist_ok=True)
    basename = os.path.splitext(
        os.path.splitext(os.path.basename(nifti_path))[0])[0]

    def save_vol(arr, name):
        """Map 1D voxel array back to 3D volume and save as NIfTI."""
        vol = np.zeros((nx, ny, nz), dtype=np.float32)
        vol[mask] = arr.astype(np.float32)
        out_img = nib.Nifti1Image(vol, affine, header)
        out_path = os.path.join(out_dir, f'{basename}_{name}.nii.gz')
        nib.save(out_img, out_path)
        print(f'    {out_path}')
        return vol

    co_vol = save_vol(co, 'coherence')
    amp_vol = save_vol(amp, 'amplitude')
    ph_vol = save_vol(ph, 'phase')
    signed_vol = save_vol(pref_signed, 'pref_delta_signed')
    mag_vol = save_vol(pref_mag, 'pref_delta_magnitude')
    dir_vol = save_vol(pref_dir, 'pref_direction')

    # --- Save numpy archive ---
    npz_path = os.path.join(out_dir, f'{basename}_coranal.npz')
    np.savez(npz_path,
             coherence=co_vol, amplitude=amp_vol, phase=ph_vol,
             pref_delta_signed=signed_vol,
             pref_delta_magnitude=mag_vol,
             pref_direction=dir_vol,
             mask=mask)
    print(f'    {npz_path}')

    results = {
        'co': co, 'amp': amp, 'ph': ph,
        'pref_delta_signed': pref_signed,
        'pref_delta_magnitude': pref_mag,
        'pref_direction': pref_dir,
        'co_vol': co_vol, 'amp_vol': amp_vol, 'ph_vol': ph_vol,
        'affine': affine, 'header': header, 'mask': mask,
    }

    # --- Summary statistics ---
    print(f'\n  Summary (all voxels):')
    print(f'    Coherence: mean={np.mean(co):.4f}, max={np.max(co):.4f}')
    print(f'    Amplitude: mean={np.mean(amp):.4f}, max={np.max(amp):.4f}')

    # Stats for high-coherence voxels
    co_thresh = 0.3
    sig_mask = co > co_thresh
    n_sig = np.sum(sig_mask)
    if n_sig > 0:
        print(f'    Voxels with co > {co_thresh}: {n_sig} '
              f'({100*n_sig/len(co):.1f}%)')
        print(f'    Preferred delta signed (co>{co_thresh}): '
              f'mean={np.mean(pref_signed[sig_mask]):.1f} C, '
              f'range=[{np.min(pref_signed[sig_mask]):.1f}, '
              f'{np.max(pref_signed[sig_mask]):.1f}] C')
        n_warm = np.sum(pref_dir[sig_mask] > 0)
        n_cold = np.sum(pref_dir[sig_mask] < 0)
        print(f'    Warm-tuned: {n_warm}, Cold-tuned: {n_cold}')

    return results


# ---------------------------------------------------------------------------
# Step 6: Surface projection — BOLD volume to surface time series
# ---------------------------------------------------------------------------
# This is Option B: project the 4D BOLD onto the cortical surface BEFORE
# running Fourier analysis. This gives per-vertex time series, avoiding
# interpolation artifacts when projecting scalar results across sulci.
#
# Uses FreeSurfer's mri_vol2surf. Requires:
#   - FreeSurfer installed and on PATH
#   - Subject reconstructed with recon-all (or use fsaverage)
#   - Registration file (.dat / .lta) or --regheader for same-subject
# ---------------------------------------------------------------------------

def project_bold_to_surface(nifti_path, subject, hemi, subjects_dir=None,
                            reg_file=None, target_subject=None,
                            projfrac=0.5, out_path=None):
    """Project a 4D BOLD volume onto the cortical surface using mri_vol2surf.

    Parameters
    ----------
    nifti_path : str
        Path to 4D NIfTI BOLD file.
    subject : str
        FreeSurfer subject ID (e.g., 'sub-0001' or 'fsaverage').
    hemi : str
        Hemisphere: 'lh' or 'rh'.
    subjects_dir : str or None
        FreeSurfer SUBJECTS_DIR. Uses environment variable if None.
    reg_file : str or None
        Registration file (.dat or .lta). If None, uses --regheader
        (assumes BOLD is already in subject's anatomical space).
    target_subject : str or None
        Target surface subject for resampling (e.g., 'fsaverage').
        If None, stays in native subject space.
    projfrac : float
        Fraction of cortical thickness to sample at (0=white, 1=pial,
        0.5=midthickness). Default 0.5.
    out_path : str or None
        Output path for surface time series. Auto-generated if None.

    Returns
    -------
    out_path : str
        Path to the output surface time series file (.mgz).
    """
    import subprocess

    if subjects_dir is None:
        subjects_dir = os.environ.get('SUBJECTS_DIR', '')
        if not subjects_dir:
            raise ValueError(
                'SUBJECTS_DIR not set. Pass subjects_dir or set the '
                'SUBJECTS_DIR environment variable.')

    if out_path is None:
        base = os.path.splitext(os.path.splitext(
            os.path.basename(nifti_path))[0])[0]
        out_dir = os.path.dirname(nifti_path)
        out_path = os.path.join(out_dir, f'{hemi}.{base}_surf.mgz')

    cmd = [
        'mri_vol2surf',
        '--src', nifti_path,
        '--out', out_path,
        '--hemi', hemi,
        '--projfrac', str(projfrac),
        '--srcsubject', subject,
        '--sd', subjects_dir,
    ]

    if reg_file:
        cmd += ['--reg', reg_file]
    else:
        cmd += ['--regheader', subject]

    if target_subject:
        cmd += ['--trgsubject', target_subject]

    print(f'  Projecting {hemi} to surface...')
    print(f'    cmd: {" ".join(cmd)}')
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f'mri_vol2surf failed (exit {result.returncode}):\n'
            f'{result.stderr}')

    print(f'    Output: {out_path}')
    return out_path


def smooth_surface_tseries(surf_ts_path, subject, hemi, fwhm,
                           subjects_dir=None, out_path=None):
    """Smooth a surface time series using mri_surf2surf.

    Applies geodesic (surface-based) Gaussian smoothing to a 4D surface
    time series. This smooths along the cortical manifold, avoiding
    blurring across sulcal walls — critical for preserving phase gradients
    in topographic mapping.

    Smoothing is applied to the BOLD time series BEFORE Fourier analysis,
    not to the phase maps (phase is circular and cannot be linearly
    averaged).

    Parameters
    ----------
    surf_ts_path : str
        Path to input surface time series (.mgz / .mgh).
    subject : str
        FreeSurfer subject ID whose surface geometry is used for smoothing.
    hemi : str
        Hemisphere: 'lh' or 'rh'.
    fwhm : float
        Smoothing kernel full-width at half-maximum in mm.
        Recommended: 2 mm for topographic mapping, 4 mm for first pass.
    subjects_dir : str or None
        FreeSurfer SUBJECTS_DIR. Uses environment variable if None.
    out_path : str or None
        Output path. Auto-generated with _sm{fwhm} suffix if None.

    Returns
    -------
    out_path : str
        Path to the smoothed surface time series.
    """
    import subprocess

    if subjects_dir is None:
        subjects_dir = os.environ.get('SUBJECTS_DIR', '')
        if not subjects_dir:
            raise ValueError(
                'SUBJECTS_DIR not set. Pass subjects_dir or set the '
                'SUBJECTS_DIR environment variable.')

    if out_path is None:
        base, ext = os.path.splitext(surf_ts_path)
        # Handle .nii.gz double extension
        if base.endswith('.nii'):
            base = base[:-4]
            ext = '.nii' + ext
        out_path = f'{base}_sm{fwhm}{ext}'

    cmd = [
        'mri_surf2surf',
        '--hemi', hemi,
        '--srcsubject', subject,
        '--sval', surf_ts_path,
        '--trgsubject', subject,
        '--tval', out_path,
        '--fwhm', str(fwhm),
        '--sd', subjects_dir,
    ]

    print(f'  Smoothing {hemi} surface tSeries (FWHM={fwhm} mm)...')
    print(f'    cmd: {" ".join(cmd)}')
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f'mri_surf2surf failed (exit {result.returncode}):\n'
            f'{result.stderr}')

    print(f'    Output: {out_path}')
    return out_path


def load_surface_tseries(surf_path):
    """Load a surface time series file (.mgz, .mgh, or .func.gii).

    Parameters
    ----------
    surf_path : str
        Path to surface time series. Supported formats:
        - FreeSurfer .mgz/.mgh: shape (n_vertices, 1, 1, n_timepoints)
        - GIFTI .func.gii: each darray is one time point

    Returns
    -------
    data : np.ndarray, shape (n_timepoints, n_vertices)
        Surface time series, rows=time, columns=vertices.
    n_vertices : int
        Number of surface vertices.
    """
    import nibabel as nib

    if surf_path.endswith('.gii') or surf_path.endswith('.func.gii'):
        gii = nib.load(surf_path)
        # Each darray is one timepoint, shape (n_vertices,)
        data = np.column_stack([d.data for d in gii.darrays]).T
        # data is now (n_timepoints, n_vertices)
    else:
        # FreeSurfer .mgz / .mgh: shape (n_vertices, 1, 1, n_timepoints)
        img = nib.load(surf_path)
        arr = img.get_fdata()
        # Squeeze out singleton dims → (n_vertices, n_timepoints)
        arr = arr.squeeze()
        if arr.ndim == 1:
            raise ValueError(
                f'{surf_path} has only 1 time point — expected 4D surface '
                f'time series.')
        # Transpose to (n_timepoints, n_vertices)
        data = arr.T

    n_vertices = data.shape[1]
    return data, n_vertices


def save_surface_overlay(data, n_vertices, out_path, template_path=None):
    """Save a per-vertex scalar map as a surface overlay.

    Parameters
    ----------
    data : np.ndarray, shape (n_vertices,)
        Scalar data for each vertex.
    n_vertices : int
        Number of vertices (for validation).
    out_path : str
        Output file path. Format determined by extension:
        - .mgz/.mgh: FreeSurfer overlay
        - .func.gii: GIFTI functional
        - .curv: FreeSurfer curvature format
    template_path : str or None
        Template surface file to copy header from (for .mgz).
    """
    import nibabel as nib

    assert len(data) == n_vertices, (
        f'Data length {len(data)} != n_vertices {n_vertices}')

    if out_path.endswith('.gii') or out_path.endswith('.func.gii'):
        darray = nib.gifti.GiftiDataArray(
            data=data.astype(np.float32),
            intent='NIFTI_INTENT_NONE',
            datatype='NIFTI_TYPE_FLOAT32')
        gii = nib.gifti.GiftiImage(darrays=[darray])
        nib.save(gii, out_path)
    else:
        # FreeSurfer .mgz format: (n_vertices, 1, 1)
        vol = data.astype(np.float32).reshape(-1, 1, 1)
        img = nib.MGHImage(vol, affine=np.eye(4))
        nib.save(img, out_path)


def run_surface_analysis(nifti_path=None, surface_ts_paths=None,
                         subject=None, subjects_dir=None,
                         hemis=('lh', 'rh'), reg_file=None,
                         target_subject=None, projfrac=0.5,
                         smooth_fwhm=0, n_cycles=8, config=None,
                         noise_band=0, detrend_order=1,
                         dummy_volumes=None, warm_first=True,
                         out_dir=None, output_format='mgz'):
    """Run the full surface-based phase-encoding analysis (Option B).

    Either provide a volumetric BOLD (nifti_path) to be projected to the
    surface, or provide pre-computed surface time series (surface_ts_paths).

    Pipeline with smoothing enabled (--smooth-fwhm > 0):
        volume BOLD
          → mri_vol2surf (project to surface)
          → mri_surf2surf --fwhm (geodesic smoothing on surface)   ← HERE
          → percent_tseries (detrend + normalise)
          → compute_coranal (FFT)
          → phase_to_thermal_pref

    Smoothing is applied to the BOLD time series on the surface, BEFORE
    the Fourier analysis. This preserves phase information because we are
    smoothing the signal, not the (circular) phase map. Surface-based
    smoothing respects cortical geometry and does not blur across sulci.

    Parameters
    ----------
    nifti_path : str or None
        Path to 4D NIfTI BOLD. Will be projected to surface via mri_vol2surf.
        Not needed if surface_ts_paths is provided.
    surface_ts_paths : dict or None
        Pre-computed surface time series, keyed by hemisphere.
        E.g. {'lh': 'lh.bold_surf.mgz', 'rh': 'rh.bold_surf.mgz'}
        If provided, skips the projection step.
    subject : str
        FreeSurfer subject ID (required if projecting from volume or
        smoothing).
    subjects_dir : str or None
        FreeSurfer SUBJECTS_DIR.
    hemis : tuple of str
        Hemispheres to process. Default ('lh', 'rh').
    reg_file : str or None
        Registration file for mri_vol2surf.
    target_subject : str or None
        Target subject for surface resampling (e.g., 'fsaverage').
    projfrac : float
        Cortical depth fraction for sampling (0=white, 0.5=mid, 1=pial).
    smooth_fwhm : float
        Surface smoothing FWHM in mm. 0 = no smoothing (default).
        Recommended: 2 mm for topographic mapping, 4 mm for first pass.
        Smoothing is applied to the surface time series BEFORE Fourier
        analysis, using mri_surf2surf --fwhm (geodesic Gaussian kernel).
    n_cycles : int
        Number of stimulus cycles.
    config : dict or None
        Experiment config.
    noise_band : int or array-like
        Noise band setting.
    detrend_order : int
        Polynomial detrend order.
    dummy_volumes : int or None
        Dummy volumes to discard.
    warm_first : bool
        Warm-first stimulus ordering.
    out_dir : str or None
        Output directory.
    output_format : str
        Output overlay format: 'mgz' (FreeSurfer) or 'gii' (GIFTI).

    Returns
    -------
    results : dict
        Per-hemisphere results keyed by 'lh' and/or 'rh'. Each contains:
        'co', 'amp', 'ph', 'pref_delta', 'pref_direction', 'n_vertices'.
    """
    if config is None:
        config = CONFIG
    if dummy_volumes is None:
        dummy_volumes = config.get('dummy_volumes', 0)
    if out_dir is None:
        if nifti_path:
            out_dir = os.path.dirname(nifti_path)
        elif surface_ts_paths:
            first = next(iter(surface_ts_paths.values()))
            out_dir = os.path.dirname(first)
        else:
            out_dir = '.'

    max_delta = config['max_delta']
    os.makedirs(out_dir, exist_ok=True)

    # Determine basename for output files
    if nifti_path:
        basename = os.path.splitext(
            os.path.splitext(os.path.basename(nifti_path))[0])[0]
    else:
        first = next(iter(surface_ts_paths.values()))
        bn = os.path.basename(first)
        # Strip hemi prefix and _surf suffix
        basename = bn.split('.', 1)[-1] if '.' in bn else bn
        basename = os.path.splitext(os.path.splitext(basename)[0])[0]
        basename = basename.replace('_surf', '')

    ext = '.func.gii' if output_format == 'gii' else '.mgz'
    results = {}

    for hemi in hemis:
        print(f'\n=== {hemi.upper()} hemisphere ===')

        # --- Get surface time series ---
        if surface_ts_paths and hemi in surface_ts_paths:
            surf_ts_path = surface_ts_paths[hemi]
            print(f'  Loading pre-computed surface tSeries: {surf_ts_path}')
        elif nifti_path:
            surf_ts_path = os.path.join(
                out_dir, f'{hemi}.{basename}_surf.mgz')
            if not os.path.exists(surf_ts_path):
                surf_ts_path = project_bold_to_surface(
                    nifti_path, subject, hemi,
                    subjects_dir=subjects_dir,
                    reg_file=reg_file,
                    target_subject=target_subject,
                    projfrac=projfrac,
                    out_path=surf_ts_path)
            else:
                print(f'  Surface tSeries already exists: {surf_ts_path}')
        else:
            raise ValueError(
                f'No input for {hemi}: provide nifti_path or '
                f'surface_ts_paths["{hemi}"]')

        # --- Surface smoothing (before Fourier analysis) ---
        # Smoothing the time series preserves phase information.
        # Smoothing the phase map would destroy it (phase is circular).
        if smooth_fwhm > 0:
            # Determine which subject's surface geometry to use
            smooth_subject = target_subject if target_subject else subject
            if not smooth_subject:
                raise ValueError(
                    '--subject is required for surface smoothing '
                    '(need surface geometry for geodesic kernel)')
            smoothed_path = os.path.join(
                out_dir,
                f'{hemi}.{basename}_surf_sm{smooth_fwhm}.mgz')
            if not os.path.exists(smoothed_path):
                smooth_surface_tseries(
                    surf_ts_path, smooth_subject, hemi, smooth_fwhm,
                    subjects_dir=subjects_dir, out_path=smoothed_path)
            else:
                print(f'  Smoothed tSeries already exists: {smoothed_path}')
            surf_ts_path = smoothed_path

        # --- Load surface time series ---
        data, n_vertices = load_surface_tseries(surf_ts_path)
        n_tp = data.shape[0]
        print(f'  Loaded: {n_tp} timepoints x {n_vertices} vertices')

        # --- Discard dummy volumes ---
        if dummy_volumes > 0:
            print(f'  Discarding {dummy_volumes} dummy volumes')
            data = data[dummy_volumes:]
            n_tp = data.shape[0]

        # --- Trim to stimulation window ---
        stim_frames, n_stim = compute_stim_frames(
            config, n_tp, trim_to_n_cycles=n_cycles)
        print(f'  Trimming to stimulation window: frames {stim_frames[0]}-'
              f'{stim_frames[-1]} ({n_stim} volumes)')
        data = data[stim_frames]

        # --- Mask: exclude zero-variance vertices ---
        vertex_std = np.std(data, axis=0)
        vertex_mean = np.mean(data, axis=0)
        valid = (vertex_std > 0) & (vertex_mean > 0)
        n_valid = np.sum(valid)
        print(f'  Valid vertices: {n_valid} / {n_vertices}')

        # --- Preprocess ---
        print('  Preprocessing (percent tSeries)...')
        pt = percent_tseries(data[:, valid], detrend_order=detrend_order)

        # --- Fourier analysis ---
        print(f'  Fourier analysis (n_cycles={n_cycles})...')
        co, amp, ph = compute_coranal(pt, n_cycles, noise_band=noise_band)

        # --- Phase-to-thermal mapping (bipolar waveform) ---
        pref_signed, pref_mag, pref_dir = phase_to_thermal_pref(
            ph, max_delta, warm_first)

        # --- Map back to full vertex arrays ---
        co_full = np.zeros(n_vertices, dtype=np.float32)
        amp_full = np.zeros(n_vertices, dtype=np.float32)
        ph_full = np.zeros(n_vertices, dtype=np.float32)
        signed_full = np.zeros(n_vertices, dtype=np.float32)
        mag_full = np.zeros(n_vertices, dtype=np.float32)
        dir_full = np.zeros(n_vertices, dtype=np.float32)

        co_full[valid] = co.astype(np.float32)
        amp_full[valid] = amp.astype(np.float32)
        ph_full[valid] = ph.astype(np.float32)
        signed_full[valid] = pref_signed.astype(np.float32)
        mag_full[valid] = pref_mag.astype(np.float32)
        dir_full[valid] = pref_dir.astype(np.float32)

        # --- Save surface overlays ---
        print(f'  Saving surface overlays...')
        overlay_names = {
            'coherence': co_full,
            'amplitude': amp_full,
            'phase': ph_full,
            'pref_delta_signed': signed_full,
            'pref_delta_magnitude': mag_full,
            'pref_direction': dir_full,
        }
        for name, arr in overlay_names.items():
            out_path = os.path.join(
                out_dir, f'{hemi}.{basename}_{name}{ext}')
            save_surface_overlay(arr, n_vertices, out_path)
            print(f'    {out_path}')

        # --- Save numpy archive ---
        npz_path = os.path.join(out_dir, f'{hemi}.{basename}_coranal.npz')
        np.savez(npz_path, coherence=co_full, amplitude=amp_full,
                 phase=ph_full, pref_delta_signed=signed_full,
                 pref_delta_magnitude=mag_full,
                 pref_direction=dir_full, valid_mask=valid)
        print(f'    {npz_path}')

        # --- Summary ---
        print(f'\n  Summary ({hemi}, valid vertices):')
        print(f'    Coherence: mean={np.mean(co):.4f}, max={np.max(co):.4f}')
        print(f'    Amplitude: mean={np.mean(amp):.4f}, max={np.max(amp):.4f}')
        co_thresh = 0.3
        sig = co > co_thresh
        n_sig = np.sum(sig)
        if n_sig > 0:
            print(f'    Vertices with co > {co_thresh}: {n_sig} '
                  f'({100*n_sig/len(co):.1f}%)')
            print(f'    Preferred delta signed (co>{co_thresh}): '
                  f'mean={np.mean(pref_signed[sig]):.1f} C, '
                  f'range=[{np.min(pref_signed[sig]):.1f}, '
                  f'{np.max(pref_signed[sig]):.1f}] C')
            n_warm = np.sum(pref_dir[sig] > 0)
            n_cold = np.sum(pref_dir[sig] < 0)
            print(f'    Warm-tuned: {n_warm}, Cold-tuned: {n_cold}')

        results[hemi] = {
            'co': co_full, 'amp': amp_full, 'ph': ph_full,
            'pref_delta_signed': signed_full,
            'pref_delta_magnitude': mag_full,
            'pref_direction': dir_full,
            'valid_mask': valid, 'n_vertices': n_vertices,
        }

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Phase-encoding Fourier analysis for thermal pRF.',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest='mode', help='Analysis mode')

    # --- Shared arguments ---
    def add_common_args(p):
        p.add_argument('--n-cycles', type=int, default=None,
                       help='Number of stimulus cycles (default: from config)')
        p.add_argument('--noise-band', type=float, default=0,
                       help='Noise band width (0=all freqs, >0=bandpass)')
        p.add_argument('--detrend', type=int, default=1,
                       help='Detrend order (0=none, 1=linear, 2=quadratic)')
        p.add_argument('--dummy-volumes', type=int, default=None,
                       help='Dummy volumes to discard (default: from config). '
                       'Set to 0 if your preprocessed data already has '
                       'dummies removed.')
        direction = p.add_mutually_exclusive_group()
        direction.add_argument('--warm-first', action='store_true',
                               default=True, dest='warm_first',
                               help='Warm-first stimulus order (default)')
        direction.add_argument('--cool-first', action='store_false',
                               dest='warm_first',
                               help='Cool-first stimulus order')
        p.add_argument('--out-dir', default=None,
                       help='Output directory')

    # --- Option A: volume mode ---
    vol_parser = subparsers.add_parser(
        'volume', help='Option A: Fourier analysis in volume space')
    vol_parser.add_argument('--nifti', required=True,
                            help='Path to 4D NIfTI BOLD file')
    add_common_args(vol_parser)

    # --- Option B: surface mode ---
    surf_parser = subparsers.add_parser(
        'surface', help='Option B: Fourier analysis on cortical surface')
    surf_input = surf_parser.add_mutually_exclusive_group(required=True)
    surf_input.add_argument('--nifti',
                            help='4D NIfTI BOLD to project to surface')
    surf_input.add_argument('--surface-ts', nargs='+', metavar='HEMI.FILE',
                            help='Pre-computed surface time series '
                            '(e.g., lh.bold_surf.mgz rh.bold_surf.mgz)')
    surf_parser.add_argument('--subject', default=None,
                             help='FreeSurfer subject ID (required with --nifti)')
    surf_parser.add_argument('--subjects-dir', default=None,
                             help='FreeSurfer SUBJECTS_DIR')
    surf_parser.add_argument('--reg-file', default=None,
                             help='Registration file (.dat/.lta). '
                             'Omit for --regheader (same-subject space)')
    surf_parser.add_argument('--target-subject', default=None,
                             help='Resample to target surface '
                             '(e.g., fsaverage)')
    surf_parser.add_argument('--projfrac', type=float, default=0.5,
                             help='Cortical depth (0=white, 0.5=mid, 1=pial)')
    surf_parser.add_argument('--hemi', nargs='+', default=['lh', 'rh'],
                             choices=['lh', 'rh'],
                             help='Hemispheres to process (default: both)')
    surf_parser.add_argument('--smooth-fwhm', type=float, default=0,
                             help='Surface smoothing FWHM in mm (default: 0 = none). '
                             'Applied to BOLD time series on surface BEFORE '
                             'Fourier analysis. Recommended: 2 mm for '
                             'topographic mapping, 4 mm for first pass.')
    surf_parser.add_argument('--output-format', default='mgz',
                             choices=['mgz', 'gii'],
                             help='Surface overlay format (default: mgz)')
    add_common_args(surf_parser)

    args = parser.parse_args()

    if args.mode is None:
        parser.print_help()
        print('\nError: specify a mode: volume or surface')
        return

    config = CONFIG.copy()
    n_cycles = args.n_cycles
    if n_cycles is None:
        raw = config['cycles_per_block']
        n_cycles = int(raw)
        if raw != n_cycles:
            print(f'NOTE: cycles_per_block={raw} in config is not an integer. '
                  f'Using n_cycles={n_cycles} for Fourier analysis (FFT bins '
                  f'are integer-indexed). The extra {raw - n_cycles:.1f} cycle '
                  f'contributes via spectral leakage but does not affect the '
                  f'primary bin.')
    warm_first = args.warm_first

    if args.mode == 'volume':
        run_phase_encoding_analysis(
            nifti_path=args.nifti,
            n_cycles=n_cycles,
            config=config,
            noise_band=args.noise_band,
            detrend_order=args.detrend,
            dummy_volumes=args.dummy_volumes,
            warm_first=warm_first,
            out_dir=args.out_dir,
        )

    elif args.mode == 'surface':
        # Parse surface time series paths if provided
        surface_ts_paths = None
        if args.surface_ts:
            surface_ts_paths = {}
            for path in args.surface_ts:
                bn = os.path.basename(path)
                if bn.startswith('lh.'):
                    surface_ts_paths['lh'] = path
                elif bn.startswith('rh.'):
                    surface_ts_paths['rh'] = path
                else:
                    raise ValueError(
                        f'Cannot determine hemisphere from filename: {path}. '
                        f'Files must start with "lh." or "rh."')

        if args.nifti and not args.subject:
            parser.error('--subject is required when projecting from --nifti')

        run_surface_analysis(
            nifti_path=args.nifti,
            surface_ts_paths=surface_ts_paths,
            subject=args.subject,
            subjects_dir=args.subjects_dir,
            hemis=args.hemi,
            reg_file=args.reg_file,
            target_subject=args.target_subject,
            projfrac=args.projfrac,
            smooth_fwhm=args.smooth_fwhm,
            n_cycles=n_cycles,
            config=config,
            noise_band=args.noise_band,
            detrend_order=args.detrend,
            dummy_volumes=args.dummy_volumes,
            warm_first=warm_first,
            out_dir=args.out_dir,
            output_format=args.output_format,
        )


if __name__ == '__main__':
    main()
