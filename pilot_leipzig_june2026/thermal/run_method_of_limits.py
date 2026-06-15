"""
Method of Limits thermal thresholding (CDT, WDT).

Temperature ramps continuously from baseline at 2.5°C/s.
Participant presses a key the moment they detect the change.
The temperature at keypress is recorded as the threshold.

Runs CDT (cooling) then WDT (warming). 3 practice + 3 test trials each.

Usage:
    python run_method_of_limits.py                # with PsychoPy display
    python run_method_of_limits.py --no-display   # console only
"""

import argparse
import csv
import json
import math
import os
import time
from datetime import datetime

from config_thermal_L01 import CONFIG
from thermode import ThermodeController


def run_mli_modality(modality, config, thermode, phase, use_display=True):
    """Run Method of Limits trials for one modality.

    Parameters
    ----------
    modality : str
        'CDT' or 'WDT'
    config : dict
    thermode : ThermodeController
    phase : str
        'practice' or 'test'
    use_display : bool

    Returns
    -------
    list of trial dicts
    """
    baseline = config['baseline_temp']
    ramp_rate = config['mli_ramp_rate']  # 2.5 °C/s
    return_rate = config['mli_return_rate']
    update_hz = config['update_hz']
    dt = 1.0 / update_hz

    if phase == 'practice':
        n_trials = config['mli_trials_practice']
    else:
        n_trials = config['mli_trials_test']

    if modality == 'CDT':
        direction = -1
        floor = config['mli_cdt_floor']
        ceiling = baseline
        iti = config['mli_iti']
        label = 'cooling'
        instruction = 'Press UP ARROW as soon as you feel COOLING'
    elif modality == 'WDT':
        direction = +1
        floor = baseline
        ceiling = config['mli_wdt_ceiling']
        iti = config['mli_iti']
        label = 'warming'
        instruction = 'Press UP ARROW as soon as you feel WARMING'
    else:
        raise ValueError(f'Unknown modality: {modality}')

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
        msg = visual.TextStim(win, text='', height=0.05, color='white',
                              wrapWidth=1.5)
        info = visual.TextStim(win, text='', height=0.03, color='grey',
                               pos=(0, -0.35))
        fix = visual.TextStim(win, text='+', height=0.1, color='white')
        kb = keyboard.Keyboard()

    print(f'\n--- Method of Limits: {modality} ({phase}) ---')
    print(f'  {n_trials} trials, ramp = {ramp_rate}°C/s ({label})')

    # Configure TCS for follow mode (continuous ramp)
    if not config['simulation']:
        thermode.device.set_ramp_speed([ramp_rate] * 5)
        thermode.device.set_return_speed([return_rate] * 5)
        thermode.device.set_follow()

    trials = []

    for trial_idx in range(n_trials):
        # Show instruction
        if win:
            msg.text = instruction
            info.text = f'{modality} {phase} — trial {trial_idx + 1}/{n_trials}'
            msg.draw()
            info.draw()
            win.flip()
            _wait(2.0, win)
            # Clear keys
            kb.clearEvents()

        print(f'  Trial {trial_idx + 1}: ramping {label}...', end='', flush=True)

        # Start from baseline
        thermode.set_baseline()
        _wait(1.0, win)

        # Ramp until keypress or limit
        current_temp = baseline
        responded = False
        response_temp = math.nan
        t_start = time.monotonic()

        while True:
            # Update temperature
            current_temp += direction * ramp_rate * dt
            current_temp = max(floor, min(ceiling, current_temp))
            thermode.set_temperatures([current_temp] * 5)

            # Show fixation with temp info for experimenter
            if win:
                fix.draw()
                info.text = f'{current_temp:.1f}°C'
                info.draw()
                win.flip()

            # Check for keypress
            if win:
                keys = kb.getKeys(keyList=['up', 'escape'])
                if keys:
                    for key in keys:
                        if key.name == 'escape':
                            thermode.set_baseline()
                            if win:
                                win.close()
                            raise KeyboardInterrupt('Escape pressed')
                        if key.name == 'up':
                            responded = True
                            response_temp = current_temp
                            break
            else:
                # Console: check elapsed time, auto-respond after a bit for testing
                import select
                if select.select([sys.stdin], [], [], 0)[0]:
                    sys.stdin.readline()
                    responded = True
                    response_temp = current_temp

            if responded:
                break

            # Hit the temperature limit
            if (direction == -1 and current_temp <= floor) or \
               (direction == +1 and current_temp >= ceiling):
                response_temp = current_temp
                break

            _wait(dt, None)  # Use time.sleep for timing precision

        elapsed = time.monotonic() - t_start
        delta = abs(response_temp - baseline)

        print(f' {response_temp:.1f}°C (delta={delta:.1f}°C, '
              f't={elapsed:.1f}s, '
              f'{"responded" if responded else "LIMIT"})')

        # Return to baseline
        thermode.set_baseline()
        if win:
            msg.text = 'Returning to baseline...'
            msg.draw()
            win.flip()
        _wait(3.0, win)  # time to return

        trials.append({
            'trial': trial_idx + 1,
            'modality': modality,
            'phase': phase,
            'response_temp': response_temp,
            'delta': delta,
            'responded': int(responded),
            'elapsed_s': elapsed,
        })

        # ITI
        if win:
            fix.draw()
            win.flip()
        _wait(iti, win)

    if win:
        win.close()

    return trials


