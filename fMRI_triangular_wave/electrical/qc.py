"""
Real-time quality control for DS5 electrical stimulation.

Tracks per-cycle metrics:
- Timing precision (actual vs expected sample intervals)
- Amplitude ramp rate
- Number of delivered pulses
"""

import math
import numpy as np


class ElectricalQC:
    """Accumulates per-sample stimulation data and computes QC metrics.

    Usage:
        qc = ElectricalQC(config)
        qc.start_cycle(cycle_idx)
        for each sample:
            qc.update(timestamp, amplitude)
        summary = qc.end_cycle()
    """

    def __init__(self, config):
        self.update_hz = config['update_hz']
        self.simulation = config['simulation']
        self._cycle_summaries = []
        self._reset_cycle()

    def _reset_cycle(self):
        self._cycle_idx = None
        self._prev_timestamp = None
        self._amplitudes = []
        self._timing_errors = []
        self._n_pulses = 0

    def start_cycle(self, cycle_idx):
        self._reset_cycle()
        self._cycle_idx = cycle_idx

    def update(self, timestamp, amplitude):
        """Process one sample.

        Parameters
        ----------
        timestamp : float
            Time from trigger (seconds).
        amplitude : float
            Commanded amplitude in mV.
        """
        self._amplitudes.append(amplitude)
        self._n_pulses += 1

        if self._prev_timestamp is not None:
            dt = timestamp - self._prev_timestamp
            expected_dt = 1.0 / self.update_hz
            self._timing_errors.append(abs(dt - expected_dt))

        self._prev_timestamp = timestamp

    def end_cycle(self):
        amplitudes = np.array(self._amplitudes) if self._amplitudes else np.array([])
        timing_errors = np.array(self._timing_errors) if self._timing_errors else np.array([])

        summary = {
            'cycle_index': self._cycle_idx,
            'n_pulses': self._n_pulses,
            'mean_amplitude': _safe_mean(amplitudes),
            'max_amplitude': _safe_max(amplitudes),
            'mean_timing_error_ms': _safe_mean(timing_errors) * 1000,
            'max_timing_error_ms': _safe_max(timing_errors) * 1000,
            'n_samples': len(amplitudes),
        }
        self._cycle_summaries.append(summary)
        return summary

    def get_block_summaries(self):
        return list(self._cycle_summaries)

    def reset_block(self):
        self._cycle_summaries = []
        self._reset_cycle()


def _safe_mean(arr):
    return float(np.nanmean(arr)) if len(arr) > 0 else math.nan


def _safe_max(arr):
    return float(np.nanmax(arr)) if len(arr) > 0 else math.nan
