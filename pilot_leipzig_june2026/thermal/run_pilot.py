"""
Leipzig pilot session launcher — thermal modality.

Runs all thermal tasks in sequence:
    1. Yes/No thresholding (CDT, WDT, HPT)
    2. Method of Limits (CDT, WDT at 2.5°C/s)
    3. Test waveform (3 cycles with chosen delta)

Usage:
    python run_pilot.py                # full session with PsychoPy
    python run_pilot.py --no-display   # console mode
    python run_pilot.py --step 2       # start from step 2 (Method of Limits)
    python run_pilot.py --step 3 --delta 12.0  # just test waveform at 12°C delta
"""

import argparse
import json
import os
import sys
from datetime import datetime

from config_thermal_L01 import CONFIG


def main():
    parser = argparse.ArgumentParser(
        description='Leipzig pilot session — thermal')
    parser.add_argument('--no-display', action='store_true',
                        help='Console mode (no PsychoPy)')
    parser.add_argument('--step', type=int, default=1, choices=[1, 2, 3],
                        help='Start from step (1=YesNo, 2=MLi, 3=Waveform)')
    parser.add_argument('--delta', type=float, default=None,
                        help='Override waveform delta (°C) for step 3')
    args = parser.parse_args()

    display_flag = ['--no-display'] if args.no_display else []

    print('=' * 60)
    print('  LEIPZIG PILOT SESSION — THERMAL')
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'  Simulation: {CONFIG["simulation"]}')
    print(f'  Starting from step {args.step}')
    print('=' * 60)

    # --- Step 1: Yes/No thresholding ---
    if args.step <= 1:
        print('\n\n' + '#' * 60)
        print('  STEP 1: Yes/No Thresholding (CDT, WDT, HPT)')
        print('#' * 60)
        input('\n  Press Enter to start Yes/No thresholding...')

        from run_yes_no import main as yn_main
        sys.argv = ['run_yes_no.py'] + display_flag
        yn_main()

    # --- Step 2: Method of Limits ---
    if args.step <= 2:
        print('\n\n' + '#' * 60)
        print('  STEP 2: Method of Limits (CDT, WDT at 2.5°C/s)')
        print('#' * 60)
        input('\n  Press Enter to start Method of Limits...')

        from run_method_of_limits import main as mli_main
        sys.argv = ['run_method_of_limits.py'] + display_flag
        mli_main()

    # --- Step 3: Test waveform ---
    print('\n\n' + '#' * 60)
    print('  STEP 3: Test Waveform')
    print('#' * 60)

    if args.delta:
        delta = args.delta
    else:
        # Try to read delta from previous thresholds
        delta = CONFIG['waveform_max_delta']
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'data')
        yn_summaries = sorted(
            [f for f in os.listdir(data_dir) if f.startswith('yn_summary_')]
        ) if os.path.isdir(data_dir) else []

        if yn_summaries:
            latest = os.path.join(data_dir, yn_summaries[-1])
            with open(latest) as f:
                yn_data = json.load(f)
            # Use the smallest detection threshold as max_delta
            deltas = []
            for mod in ['CDT', 'WDT']:
                if mod in yn_data and 'threshold_delta' in yn_data[mod]:
                    deltas.append(yn_data[mod]['threshold_delta'])
            if deltas:
                suggested = min(deltas)
                print(f'\n  YN thresholds found: {deltas}')
                print(f'  Suggested max_delta: {suggested:.1f}°C')
                print(f'  Default max_delta: {delta:.1f}°C')

        user_delta = input(f'\n  Enter max_delta (°C) or press Enter for '
                          f'{delta:.1f}: ').strip()
        if user_delta:
            try:
                delta = float(user_delta)
            except ValueError:
                print(f'  Invalid input, using {delta:.1f}°C')

    print(f'\n  Running test waveform with delta = ±{delta:.1f}°C')
    input('  Press Enter to start...')

    from run_test_waveform import main as wf_main
    sys.argv = ['run_test_waveform.py', '--delta', str(delta)] + display_flag
    wf_main()

    print('\n' + '=' * 60)
    print('  THERMAL PILOT SESSION COMPLETE')
    print('=' * 60)


if __name__ == '__main__':
    main()