def _wait(duration, win=None):
    if win is not None:
        from psychopy import core
        core.wait(duration)
    else:
        time.sleep(duration)


def main():
    parser = argparse.ArgumentParser(
        description='Method of Limits thermal thresholding')
    parser.add_argument('--no-display', action='store_true',
                        help='Console mode (no PsychoPy window)')
    args = parser.parse_args()

    config = dict(CONFIG)
    use_display = not args.no_display

    timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)

    thermode = ThermodeController(config)
    thermode.set_baseline()

    all_trials = []

    try:
        for modality in ['CDT', 'WDT']:
            # Practice
            practice = run_mli_modality(modality, config, thermode,
                                        'practice', use_display)
            all_trials.extend(practice)

            print(f'  Practice done. Waiting 10s before test trials...')
            _wait(10.0, None)

            # Test
            test = run_mli_modality(modality, config, thermode,
                                    'test', use_display)
            all_trials.extend(test)

    except KeyboardInterrupt:
        print('\n  Aborted.')
    finally:
        thermode.close()

    # Save trial data
    if all_trials:
        trial_path = os.path.join(data_dir, f'mli_{timestamp}.tsv')
        with open(trial_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, delimiter='\t',
                                    fieldnames=all_trials[0].keys())
            writer.writeheader()
            writer.writerows(all_trials)
        print(f'\nTrials saved: {trial_path}')

    # Compute thresholds from test trials
    summary = {'timestamp': timestamp, 'config': config}
    print('\n' + '=' * 50)
    print('  METHOD OF LIMITS THRESHOLDS')
    for modality in ['CDT', 'WDT']:
        test_trials = [t for t in all_trials
                       if t['modality'] == modality and t['phase'] == 'test'
                       and t['responded']]
        if test_trials:
            mean_temp = sum(t['response_temp'] for t in test_trials) / len(test_trials)
            mean_delta = sum(t['delta'] for t in test_trials) / len(test_trials)
            print(f'  {modality}: mean = {mean_temp:.2f}°C  '
                  f'(delta = {mean_delta:.2f}°C, n={len(test_trials)})')
            summary[modality] = {
                'threshold_temp': mean_temp,
                'threshold_delta': mean_delta,
                'n_trials': len(test_trials),
            }
        else:
            print(f'  {modality}: no valid test responses')
    print('=' * 50)

    summary_path = os.path.join(data_dir, f'mli_summary_{timestamp}.json')
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f'Summary saved: {summary_path}')


if __name__ == '__main__':
    main()
