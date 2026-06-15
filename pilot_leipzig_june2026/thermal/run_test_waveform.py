"""
Test triangular waveform run with the TCS thermode.

Runs a short block (3 cycles by default) using the same triangular wave
as the main experiment, to verify temperatures are comfortable and the
thermode tracks setpoints correctly.

Can optionally override max_delta based on thresholds from the
Yes/No or Method of Limits tasks.

Usage:
    python run_test_waveform.py                     # default 17.5°C delta
    python run_test_waveform.py --delta 12.0        # custom delta
    python run_test_waveform.py --no-display        # console only
"""

import argparse
import csv
import math
import os
import time
from datetime import datetime

from config_thermal_L01 import CONFIG
from thermode import ThermodeController
from waveform import generate_delta_waveform, apply_mask
from masks import get_mask


def run_test(config, max_delta, mask_name, warm_first, use_display=True):
    """Run a short waveform test block."""

    baseline = config['baseline_temp']
    cycle_duration = config['waveform_cycle_duration']
    n_cycles = config['waveform_n_cycles']
    baseline_buffer = config['waveform_baseline_buffer']
    update_hz = config['update_hz']
    dt = 1.0 / update_hz
    samples_per_cycle = int(cycle_duration * update_hz)

    mask_array = get_mask(mask_name)

    # Generate waveform
    waveform = generate_delta_waveform(cycle_duration, update_hz, max_delta)

    total_time = 2 * baseline_buffer + n_cycles * cycle_duration
    print(f'\n{"=" * 55}')
    print(f'  Test Waveform Run')
    print(f'  Mask: {mask_name}  {mask_array}')
    print(f'  Delta: ±{max_delta}°C  (range: {baseline - max_delta:.1f}'
          f'–{baseline + max_delta:.1f}°C)')
    print(f'  Cycles: {n_cycles} x {cycle_duration}s = {n_cycles * cycle_duration}s')
    print(f'  Total: ~{total_time:.0f}s')
    print(f'  Direction: {"warm-first" if warm_first else "cool-first"}')
    print(f'{"=" * 55}\n')

    # PsychoPy
    win = None
    if use_display:
        from psychopy import visual, core, event
        from psychopy.hardware import keyboard
        win = visual.Window(
            size=[800, 600], units='height',
            fullscr=config['fullscreen'],
            screen=config['screen_index'],
            color=[0, 0, 0])
        fix = visual.Circle(win, radius=0.01, edges=32,
                            lineColor='white', fillColor='lightGrey')
        info = visual.TextStim(win, text='', height=0.03, color='grey',
                               pos=(0, -0.35))
        kb = keyboard.Keyboard()

    thermode = ThermodeController(config)

    # Configure for follow mode
    if not config['simulation']:
        thermode.device.set_ramp_speed([config['waveform_ramp_rate']] * 5)
        thermode.device.set_return_speed([config['waveform_ramp_rate']] * 5)
        thermode.device.set_follow()

    # Output file
    timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)
    tsv_path = os.path.join(data_dir, f'test_waveform_{timestamp}.tsv')
    tsv_file = open(tsv_path, 'w', newline='')
    writer = csv.writer(tsv_file, delimiter='\t')
    writer.writerow(['time_s', 'cycle', 'sample', 'delta',
                     'z1_cmd', 'z2_cmd', 'z3_cmd', 'z4_cmd', 'z5_cmd',
                     'z1_act', 'z2_act', 'z3_act', 'z4_act', 'z5_act'])

    try:
        # --- Pre-baseline ---
        print('  Pre-baseline...', flush=True)
        thermode.set_baseline()
        _run_baseline(baseline_buffer, thermode, writer, win, fix, info,
                      config, 'Pre-baseline')

        # --- Stimulation cycles ---
        t_start = time.monotonic()
        for cycle_idx in range(n_cycles):
            print(f'  Cycle {cycle_idx + 1}/{n_cycles}', flush=True)
            cycle_clock = time.monotonic()

            for sample_idx in range(samples_per_cycle):
                target_time = sample_idx * dt

                delta = float(waveform[sample_idx])
                temps = apply_mask(delta, mask_array, baseline,
                                   config['temp_min'], config['temp_max'])

                thermode.set_temperatures(temps)
                actual = thermode.get_temperatures()

                elapsed = time.monotonic() - t_start
                writer.writerow([
                    f'{elapsed:.4f}', cycle_idx, sample_idx,
                    f'{delta:.4f}',
                    f'{temps[0]:.2f}', f'{temps[1]:.2f}', f'{temps[2]:.2f}',
                    f'{temps[3]:.2f}', f'{temps[4]:.2f}',
                    f'{actual[0]}', f'{actual[1]}', f'{actual[2]}',
                    f'{actual[3]}', f'{actual[4]}',
                ])

                if win:
                    fix.draw()
                    info.text = (f'Cycle {cycle_idx + 1}/{n_cycles}  '
                                 f'D={delta:.1f}  '
                                 f'Z: {temps[0]:.0f} {temps[1]:.0f} '
                                 f'{temps[2]:.0f} {temps[3]:.0f} {temps[4]:.0f}')
                    info.draw()
                    win.flip()

                    keys = kb.getKeys(keyList=['escape'])
                    if keys:
                        raise KeyboardInterrupt('Escape pressed')

                # Timing
                wait = dt - (time.monotonic() - cycle_clock - target_time)
                if wait > 0:
                    time.sleep(wait)

            # Flush after each cycle
            tsv_file.flush()

        # --- Post-baseline ---
        print('  Post-baseline...', flush=True)
        thermode.set_baseline()
        _run_baseline(baseline_buffer, thermode, writer, win, fix, info,
                      config, 'Post-baseline')

    except KeyboardInterrupt:
        print('\n  Aborted.')
    finally:
        thermode.set_baseline()
        thermode.close()
        tsv_file.close()

    if win:
        win.close()

    print(f'\n  Data saved: {tsv_path}')
    print('  Test waveform complete.')


