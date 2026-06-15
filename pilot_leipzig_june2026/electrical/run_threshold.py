"""
Electrical detection and pain threshold estimation.

Ascending Method of Limits: starts at a low amplitude, delivers single
pulses with increasing intensity. The participant reports:
    1. When they first FEEL the pulse (detection threshold, EDT)
    2. When it becomes PAINFUL (pain threshold, EPT)

Repeated 3 times (configurable). Thresholds are the mean across runs.

Usage:
    python run_threshold.py                # with PsychoPy display
    python run_threshold.py --no-display   # console only
    python run_threshold.py --sim          # simulation mode
"""

import argparse
import csv
import json
import math
import os
import time
from datetime import datetime

from config_electric_L01 import CONFIG
from ds5_controller import DS5Controller


def run_ascending_series(run_idx, config, ds5, use_display=True):
    """Run one ascending series to find EDT and EPT.

    Returns
    -------
    dict with 'edt_mv', 'ept_mv', and 'trials' list
    """
    start = config['thresh_start_mv']
    step = config['thresh_step_mv']
    step_fine = config['thresh_step_fine_mv']
    iti = config['thresh_iti']
    ceiling = config['thresh_max_mv']
    pw = config['pulse_width_ms']

    # PsychoPy
    win = None
    if use_display:
        from psychopy import visual, core, event
        win = visual.Window(
            size=[800, 600], units='height', fullscr=False,
            screen=0, color=[0, 0, 0])
        fix = visual.TextStim(win, text='+', height=0.1, color='white')
        prompt = visual.TextStim(win, text='', height=0.05, color='white',
                                 wrapWidth=1.5)
        info = visual.TextStim(win, text='', height=0.03, color='grey',
                               pos=(0, -0.35))

    print(f'\n  --- Run {run_idx + 1} ---')

    amplitude = start
    current_step = step
    edt_mv = None
    ept_mv = None
    trials = []
    trial_num = 0

    while amplitude <= ceiling:
        trial_num += 1

        # Show fixation before pulse
        if win:
            fix.draw()
            info.text = f'Run {run_idx + 1}  |  {amplitude} mV  |  trial {trial_num}'
            info.draw()
            win.flip()
        _wait(0.5, win)

        # Deliver pulse
        ds5.set_amplitude(amplitude)
        ds5.trigger()

        print(f'    trial {trial_num}: {amplitude} mV', end='', flush=True)

        # Collect response
        if edt_mv is None:
            question = 'Did you FEEL the pulse?\n\nLeft = YES    Right = NO'
            response_type = 'detection'
        else:
            question = 'Was it PAINFUL?\n\nLeft = YES    Right = NO'
            response_type = 'pain'

        response = _collect_response(question, win, prompt, use_display)

        if response is None:
            # Escape pressed
            if win:
                win.close()
            raise KeyboardInterrupt('Escape pressed')

        print(f'  -> {"YES" if response else "NO"} ({response_type})')

        trials.append({
            'run': run_idx + 1,
            'trial': trial_num,
            'amplitude_mv': amplitude,
            'pulse_width_ms': pw,
            'question': response_type,
            'response': int(response),
        })

        if response:
            if edt_mv is None:
                # First detection — record EDT
                edt_mv = amplitude
                print(f'    ** EDT = {edt_mv} mV **')
                # Switch to fine steps for pain threshold
                current_step = step_fine
            else:
                # Pain detected — record EPT, end this run
                ept_mv = amplitude
                print(f'    ** EPT = {ept_mv} mV **')
                break

        # Increase amplitude
        amplitude += current_step

        # ITI
        _wait(iti, win)

    if amplitude > ceiling and ept_mv is None:
        print(f'    Reached ceiling ({ceiling} mV) without pain threshold')

    if win:
        win.close()

    return {
        'edt_mv': edt_mv if edt_mv is not None else math.nan,
        'ept_mv': ept_mv if ept_mv is not None else math.nan,
        'trials': trials,
    }


