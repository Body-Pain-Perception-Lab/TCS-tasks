"""
Triangle waveform generation for electrical stimulation.

Generates a unipolar triangle wave of amplitude values (mV) for the DS5.
One cycle: floor → max → floor (seamless tile for continuous stimulation).
"""

import numpy as np


def generate_amplitude_waveform(cycle_duration, update_hz, max_amplitude,
                                ramp_floor=0.0):
    """Generate one full cycle of a unipolar triangle wave.

    The waveform tiles seamlessly: it starts and ends at the same value
    (0 or ramp_floor) so that consecutive cycles produce a continuous
    triangle with no inter-cycle dropouts.

    Without ramp_floor (default 0):
        0 → max → 0   (endpoints match for tiling)

    With ramp_floor > 0:
        floor → max → floor   (no zeros — seamless at floor level)

    The caller is responsible for inserting a single 0 at the very start
    and end of the full half if a silence bookend is needed.

    Parameters
    ----------
    cycle_duration : float
        Total duration of one cycle in seconds.
    update_hz : int
        Samples per second.
    max_amplitude : float
        Peak amplitude in mV.
    ramp_floor : float
        Minimum amplitude in mV during the ramp.  All values are linearly
        rescaled from [0, max] to [floor, max].  Default 0 (no floor).

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
        # Rescale entire waveform from [0, max] to [floor, max]
        amplitude = ramp_floor + (max_amplitude - ramp_floor) * (amplitude / max_amplitude)

    return amplitude


def phase_shift_waveform(waveform):
    """Shift waveform by half-period for ramp-down-first blocks.

    Shifts so the waveform starts at max and ramps down first:
        max → floor → max  (with floor)
        max → 0 → max      (without floor)
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
