"""
Triangular wave electrical stimulation — mirrors the thermal paradigm.

Delivers a train of electrical pulses whose amplitude follows a bipolar
triangular envelope, matching the thermal experiment's waveform shape:

    mid → high → mid → low → mid   (one cycle)

Mapping from thermal to electrical:
    - Thermal baseline (30°C)       → mid-intensity (midpoint of EDT–EPT)
    - Thermal +max_delta (47.5°C)   → high intensity (near EPT)
    - Thermal -max_delta (12.5°C)   → low intensity (near EDT)
    - Thermal ramp rate (2.5°C/s)   → electrical ramp in mV/s that gives
                                       the same cycle timing (28s)

Pulse train: pulses are delivered at a fixed rate (default 5 Hz).
Each pulse amplitude follows the triangular waveform.

Usage:
    python run_triangular_wave.py --edt 200 --ept 800     # real thresholds
    python run_triangular_wave.py --edt 200 --ept 800 --cycles 3
    python run_triangular_wave.py --edt 200 --ept 800 --no-display
    python run_triangular_wave.py --auto                   # read from ethresh_summary
"""

import argparse
import csv
import json
import math
import os
import time
from datetime import datetime

import numpy as np

from config_electric_L01 import CONFIG
from ds5_controller import DS5Controller


def generate_electrical_waveform(cycle_duration, pulse_hz, mid_mv, delta_mv):
    """Generate one cycle of bipolar triangular amplitude envelope.

    Mirrors thermal generate_delta_waveform():
        0 → +delta → 0 → -delta → 0

    Mapped to electrical:
        mid → mid+delta → mid → mid-delta → mid

    Parameters
    ----------
    cycle_duration : float
        Duration of one cycle in seconds.
    pulse_hz : float
        Pulse delivery rate (Hz).
    mid_mv : float
        Centre amplitude in mV (the "baseline" intensity).
    delta_mv : float
        Peak deviation from mid (mV).

    Returns
    -------
    amplitudes : np.ndarray
        Amplitude in mV for each pulse in one cycle.
    ramp_rate_mv_s : float
        Ramp rate in mV/s (analogous to 2.5°C/s in thermal).
    """
    n_pulses = int(cycle_duration * pulse_hz)
    t = np.arange(n_pulses) / pulse_hz

    # Bipolar triangle: 0 → +A → 0 → -A → 0
    phase = (t % cycle_duration) / cycle_duration
    shifted = (phase + 0.25) % 1.0
    delta_envelope = delta_mv * (1.0 - 2.0 * np.abs(2.0 * shifted - 1.0))

    amplitudes = mid_mv + delta_envelope
    # Clamp to non-negative
    amplitudes = np.clip(amplitudes, 0, None)

    ramp_rate_mv_s = delta_mv / (cycle_duration / 4)

    return amplitudes, ramp_rate_mv_s


