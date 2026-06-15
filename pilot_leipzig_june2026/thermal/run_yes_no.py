"""
Yes/No thermal detection thresholding (CDT, WDT, HPT).

Adaptive 1-up/1-down staircase: delivers a brief 2s thermal stimulus,
participant reports "Yes I felt it" or "No I didn't" via arrow keys.
Step size halves after the first reversal for finer convergence.

Runs CDT, WDT, HPT sequentially. Saves results + threshold estimates.

Usage:
    python run_yes_no.py                # with PsychoPy display
    python run_yes_no.py --no-display   # console only (for testing)
"""

import argparse
import csv
import json
import math
import os
import sys
import time
from datetime import datetime

from config_thermal_L01 import CONFIG
from thermode import ThermodeController


def run_yes_no_modality(modality, config, thermode, use_display=True):
    """Run one Yes/No staircase for a single modality.

    Parameters
    ----------
    modality : str
        'CDT', 'WDT', or 'HPT'
    config : dict
    thermode : ThermodeController
    use_display : bool

    Returns
    -------
    dict with threshold estimate and trial data
    """
    baseline = config['baseline_temp']
    n_trials = config['yn_n_trials']
    stim_dur = config['yn_stim_duration']
    iti = config['yn_iti']
    timeout = config['yn_timeout']
    step_large = config['yn_step_large']
    step_small = config['yn_step_small']
    ramp_rate = config['yn_ramp_rate']
    return_rate = config['yn_return_rate']

    if modality == 'CDT':
        start_delta = config['yn_cdt_start_delta']
        direction = -1  # cooling
        question = 'Did you feel COOLING?'
        floor = config['temp_min']
        ceiling = baseline
    elif modality == 'WDT':
        start_delta = config['yn_wdt_start_delta']
        direction = +1  # warming
        question = 'Did you feel WARMING?'
        floor = baseline
        ceiling = config['temp_max']
    elif modality == 'HPT':
        start_delta = config['yn_hpt_start_delta']
        direction = +1  # warming (pain)
        question = 'Did you feel PAIN (burning/stinging)?'
        floor = baseline
        ceiling = config['temp_max']
    else:
        raise ValueError(f'Unknown modality: {modality}')

    # PsychoPy setup
    win = None
    if use_display:
        from psychopy import visual, core, event
        win = visual.Window(
            size=[800, 600], units='height',
            fullscr=config['fullscreen'],
            screen=config['screen_index'],
            color=[0, 0, 0])
        fix = visual.TextStim(win, text='+', height=0.1, color='white')
        prompt = visual.TextStim(win, text='', height=0.05, color='white',
                                 pos=(0, 0), wrapWidth=1.5)
        info = visual.TextStim(win, text='', height=0.03, color='grey',
                               pos=(0, -0.35))

    print(f'\n--- Yes/No {modality} ---')
    print(f'  {n_trials} trials, starting delta = {start_delta}°C')

    # Configure TCS for brief stimuli
    if not config['simulation']:
        thermode.device.set_durations([stim_dur] * 5)
        thermode.device.set_ramp_speed([ramp_rate] * 5)
        thermode.device.set_return_speed([return_rate] * 5)

    # Staircase state
    delta = start_delta
    step = step_large
    n_reversals = 0
    prev_response = None
    reversal_deltas = []
    trials = []

    for trial_idx in range(n_trials):
        # Compute target temperature
        target_temp = baseline + direction * delta
        target_temp = max(floor, min(ceiling, target_temp))

        # Show fixation
        if win:
            fix.draw()
            info.text = (f'{modality} trial {trial_idx + 1}/{n_trials}  '
                         f'delta={delta:.1f}°C')
            info.draw()
            win.flip()
        print(f'  Trial {trial_idx + 1}: delta={delta:.1f}°C  '
              f'target={target_temp:.1f}°C', end='')

        # Brief pause before stimulus
        _wait(0.5, win)

        # Deliver stimulus
        thermode.set_temperatures([target_temp] * 5)
        _wait(stim_dur, win)
        thermode.set_baseline()

        # Show question and collect response
        if win:
            prompt.text = f'{question}\n\nLeft arrow = YES    Right arrow = NO'
            prompt.draw()
            win.flip()
            event.clearEvents()

            response = None
            rt = None
            t0 = time.monotonic()
            while time.monotonic() - t0 < timeout:
                keys = event.getKeys(keyList=['left', 'right', 'escape'],
                                     timeStamped=True)
                for key, timestamp in keys:
                    if key == 'escape':
                        if win:
                            win.close()
                        raise KeyboardInterrupt('Escape pressed')
                    if key == 'left':
                        response = True  # Yes
                        rt = time.monotonic() - t0
                    elif key == 'right':
                        response = False  # No
                        rt = time.monotonic() - t0
                if response is not None:
                    break
        else:
            # Console mode
            try:
                ans = input('  [y/n]? ').strip().lower()
                response = ans in ('y', 'yes', '1')
                rt = None
            except EOFError:
                response = False
                rt = None

        if response is None:
            print('  -> TIMEOUT (no response)')
            response = False
            rt = timeout

        detected = response
        print(f'  -> {"YES" if detected else "NO"}')

        # Record trial
        trials.append({
            'trial': trial_idx + 1,
            'modality': modality,
            'delta': delta,
            'target_temp': target_temp,
            'detected': int(detected),
            'rt': rt if rt is not None else math.nan,
        })

        # Update staircase (1-up/1-down)
        if detected:
            new_delta = delta - step  # harder (less intense)
        else:
            new_delta = delta + step  # easier (more intense)

        # Check for reversal
        if prev_response is not None and detected != prev_response:
            n_reversals += 1
            reversal_deltas.append(delta)
            if n_reversals == 1:
                step = step_small  # switch to fine step
        prev_response = detected

        # Clamp delta
        delta = max(0.1, new_delta)

        # ITI
        _wait(iti, win)

    if win:
        win.close()

    # Compute threshold: mean of last 6 reversal deltas (or all if fewer)
    if reversal_deltas:
        use_reversals = reversal_deltas[-6:]
        threshold_delta = sum(use_reversals) / len(use_reversals)
    else:
        threshold_delta = delta
    threshold_temp = baseline + direction * threshold_delta

    print(f'\n  {modality} threshold: delta = {threshold_delta:.2f}°C  '
          f'({threshold_temp:.2f}°C)')
    print(f'  Reversals: {n_reversals}')

    return {
        'modality': modality,
        'threshold_delta': threshold_delta,
        'threshold_temp': threshold_temp,
        'n_reversals': n_reversals,
        'reversal_deltas': reversal_deltas,
        'trials': trials,
    }


