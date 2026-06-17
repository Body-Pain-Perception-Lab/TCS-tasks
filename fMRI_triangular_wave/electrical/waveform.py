"""
Triangle waveform generation for electrical stimulation.

Generates a unipolar triangle wave of amplitude values (mV) for the DS5.
One cycle: 0 → max_amplitude → 0 (single up-down ramp).
"""

import numpy as np


def generate_amplitude_waveform(cycle_duration, update_hz, max_amplitude,
                                ramp_floor=0.0):
    """Generate one full cycle of a unipolar triangle wave.

    Without ramp_floor (default 0):
        0 → max → 0

    With ramp_floor > 0 the triangle ramps between floor and max, with a
    single 0-sample at each endpoint (matching the ds5.py pilot waveform):
        0 → floor..max..floor → 0

    Parameters
    ----------
    cycle_duration : float
        Total duration of one cycle in seconds.
    update_hz : int
        Samples per second.
    max_amplitude : float
        Peak amplitude in mV.
    ramp_floor : float
        Minimum non-zero amplitude in mV.  Samples that would fall below
        this are lifted to the floor, except the very first and last sample
        which stay at 0.  Default 0 (no floor).

    Returns
    -------
    np.ndarray
        1-D array of amplitude values, length = cycle_duration * update_hz.
    """
    n_samples = int(cycle_duration * update_hz)
    t = np.arange(n_samples) / update_hz

    # Unipolar triangle: 0 → max → 0
    phase = t / cycle_duration
    amplitude = max_amplitude * (1.0 - np.abs(2.0 * phase - 1.0))

    if ramp_floor > 0:
        # Rescale the ramp portion (samples 1..-2) into floor..max range
        inner = amplitude[1:-1]
        inner[:] = ramp_floor + (max_amplitude - ramp_floor) * (inner / max_amplitude)
        # Endpoints stay at 0

    return amplitude


def phase_shift_waveform(waveform):
    """Shift waveform by half-period for ramp-down-first blocks.

    Shifts so the waveform starts at max and ramps down first:
        max → 0 → max
    """
    return np.roll(waveform, len(waveform) // 2)


def clamp_amplitude(amplitude, amp_min=0.0, amp_max=10000.0):
    """Clamp amplitude to safe bounds.

    Parameters
    ----------
    amplitude : float
        Amplitude in mV.
    amp_min, amp_max : float
        Safety clamp bounds.

    Returns
    -------
    float
        Clamped amplitude.
    """
    return max(amp_min, min(amp_max, round(amplitude, 2)))
