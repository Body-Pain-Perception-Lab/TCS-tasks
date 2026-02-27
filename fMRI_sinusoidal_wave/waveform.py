"""
Sinusoidal waveform generation and mask application for thermal stimulation.
"""

import numpy as np


def generate_delta_waveform(cycle_duration, update_hz, max_delta=20.0):
    """Generate one full cycle of a bipolar sinusoidal wave as delta values.

    One cycle contains one full bipolar period:
        0 → +max_delta → 0 → -max_delta → 0

    For a +1 (warm) mask zone with baseline 30 C and max_delta 20 C:
        30 → 50 → 30 → 10 → 30

    Instantaneous ramp rate varies sinusoidally; peak rate is
    max_delta * 2π / cycle_duration.

    Parameters
    ----------
    cycle_duration : float
        Total duration of one cycle in seconds.
    update_hz : int
        Samples per second.
    max_delta : float
        Peak amplitude in degrees C.

    Returns
    -------
    np.ndarray
        1-D array of delta values, length = cycle_duration * update_hz.
    """
    n_samples = int(cycle_duration * update_hz)
    t = np.arange(n_samples) / update_hz

    # Bipolar sine: 0 → +A → 0 → -A → 0
    delta = max_delta * np.sin(2.0 * np.pi * t / cycle_duration)
    return delta


def phase_shift_waveform(waveform):
    """Shift waveform by half-period for cool-first blocks.

    Shifts the bipolar sine so that delta starts at 0 and goes negative
    first: 0 → -max_delta → 0 → +max_delta → 0
    (warm zones cool down first).
    """
    return np.roll(waveform, len(waveform) // 2)


def apply_mask(delta, mask, baseline_temp=30.0, temp_min=10.0, temp_max=50.0):
    """Compute 5-zone temperatures from a scalar delta and mask.

    Parameters
    ----------
    delta : float
        Current delta value from the waveform.
    mask : list or np.ndarray
        5-element array with values +1 (warm), -1 (cool), or 0 (neutral).
    baseline_temp : float
        Baseline temperature in degrees C.
    temp_min, temp_max : float
        Safety clamp bounds.

    Returns
    -------
    list of float
        5 zone temperatures, clamped to [temp_min, temp_max].
    """
    temps = []
    for s in mask:
        t = baseline_temp + s * delta
        t = max(temp_min, min(temp_max, t))
        temps.append(round(t, 2))
    return temps