def _wait(duration, win=None):
    """Wait using PsychoPy core.wait if available, else time.sleep."""
    if win is not None:
        from psychopy import core
        core.wait(duration)
    else:
        time.sleep(duration)


def main():
    parser = argparse.ArgumentParser(description='Yes/No thermal thresholding')
    parser.add_argument('--no-display', action='store_true',
                        help='Console mode (no PsychoPy window)')
    parser.add_argument('--modality', choices=['CDT', 'WDT', 'HPT'],
                        help='Run a single modality instead of all three')
    args = parser.parse_args()

    config = dict(CONFIG)
    use_display = not args.no_display

    # Output setup
    timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)

    thermode = ThermodeController(config)
    thermode.set_baseline()

    modalities = [args.modality] if args.modality else ['CDT', 'WDT', 'HPT']
    all_results = {}

    try:
        for mod in modalities:
            result = run_yes_no_modality(mod, config, thermode,
                                         use_display=use_display)
            all_results[mod] = result

            # Save per-modality trial data
            trial_path = os.path.join(data_dir,
                                      f'yn_{mod.lower()}_{timestamp}.tsv')
            with open(trial_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, delimiter='\t',
                                        fieldnames=result['trials'][0].keys())
                writer.writeheader()
                writer.writerows(result['trials'])
            print(f'  Saved: {trial_path}')

    except KeyboardInterrupt:
        print('\n  Aborted.')
    finally:
        thermode.close()

    # Save summary
    summary_path = os.path.join(data_dir, f'yn_summary_{timestamp}.json')
    summary = {
        'timestamp': timestamp,
        'config': config,
    }
    for mod, result in all_results.items():
        summary[mod] = {
            'threshold_delta': result['threshold_delta'],
            'threshold_temp': result['threshold_temp'],
            'n_reversals': result['n_reversals'],
            'reversal_deltas': result['reversal_deltas'],
        }
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f'\nSummary saved: {summary_path}')

    # Print final thresholds
    print('\n' + '=' * 50)
    print('  THRESHOLDS')
    for mod, result in all_results.items():
        print(f'  {mod}: delta = {result["threshold_delta"]:.2f}°C  '
              f'({result["threshold_temp"]:.2f}°C)')
    print('=' * 50)


if __name__ == '__main__':
    main()