def run_wave(config, edt_mv, ept_mv, n_cycles, pulse_hz, use_display=True):
    """Run the triangular wave electrical stimulation."""

    cycle_duration = config.get('wave_cycle_duration', 28.0)
    pw = config['pulse_width_ms']
    baseline_buffer = config.get('wave_baseline_buffer', 6.0)
    dt = 1.0 / pulse_hz

    # Compute mid-intensity and delta from thresholds
    mid_mv = (edt_mv + ept_mv) / 2.0
    delta_mv = (ept_mv - edt_mv) / 2.0

    # Generate one cycle
    cycle_amplitudes, ramp_rate = generate_electrical_waveform(
        cycle_duration, pulse_hz, mid_mv, delta_mv)
    pulses_per_cycle = len(cycle_amplitudes)

    total_stim = n_cycles * cycle_duration
    total_time = 2 * baseline_buffer + total_stim

    print(f'\n{"=" * 60}')
    print(f'  Electrical Triangular Wave')
    print(f'  EDT = {edt_mv:.0f} mV,  EPT = {ept_mv:.0f} mV')
    print(f'  Mid-intensity = {mid_mv:.0f} mV,  delta = ±{delta_mv:.0f} mV')
    print(f'  Range: {mid_mv - delta_mv:.0f} – {mid_mv + delta_mv:.0f} mV')
    print(f'  Ramp rate: {ramp_rate:.1f} mV/s  '
          f'(analogous to thermal 2.5°C/s)')
    print(f'  Cycle: {cycle_duration}s  |  Pulse rate: {pulse_hz} Hz  '
          f'|  Pulse width: {pw} ms')
    print(f'  Cycles: {n_cycles}  |  Total: ~{total_time:.0f}s')
    print(f'{"=" * 60}\n')

    # PsychoPy
    win = None
    if use_display:
        from psychopy import visual, core
        from psychopy.hardware import keyboard
        win = visual.Window(
            size=[800, 600], units='height', fullscr=False,
            screen=0, color=[0, 0, 0])
        fix = visual.Circle(win, radius=0.01, edges=32,
                            lineColor='white', fillColor='lightGrey')
        info = visual.TextStim(win, text='', height=0.03, color='grey',
                               pos=(0, -0.35))
        kb = keyboard.Keyboard()

    ds5 = DS5Controller(port=config['com_port'],
                        simulation=config['simulation'])
    ds5.set_pulse_width(pw)

    # Output
    timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)
    tsv_path = os.path.join(data_dir, f'ewave_{timestamp}.tsv')
    tsv_file = open(tsv_path, 'w', newline='')
    writer = csv.writer(tsv_file, delimiter='\t')
    writer.writerow(['time_s', 'cycle', 'pulse_idx', 'amplitude_mv',
                     'delta_from_mid_mv', 'phase'])

    t_start = time.monotonic()

    try:
        # --- Pre-baseline (no pulses, just wait) ---
        print('  Pre-baseline...', flush=True)
        if win:
            fix.draw()
            info.text = 'Pre-baseline'
            info.draw()
            win.flip()
        _wait(baseline_buffer, win)

        # --- Stimulation cycles ---
        for cycle_idx in range(n_cycles):
            print(f'  Cycle {cycle_idx + 1}/{n_cycles}', flush=True)
            cycle_start = time.monotonic()

            for pulse_idx in range(pulses_per_cycle):
                target_time = pulse_idx * dt
                amp = float(cycle_amplitudes[pulse_idx])
                delta_from_mid = amp - mid_mv

                # Deliver pulse
                ds5.set_amplitude(amp)
                ds5.trigger()

                elapsed = time.monotonic() - t_start

                # Determine phase label
                frac = pulse_idx / pulses_per_cycle
                if frac < 0.25:
                    phase = 'rising'
                elif frac < 0.5:
                    phase = 'falling-to-mid'
                elif frac < 0.75:
                    phase = 'falling'
                else:
                    phase = 'rising-to-mid'

                writer.writerow([
                    f'{elapsed:.4f}', cycle_idx, pulse_idx,
                    f'{amp:.1f}', f'{delta_from_mid:.1f}', phase])

                if win:
                    fix.draw()
                    info.text = (f'Cycle {cycle_idx + 1}/{n_cycles}  |  '
                                 f'{amp:.0f} mV  |  '
                                 f'D={delta_from_mid:+.0f}')
                    info.draw()
                    win.flip()
                    keys = kb.getKeys(keyList=['escape'])
                    if keys:
                        raise KeyboardInterrupt('Escape pressed')

                # Timing: wait until next pulse is due
                wait = dt - (time.monotonic() - cycle_start - target_time)
                if wait > 0:
                    time.sleep(wait)

            tsv_file.flush()

        # --- Post-baseline ---
        print('  Post-baseline...', flush=True)
        if win:
            fix.draw()
            info.text = 'Post-baseline'
            info.draw()
            win.flip()
        _wait(baseline_buffer, win)

    except KeyboardInterrupt:
        print('\n  Aborted.')
    finally:
        ds5.close()
        tsv_file.close()

    if win:
        win.close()

    # Save metadata
    meta = {
        'timestamp': timestamp,
        'edt_mv': edt_mv,
        'ept_mv': ept_mv,
        'mid_mv': mid_mv,
        'delta_mv': delta_mv,
        'ramp_rate_mv_s': ramp_rate,
        'cycle_duration_s': cycle_duration,
        'n_cycles': n_cycles,
        'pulse_hz': pulse_hz,
        'pulse_width_ms': pw,
        'config': config,
    }
    meta_path = os.path.join(data_dir, f'ewave_{timestamp}.json')
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2, default=str)

    print(f'\n  Data saved: {tsv_path}')
    print(f'  Metadata saved: {meta_path}')


def _wait(duration, win=None):
    if win is not None:
        from psychopy import core
        core.wait(duration)
    else:
        time.sleep(duration)


def main():
    parser = argparse.ArgumentParser(
        description='Triangular wave electrical stimulation')
    parser.add_argument('--edt', type=float, default=None,
                        help='Electrical detection threshold (mV)')
    parser.add_argument('--ept', type=float, default=None,
                        help='Electrical pain threshold (mV)')
    parser.add_argument('--auto', action='store_true',
                        help='Read thresholds from latest ethresh_summary JSON')
    parser.add_argument('--cycles', type=int, default=3,
                        help='Number of cycles (default: 3)')
    parser.add_argument('--pulse-hz', type=float, default=5.0,
                        help='Pulse delivery rate in Hz (default: 5)')
    parser.add_argument('--no-display', action='store_true',
                        help='Console mode (no PsychoPy)')
    args = parser.parse_args()

    config = dict(CONFIG)

    # Resolve thresholds
    edt = args.edt
    ept = args.ept

    if args.auto or (edt is None and ept is None):
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'data')
        summaries = sorted(
            [f for f in os.listdir(data_dir)
             if f.startswith('ethresh_summary_')]
        ) if os.path.isdir(data_dir) else []

        if summaries:
            latest = os.path.join(data_dir, summaries[-1])
            with open(latest) as f:
                thresh = json.load(f)
            auto_edt = thresh.get('edt_mean_mv')
            auto_ept = thresh.get('ept_mean_mv')
            print(f'  Found thresholds: EDT={auto_edt} mV, EPT={auto_ept} mV '
                  f'({summaries[-1]})')
            if edt is None:
                edt = auto_edt
            if ept is None:
                ept = auto_ept

    if edt is None or ept is None:
        print('ERROR: Need both --edt and --ept, or run run_threshold.py first '
              'and use --auto')
        return

    if edt >= ept:
        print(f'ERROR: EDT ({edt}) must be less than EPT ({ept})')
        return

    run_wave(config, edt, ept, args.cycles, args.pulse_hz,
             use_display=not args.no_display)


if __name__ == '__main__':
    main()
