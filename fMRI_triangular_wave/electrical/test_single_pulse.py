"""
Interactive DS5 single-pulse testing.

Manually trigger electrical pulses one at a time to explore the
perceptible intensity range. Press Enter to deliver a pulse,
+/- to adjust amplitude, and q to quit.

Usage:
    python test_single_pulse.py                          # simulation
    python test_single_pulse.py --port /dev/ttyUSB0      # real hardware (Linux)
    python test_single_pulse.py --port COM4               # real hardware (Windows)
    python test_single_pulse.py --port /dev/ttyUSB0 --pw 1.0 --start 100 --step 50
"""

import argparse
import csv
import os
import sys
from datetime import datetime

from ds5_controller import DS5Controller


def run_test(port, simulation, pulse_width_ms, start_mv, step_mv):
    """Interactive pulse testing loop."""

    ds5 = DS5Controller(port=port, simulation=simulation)
    ds5.set_pulse_width(pulse_width_ms)

    amplitude_mv = start_mv
    ds5.set_amplitude(amplitude_mv)

    # Log file
    timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f'pulse_test_{timestamp}.tsv')
    log_file = open(log_path, 'w', newline='')
    log_writer = csv.writer(log_file, delimiter='\t')
    log_writer.writerow(['pulse_num', 'amplitude_mv', 'pulse_width_ms', 'simulation'])

    pulse_count = 0
    mode = 'SIM' if simulation else f'LIVE ({port})'

    print(f'\n{"=" * 55}')
    print(f'  DS5 Single Pulse Test — {mode}')
    print(f'  Pulse width: {pulse_width_ms} ms')
    print(f'  Starting amplitude: {amplitude_mv} mV')
    print(f'  Step size: {step_mv} mV')
    print(f'{"=" * 55}')
    print()
    print('  Controls:')
    print('    Enter     — deliver pulse at current amplitude')
    print('    +  or  u  — increase amplitude by step')
    print('    -  or  d  — decrease amplitude by step')
    print('    number    — set amplitude directly (e.g. "250")')
    print('    s <value> — change step size (e.g. "s 25")')
    print('    w <value> — change pulse width in ms (e.g. "w 0.5")')
    print('    q         — quit')
    print()

    try:
        while True:
            prompt = (f'  [{pulse_count} pulses]  '
                      f'amplitude={amplitude_mv} mV  '
                      f'pw={pulse_width_ms} ms  '
                      f'step={step_mv} mV  > ')
            try:
                user_input = input(prompt).strip().lower()
            except EOFError:
                break

            if user_input == 'q':
                break

            elif user_input in ('', 'p'):
                # Trigger pulse
                ds5.set_amplitude(amplitude_mv)
                ds5.trigger()
                pulse_count += 1
                log_writer.writerow([pulse_count, amplitude_mv,
                                     pulse_width_ms, int(simulation)])
                log_file.flush()
                print(f'    -> PULSE #{pulse_count}: {amplitude_mv} mV, '
                      f'{pulse_width_ms} ms')

            elif user_input in ('+', 'u'):
                amplitude_mv += step_mv
                ds5.set_amplitude(amplitude_mv)
                print(f'    amplitude -> {amplitude_mv} mV')

            elif user_input in ('-', 'd'):
                amplitude_mv = max(0, amplitude_mv - step_mv)
                ds5.set_amplitude(amplitude_mv)
                print(f'    amplitude -> {amplitude_mv} mV')

            elif user_input.startswith('s '):
                try:
                    step_mv = float(user_input[2:])
                    print(f'    step -> {step_mv} mV')
                except ValueError:
                    print('    invalid step value')

            elif user_input.startswith('w '):
                try:
                    pulse_width_ms = float(user_input[2:])
                    ds5.set_pulse_width(pulse_width_ms)
                    print(f'    pulse width -> {pulse_width_ms} ms')
                except ValueError:
                    print('    invalid pulse width')

            else:
                try:
                    amplitude_mv = float(user_input)
                    ds5.set_amplitude(amplitude_mv)
                    print(f'    amplitude -> {amplitude_mv} mV')
                except ValueError:
                    print('    unknown command (Enter=pulse, +/-=adjust, '
                          'number=set, q=quit)')

    except KeyboardInterrupt:
        print('\n    interrupted')

    finally:
        ds5.close()
        log_file.close()

    print(f'\n  {pulse_count} pulses delivered.')
    print(f'  Log saved: {log_path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Interactive DS5 single-pulse testing')
    parser.add_argument('--port', default='/dev/ttyUSB0',
                        help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('--sim', action='store_true',
                        help='Simulation mode (no hardware)')
    parser.add_argument('--pw', type=float, default=0.5,
                        help='Pulse width in ms (default: 0.5)')
    parser.add_argument('--start', type=float, default=100,
                        help='Starting amplitude in mV (default: 100)')
    parser.add_argument('--step', type=float, default=50,
                        help='Amplitude step size in mV (default: 50)')
    args = parser.parse_args()

    run_test(port=args.port,
             simulation=args.sim,
             pulse_width_ms=args.pw,
             start_mv=args.start,
             step_mv=args.step)