def _run_baseline(duration, thermode, writer, win, fix, info, config, label):
    """Hold baseline for a period, logging data."""
    update_hz = config['update_hz']
    dt = 1.0 / update_hz
    n_samples = int(duration * update_hz)
    baseline_temps = [config['baseline_temp']] * 5
    t_start = time.monotonic()

    for i in range(n_samples):
        thermode.set_temperatures(baseline_temps)
        actual = thermode.get_temperatures()
        elapsed = time.monotonic() - t_start

        writer.writerow([
            f'{elapsed:.4f}', -1, i, '0.0000',
            f'{baseline_temps[0]:.2f}', f'{baseline_temps[1]:.2f}',
            f'{baseline_temps[2]:.2f}', f'{baseline_temps[3]:.2f}',
            f'{baseline_temps[4]:.2f}',
            f'{actual[0]}', f'{actual[1]}', f'{actual[2]}',
            f'{actual[3]}', f'{actual[4]}',
        ])

        if win:
            fix.draw()
            info.text = label
            info.draw()
            win.flip()

        wait = dt - (time.monotonic() - t_start - i * dt)
        if wait > 0:
            time.sleep(wait)


def main():
    parser = argparse.ArgumentParser(description='Test triangular waveform')
    parser.add_argument('--delta', type=float, default=None,
                        help='Override max_delta (°C)')
    parser.add_argument('--mask', default='P1',
                        help='Mask name (default: P1)')
    parser.add_argument('--cycles', type=int, default=None,
                        help='Number of cycles')
    parser.add_argument('--cool-first', action='store_true',
                        help='Start with cooling (default: warm-first)')
    parser.add_argument('--no-display', action='store_true',
                        help='Console only (no PsychoPy)')
    args = parser.parse_args()

    config = dict(CONFIG)
    max_delta = args.delta if args.delta else config['waveform_max_delta']
    if args.cycles:
        config['waveform_n_cycles'] = args.cycles

    run_test(config, max_delta, args.mask, warm_first=not args.cool_first,
             use_display=not args.no_display)


if __name__ == '__main__':
    main()
