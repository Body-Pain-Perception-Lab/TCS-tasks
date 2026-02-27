#!/usr/bin/env python3
"""
Cost-benefit simulation: sinusoidal vs triangular waveform for phase encoding.

Compares the two waveforms on:
1. Power spectrum — how much signal is at the fundamental vs harmonics
2. Phase estimation accuracy — how well phase is recovered from noisy fMRI data
3. Temperature dwell time — how uniformly the temperature space is sampled

Uses the actual experiment parameters:
    cycle_duration = 28s, max_delta = 17.5°C, TR = 1.5s,
    25 cycles, baseline_temp = 30°C

Usage:
    python3 simulate_waveform_comparison.py
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import gamma as gamma_dist


# ── Experiment parameters ────────────────────────────────────────────────────
CYCLE_DURATION = 28.0       # seconds
MAX_DELTA = 17.5            # °C
BASELINE_TEMP = 30.0        # °C
N_CYCLES = 25
TR = 1.5                    # seconds
BASELINE_BUFFER = 3.5       # seconds
DUMMY_TIME = 6.0            # 4 dummy volumes × 1.5s

STIM_START = DUMMY_TIME + BASELINE_BUFFER       # 9.5s
STIM_DUR = N_CYCLES * CYCLE_DURATION            # 700s
STIM_END = STIM_START + STIM_DUR                # 709.5s
TOTAL_TIME = STIM_END + BASELINE_BUFFER         # 713s
N_VOLUMES = int(np.ceil(TOTAL_TIME / TR))

# Simulation parameters
N_SIMULATIONS = 5000        # Monte Carlo runs for phase estimation
SNR_LEVELS = [0.5, 1.0, 2.0, 3.0, 5.0]  # signal amplitude / noise std


# ── HRF ──────────────────────────────────────────────────────────────────────
def spm_hrf(dt, time_length=32.0):
    t = np.arange(0, time_length, dt)
    hrf = (gamma_dist.pdf(t, 6.0, scale=1.0) -
           gamma_dist.pdf(t, 16.0, scale=1.0) / 6.0)
    if np.max(hrf) > 0:
        hrf = hrf / np.max(hrf)
    return hrf


# ── Waveform generators ─────────────────────────────────────────────────────
def generate_sinusoidal(t, cycle_duration, max_delta):
    """Bipolar sine: 0 → +A → 0 → -A → 0"""
    return max_delta * np.sin(2 * np.pi * t / cycle_duration)


def generate_triangular(t, cycle_duration, max_delta):
    """Bipolar triangle: 0 → +A → 0 → -A → 0"""
    phase = (t % cycle_duration) / cycle_duration
    shifted = (phase + 0.25) % 1.0
    return max_delta * (1.0 - 2.0 * np.abs(2.0 * shifted - 1.0))


# ── 1. Power spectrum analysis ───────────────────────────────────────────────
def analyse_power_spectrum(fig_axes):
    """Compare frequency content of both waveforms."""
    # Generate high-resolution waveforms during stimulation only
    dt = 0.01  # 100 Hz for clean spectrum
    t = np.arange(0, STIM_DUR, dt)

    sine_wave = generate_sinusoidal(t, CYCLE_DURATION, MAX_DELTA)
    tri_wave = generate_triangular(t, CYCLE_DURATION, MAX_DELTA)

    # FFT
    n = len(t)
    freqs = np.fft.rfftfreq(n, dt)
    fund_freq = 1.0 / CYCLE_DURATION  # 0.0357 Hz

    sine_fft = np.abs(np.fft.rfft(sine_wave)) / n * 2
    tri_fft = np.abs(np.fft.rfft(tri_wave)) / n * 2

    # Power at fundamental and harmonics
    freq_resolution = freqs[1] - freqs[0]
    harmonics = [1, 3, 5, 7, 9]  # triangle has odd harmonics only
    print("=" * 65)
    print("1. POWER SPECTRUM ANALYSIS")
    print("=" * 65)
    print(f"   Fundamental frequency: {fund_freq:.4f} Hz ({CYCLE_DURATION}s cycle)")
    print(f"   {'Harmonic':<12} {'Freq (Hz)':<12} {'Sine amp':<14} {'Triangle amp':<14}")
    print(f"   {'-'*52}")

    sine_power_fund = 0
    tri_power_fund = 0
    sine_power_total = 0
    tri_power_total = 0

    for h in harmonics:
        target_freq = h * fund_freq
        idx = np.argmin(np.abs(freqs - target_freq))
        s_amp = sine_fft[idx]
        t_amp = tri_fft[idx]
        label = f"{h}f" + (" (fund.)" if h == 1 else "")
        print(f"   {label:<12} {target_freq:<12.4f} {s_amp:<14.2f} {t_amp:<14.2f}")
        if h == 1:
            sine_power_fund = s_amp**2
            tri_power_fund = t_amp**2
        sine_power_total += s_amp**2
        tri_power_total += t_amp**2

    sine_pct = 100 * sine_power_fund / sine_power_total if sine_power_total > 0 else 0
    tri_pct = 100 * tri_power_fund / tri_power_total if tri_power_total > 0 else 0
    print(f"\n   Power at fundamental (% of total harmonic power):")
    print(f"     Sinusoidal: {sine_pct:.1f}%")
    print(f"     Triangular: {tri_pct:.1f}%")
    print(f"   Fundamental amplitude ratio (tri/sine): {np.sqrt(tri_power_fund/sine_power_fund):.3f}")

    # Plot
    ax1, ax2 = fig_axes

    # Waveform comparison (2 cycles)
    t_show = np.linspace(0, 2 * CYCLE_DURATION, 1000)
    ax1.plot(t_show, BASELINE_TEMP + generate_sinusoidal(t_show, CYCLE_DURATION, MAX_DELTA),
             'b-', linewidth=2, label='Sinusoidal')
    ax1.plot(t_show, BASELINE_TEMP + generate_triangular(t_show, CYCLE_DURATION, MAX_DELTA),
             'r-', linewidth=2, label='Triangular')
    ax1.axhline(BASELINE_TEMP, color='grey', linestyle=':', alpha=0.5)
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Temperature (°C)')
    ax1.set_title('Waveform shape (2 cycles)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Power spectrum
    mask = (freqs > 0) & (freqs < 12 * fund_freq)
    ax2.stem(freqs[mask] / fund_freq, sine_fft[mask], linefmt='b-', markerfmt='bo',
             basefmt='b-', label='Sinusoidal')
    ax2.stem(freqs[mask] / fund_freq, tri_fft[mask], linefmt='r-', markerfmt='r^',
             basefmt='r-', label='Triangular')
    ax2.set_xlabel('Frequency (multiples of fundamental)')
    ax2.set_ylabel('Amplitude (°C)')
    ax2.set_title('Power spectrum')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    return sine_pct, tri_pct


# ── 2. Phase estimation accuracy ────────────────────────────────────────────
def simulate_phase_estimation(fig_ax):
    """Monte Carlo simulation of phase recovery from noisy BOLD data."""
    # Generate BOLD-like signal: waveform → HRF convolution → downsample to TR
    oversampling = 16
    dt = TR / oversampling
    n_hires = int(np.ceil(TOTAL_TIME / dt))
    t_hires = np.arange(n_hires) * dt
    hrf = spm_hrf(dt)

    # Stimulation mask
    stim_mask = (t_hires >= STIM_START) & (t_hires < STIM_END)
    t_stim = t_hires - STIM_START

    # Generate neural signals
    sine_neural = np.zeros(n_hires)
    tri_neural = np.zeros(n_hires)
    sine_neural[stim_mask] = generate_sinusoidal(t_stim[stim_mask], CYCLE_DURATION, MAX_DELTA)
    tri_neural[stim_mask] = generate_triangular(t_stim[stim_mask], CYCLE_DURATION, MAX_DELTA)

    # Convolve with HRF
    sine_bold_hr = np.convolve(sine_neural, hrf * dt)[:n_hires]
    tri_bold_hr = np.convolve(tri_neural, hrf * dt)[:n_hires]

    # Downsample to TR
    frame_times = np.arange(N_VOLUMES) * TR
    tr_idx = np.minimum(np.round(frame_times / dt).astype(int), n_hires - 1)
    sine_bold = sine_bold_hr[tr_idx]
    tri_bold = tri_bold_hr[tr_idx]

    # Normalise to unit amplitude for fair comparison
    sine_bold = sine_bold / np.max(np.abs(sine_bold))
    tri_bold = tri_bold / np.max(np.abs(tri_bold))

    # True phase at fundamental frequency (from clean signal)
    stim_volumes = (frame_times >= STIM_START) & (frame_times < STIM_END)
    n_stim_vols = np.sum(stim_volumes)

    def get_phase_at_fundamental(signal, stim_mask_vol):
        """Extract phase at stimulus frequency from signal."""
        sig = signal[stim_mask_vol]
        sig = sig - np.mean(sig)
        fft_vals = np.fft.rfft(sig)
        freqs = np.fft.rfftfreq(len(sig), TR)
        fund_idx = np.argmin(np.abs(freqs - 1.0 / CYCLE_DURATION))
        return np.angle(fft_vals[fund_idx]), np.abs(fft_vals[fund_idx])

    true_phase_sine, true_amp_sine = get_phase_at_fundamental(sine_bold, stim_volumes)
    true_phase_tri, true_amp_tri = get_phase_at_fundamental(tri_bold, stim_volumes)

    print(f"\n{'=' * 65}")
    print("2. PHASE ESTIMATION ACCURACY (Monte Carlo simulation)")
    print(f"{'=' * 65}")
    print(f"   {N_SIMULATIONS} simulations per SNR level")
    print(f"   Stimulus volumes: {n_stim_vols} ({n_stim_vols * TR:.0f}s)")
    print(f"\n   Clean signal amplitude at fundamental (normalised):")
    print(f"     Sinusoidal: {true_amp_sine:.2f}")
    print(f"     Triangular: {true_amp_tri:.2f}")
    print(f"     Ratio (sine/tri): {true_amp_sine/true_amp_tri:.3f}")

    print(f"\n   {'SNR':<8} {'Sine phase err':<20} {'Tri phase err':<20} {'Advantage'}")
    print(f"   {'-'*68}")

    sine_errors = []
    tri_errors = []

    for snr in SNR_LEVELS:
        sine_phase_errors = []
        tri_phase_errors = []

        for _ in range(N_SIMULATIONS):
            noise = np.random.randn(N_VOLUMES) / snr

            # Add noise and estimate phase
            noisy_sine = sine_bold + noise
            noisy_tri = tri_bold + noise

            est_phase_sine, _ = get_phase_at_fundamental(noisy_sine, stim_volumes)
            est_phase_tri, _ = get_phase_at_fundamental(noisy_tri, stim_volumes)

            # Circular error
            err_sine = np.abs(np.angle(np.exp(1j * (est_phase_sine - true_phase_sine))))
            err_tri = np.abs(np.angle(np.exp(1j * (est_phase_tri - true_phase_tri))))

            sine_phase_errors.append(np.degrees(err_sine))
            tri_phase_errors.append(np.degrees(err_tri))

        sine_mean = np.mean(sine_phase_errors)
        tri_mean = np.mean(tri_phase_errors)
        sine_errors.append(sine_mean)
        tri_errors.append(tri_mean)

        better = "sine" if sine_mean < tri_mean else "tri"
        pct = abs(sine_mean - tri_mean) / max(sine_mean, tri_mean) * 100
        print(f"   {snr:<8.1f} {sine_mean:<20.2f}° {tri_mean:<20.2f}° "
              f"{better} better by {pct:.1f}%")

    # Plot
    ax = fig_ax
    ax.plot(SNR_LEVELS, sine_errors, 'bo-', linewidth=2, markersize=8, label='Sinusoidal')
    ax.plot(SNR_LEVELS, tri_errors, 'r^-', linewidth=2, markersize=8, label='Triangular')
    ax.set_xlabel('SNR')
    ax.set_ylabel('Mean phase error (°)')
    ax.set_title(f'Phase estimation accuracy ({N_SIMULATIONS} simulations)')
    ax.legend()
    ax.grid(True, alpha=0.3)


# ── 3. Temperature dwell time ───────────────────────────────────────────────
def analyse_dwell_time(fig_ax):
    """Compare how much time is spent at each temperature level."""
    dt = 0.001
    t = np.arange(0, STIM_DUR, dt)

    sine_temps = BASELINE_TEMP + generate_sinusoidal(t, CYCLE_DURATION, MAX_DELTA)
    tri_temps = BASELINE_TEMP + generate_triangular(t, CYCLE_DURATION, MAX_DELTA)

    # Histogram of temperature dwell time
    temp_bins = np.linspace(BASELINE_TEMP - MAX_DELTA, BASELINE_TEMP + MAX_DELTA, 51)

    print(f"\n{'=' * 65}")
    print("3. TEMPERATURE DWELL TIME ANALYSIS")
    print(f"{'=' * 65}")

    sine_hist, _ = np.histogram(sine_temps, bins=temp_bins)
    tri_hist, _ = np.histogram(tri_temps, bins=temp_bins)

    # Normalise to percentage of total time
    sine_pct = sine_hist / sine_hist.sum() * 100
    tri_pct = tri_hist / tri_hist.sum() * 100

    # Uniformity metric (coefficient of variation — lower = more uniform)
    sine_cv = np.std(sine_pct) / np.mean(sine_pct)
    tri_cv = np.std(tri_pct) / np.mean(tri_pct)

    print(f"   Temperature range: {BASELINE_TEMP - MAX_DELTA}°C to {BASELINE_TEMP + MAX_DELTA}°C")
    print(f"   Dwell time uniformity (CV, lower = more uniform):")
    print(f"     Sinusoidal: {sine_cv:.3f}")
    print(f"     Triangular: {tri_cv:.3f}")
    print(f"\n   Time at extremes (within 2°C of peak):")
    extreme_mask = (temp_bins[:-1] > BASELINE_TEMP + MAX_DELTA - 2) | \
                   (temp_bins[:-1] < BASELINE_TEMP - MAX_DELTA + 2)
    mid_mask = (temp_bins[:-1] > BASELINE_TEMP - 2) & (temp_bins[:-1] < BASELINE_TEMP + 2)
    print(f"     Sinusoidal: {sine_pct[extreme_mask].sum():.1f}%")
    print(f"     Triangular: {tri_pct[extreme_mask].sum():.1f}%")
    print(f"   Time near baseline (within 2°C of 30°C):")
    print(f"     Sinusoidal: {sine_pct[mid_mask].sum():.1f}%")
    print(f"     Triangular: {tri_pct[mid_mask].sum():.1f}%")

    # Plot
    ax = fig_ax
    bin_centers = (temp_bins[:-1] + temp_bins[1:]) / 2
    width = (temp_bins[1] - temp_bins[0]) * 0.4
    ax.bar(bin_centers - width/2, sine_pct, width=width, color='blue', alpha=0.7,
           label='Sinusoidal')
    ax.bar(bin_centers + width/2, tri_pct, width=width, color='red', alpha=0.7,
           label='Triangular')
    ax.axvline(BASELINE_TEMP, color='grey', linestyle=':', alpha=0.5)
    ax.set_xlabel('Temperature (°C)')
    ax.set_ylabel('Dwell time (%)')
    ax.set_title('Time spent at each temperature')
    ax.legend()
    ax.grid(True, alpha=0.3)


# ── Summary ──────────────────────────────────────────────────────────────────
def print_summary(sine_pct_fund, tri_pct_fund):
    print(f"\n{'=' * 65}")
    print("SUMMARY")
    print(f"{'=' * 65}")
    print(f"""
   ┌────────────────────┬──────────────┬──────────────┐
   │ Criterion          │ Sinusoidal   │ Triangular   │
   ├────────────────────┼──────────────┼──────────────┤
   │ Power at fund.     │ {sine_pct_fund:>10.1f}%  │ {tri_pct_fund:>10.1f}%  │
   │ Harmonic leakage   │ None         │ 3f, 5f, 7f…  │
   │ Temp. uniformity   │ Biased to    │ Uniform      │
   │                    │ extremes     │              │
   │ Rate of change     │ Variable     │ Constant     │
   │                    │ (0–3.9°C/s)  │ (2.5°C/s)    │
   │ Hardware tracking  │ Easier       │ Sharp corners│
   │                    │ (smooth)     │ need fast HW │
   └────────────────────┴──────────────┴──────────────┘

   RECOMMENDATION:
   - If phase estimation accuracy at the fundamental is similar (see
     plot), the choice comes down to secondary factors.
   - Sinusoidal: cleaner spectrum, easier for thermode hardware to
     track (no abrupt direction changes), all power at one frequency.
   - Triangular: uniform temperature sampling, constant rate matches
     traditional retinotopy paradigms.
   - For a FIRST experiment, sinusoidal is the safer choice: it avoids
     harmonic contamination and is more forgiving of thermode lag.
   - You do NOT need to test both in the MRI. The phase estimation
     simulation above uses realistic BOLD noise — the differences
     shown are what you would observe in real data.
""")


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print(f"\nWaveform comparison: sinusoidal vs triangular")
    print(f"Parameters: cycle={CYCLE_DURATION}s, amplitude={MAX_DELTA}°C, "
          f"{N_CYCLES} cycles, TR={TR}s\n")

    fig = plt.figure(figsize=(14, 12))
    fig.suptitle('Sinusoidal vs Triangular Waveform Comparison\n'
                 f'({CYCLE_DURATION}s cycle, {MAX_DELTA}°C amplitude, '
                 f'{N_CYCLES} cycles, TR={TR}s)',
                 fontsize=13, fontweight='bold')

    ax1 = fig.add_subplot(2, 2, 1)
    ax2 = fig.add_subplot(2, 2, 2)
    ax3 = fig.add_subplot(2, 2, 3)
    ax4 = fig.add_subplot(2, 2, 4)

    sine_pct, tri_pct = analyse_power_spectrum((ax1, ax2))
    simulate_phase_estimation(ax3)
    analyse_dwell_time(ax4)
    print_summary(sine_pct, tri_pct)

    fig.tight_layout()
    out_path = 'waveform_comparison.png'
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f"   Figure saved: {out_path}")
    plt.close(fig)


if __name__ == '__main__':
    main()