def _collect_response(question, win, prompt_stim, use_display):
    """Collect a yes (left) / no (right) response. Returns True/False or None for escape."""
    if use_display and win is not None:
        from psychopy import event
        prompt_stim.text = question
        prompt_stim.draw()
        win.flip()
        event.clearEvents()

        while True:
            keys = event.getKeys(keyList=['left', 'right', 'escape'])
            for key in keys:
                if key == 'escape':
                    return None
                if key == 'left':
                    return True
                if key == 'right':
                    return False
    else:
        try:
            ans = input('    [y/n]? ').strip().lower()
            if ans in ('q', 'escape'):
                return None
            return ans in ('y', 'yes', '1', 'left')
        except EOFError:
            return False


def _wait(duration, win=None):
    if win is not None:
        from psychopy import core
        core.wait(duration)
    else:
        time.sleep(duration)


def main():
    parser = argparse.ArgumentParser(
        description='Electrical detection and pain threshold estimation')
    parser.add_argument('--no-display', action='store_true',
                        help='Console mode (no PsychoPy)')
    parser.add_argument('--sim', action='store_true', default=None,
                        help='Override simulation mode')
    args = parser.parse_args()

    config = dict(CONFIG)
    if args.sim is not None:
        config['simulation'] = args.sim
    use_display = not args.no_display

    timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)

    n_runs = config['thresh_n_runs']
    mode = 'SIM' if config['simulation'] else config['com_port']

    print(f'\n{"=" * 55}')
    print(f'  Electrical Threshold Estimation — {mode}')
    print(f'  Pulse width: {config["pulse_width_ms"]} ms')
    print(f'  Start: {config["thresh_start_mv"]} mV, '
          f'step: {config["thresh_step_mv"]} mV '
          f'(fine: {config["thresh_step_fine_mv"]} mV)')
    print(f'  {n_runs} ascending runs')
    print(f'  DS5 range: {config["ds5_range_note"]}')
    print(f'{"=" * 55}\n')

    ds5 = DS5Controller(port=config['com_port'],
                        simulation=config['simulation'])
    ds5.set_pulse_width(config['pulse_width_ms'])

    all_trials = []
    run_results = []

    try:
        for run_idx in range(n_runs):
            if run_idx > 0:
                input(f'\n  Press Enter to start run {run_idx + 1}/{n_runs}...')

            result = run_ascending_series(run_idx, config, ds5,
                                          use_display=use_display)
            run_results.append(result)
            all_trials.extend(result['trials'])

            print(f'  Run {run_idx + 1}: EDT = {result["edt_mv"]} mV, '
                  f'EPT = {result["ept_mv"]} mV')

    except KeyboardInterrupt:
        print('\n  Aborted.')
    finally:
        ds5.close()

    # Save trial data
    if all_trials:
        trial_path = os.path.join(data_dir, f'ethresh_{timestamp}.tsv')
        with open(trial_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, delimiter='\t',
                                    fieldnames=all_trials[0].keys())
            writer.writeheader()
            writer.writerows(all_trials)
        print(f'\nTrials saved: {trial_path}')

    # Compute mean thresholds
    edts = [r['edt_mv'] for r in run_results if not math.isnan(r['edt_mv'])]
    epts = [r['ept_mv'] for r in run_results if not math.isnan(r['ept_mv'])]

    mean_edt = sum(edts) / len(edts) if edts else math.nan
    mean_ept = sum(epts) / len(epts) if epts else math.nan

    print(f'\n{"=" * 55}')
    print(f'  ELECTRICAL THRESHOLDS')
    print(f'  Detection (EDT): {mean_edt:.1f} mV  '
          f'(runs: {[r["edt_mv"] for r in run_results]})')
    print(f'  Pain (EPT):      {mean_ept:.1f} mV  '
          f'(runs: {[r["ept_mv"] for r in run_results]})')
    print(f'{"=" * 55}')

    # Save summary
    summary = {
        'timestamp': timestamp,
        'config': config,
        'edt_mean_mv': mean_edt,
        'ept_mean_mv': mean_ept,
        'runs': [{'edt_mv': r['edt_mv'], 'ept_mv': r['ept_mv']}
                 for r in run_results],
    }
    summary_path = os.path.join(data_dir, f'ethresh_summary_{timestamp}.json')
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f'Summary saved: {summary_path}')


if __name__ == '__main__':
    main()
