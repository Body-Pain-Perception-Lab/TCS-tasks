"""
Run a single block of the fMRI tprf thermode experiment.

Run this script once per block. The experimenter controls timing between
blocks (breaks, adjustments, etc.) by simply running the script again.

Each invocation:
    1. GUI step 1: enter participant ID and session
    2. GUI step 2: see block plan summary (which blocks are done),
       select which block to run
    3. Wait for scanner trigger
    4. Run one block (baseline + 8 cycles + baseline)
    5. Collect VAS ratings (if enabled)
    6. Save data and exit

Output (BIDS, per block):
    func/sub-XX_ses-XX_task-tprf_run-XX_events_<timestamp>.tsv
    func/sub-XX_ses-XX_task-tprf_run-XX_thermode_<timestamp>.tsv
    func/sub-XX_ses-XX_task-tprf_run-XX_thermode_<timestamp>.json
    func/sub-XX_ses-XX_task-tprf_run-XX_qc_<timestamp>.tsv

Usage:
    python run_experiment.py
"""

import os
import sys
import csv
import copy
import json
import glob as _glob
from datetime import datetime

from psychopy import visual, event, core, gui
from psychopy.hardware import keyboard

from config_v3 import CONFIG
from masks import get_mask
from thermode import ThermodeController
from run_block import run_block
from ratings import collect_vas_ratings


def get_block_plan(config):
    """Return the planned 8-block sequence based on config.

    Each unique run (condition x direction) is presented twice.
    NonTGI blocks first (runs 1-4), then TGI blocks (runs 5-8).

    Block order is determined by nontgi_warm_first:
        True  (Group A): W-first, C-first pairs
        False (Group B): C-first, W-first pairs
    """
    nontgi_mask = config['nontgi_mask']
    tgi_mask = config['tgi_mask']

    if config['nontgi_warm_first']:
        return [
            {'block_type': 'NonTGI', 'mask_name': nontgi_mask, 'warm_first': True},
            {'block_type': 'NonTGI', 'mask_name': nontgi_mask, 'warm_first': False},
            {'block_type': 'NonTGI', 'mask_name': nontgi_mask, 'warm_first': True},
            {'block_type': 'NonTGI', 'mask_name': nontgi_mask, 'warm_first': False},
            {'block_type': 'TGI',    'mask_name': tgi_mask,    'warm_first': True},
            {'block_type': 'TGI',    'mask_name': tgi_mask,    'warm_first': False},
            {'block_type': 'TGI',    'mask_name': tgi_mask,    'warm_first': True},
            {'block_type': 'TGI',    'mask_name': tgi_mask,    'warm_first': False},
        ]
    else:
        return [
            {'block_type': 'NonTGI', 'mask_name': nontgi_mask, 'warm_first': False},
            {'block_type': 'NonTGI', 'mask_name': nontgi_mask, 'warm_first': True},
            {'block_type': 'NonTGI', 'mask_name': nontgi_mask, 'warm_first': False},
            {'block_type': 'NonTGI', 'mask_name': nontgi_mask, 'warm_first': True},
            {'block_type': 'TGI',    'mask_name': tgi_mask,    'warm_first': False},
            {'block_type': 'TGI',    'mask_name': tgi_mask,    'warm_first': True},
            {'block_type': 'TGI',    'mask_name': tgi_mask,    'warm_first': False},
            {'block_type': 'TGI',    'mask_name': tgi_mask,    'warm_first': True},
        ]


def scan_completed_runs(participant_id, session):
    """Check which runs already have data files for this participant/session.

    Returns dict mapping run number (e.g. '01') to the JSON sidecar contents.
    """
    base_dir = os.path.join(os.path.dirname(__file__) or '.', 'data',
                            f'sub-{participant_id}',
                            f'ses-{session}',
                            'func')
    completed = {}
    if not os.path.exists(base_dir):
        return completed

    json_files = _glob.glob(os.path.join(base_dir, '*_thermode_*.json'))
    for jf in json_files:
        fname = os.path.basename(jf)
        run_num = None
        for part in fname.split('_'):
            if part.startswith('run-'):
                run_num = part[4:]
                break
        if run_num:
            with open(jf, 'r') as f:
                sidecar = json.load(f)
            completed[run_num] = sidecar

    return completed


def get_session_info(config):
    """Two-step GUI for block selection with visual plan summary.

    Step 1: Participant ID and session number.
    Step 2: Block plan summary showing DONE/pending status for all 8 blocks,
            plus a dropdown to select which block to run next.
    """
    # --- Compute run timing for display ---
    import math
    dummy_s = config['dummy_volumes'] * config['TR']
    stim_s = config['cycles_per_block'] * config['cycle_duration']
    total_s = dummy_s + config['baseline_buffer'] + stim_s + config['baseline_buffer']
    n_volumes = int(math.ceil(total_s / config['TR']))
    run_min = int(total_s // 60)
    run_sec = int(total_s % 60)

    # --- Step 1: Participant and session ---
    dlg1 = gui.Dlg(title='fMRI Triangular Wave v2 — Participant')
    dlg1.addField('Participant ID:', '0001')
    dlg1.addField('Session:', '01')
    data1 = dlg1.show()
    if not dlg1.OK:
        print('User cancelled.')
        sys.exit(0)

    participant_id = data1[0]
    session = data1[1]

    # --- Scan for completed blocks ---
    completed = scan_completed_runs(participant_id, session)
    block_plan = get_block_plan(config)

    # Build summary text and find next pending block
    summary_lines = [
        f'--- Block Plan (8 runs) ---',
        f'Per run: {n_volumes} volumes, {run_min}m {run_sec}s '
        f'({config["cycles_per_block"]} cycles x {config["cycle_duration"]:.0f}s, '
        f'{config["baseline_buffer"]:.0f}s baseline)',
        '',
    ]
    next_block_idx = None
    for i, block in enumerate(block_plan):
        run_num = f'{i + 1:02d}'
        direction = 'W-first' if block['warm_first'] else 'C-first'
        label = f"{block['block_type']}  {block['mask_name']}  {direction}"
        if run_num in completed:
            summary_lines.append(f"  Run {i + 1} (run-{run_num}): {label}  [DONE]")
        else:
            summary_lines.append(f"  Run {i + 1} (run-{run_num}): {label}  [--]")
            if next_block_idx is None:
                next_block_idx = i

    if next_block_idx is None:
        next_block_idx = 0  # all blocks done; default to first

    n_done = len(completed)
    summary_lines.append(f'\n  {n_done}/{len(block_plan)} runs completed')

    summary = '\n'.join(summary_lines)

    # Block choices — next pending block shown first in dropdown
    all_choices = [f'Run {i + 1}' for i in range(len(block_plan))]
    choices = ([all_choices[next_block_idx]]
               + [c for j, c in enumerate(all_choices) if j != next_block_idx])

    # --- Step 2: Block selection with summary ---
    dlg2 = gui.Dlg(title='fMRI Triangular Wave v2 — Run Block')
    dlg2.addText(summary)
    dlg2.addField('Run:', choices=choices)
    dlg2.addField('Max delta (°C):', config['max_delta'])
    dlg2.addField('COM Port:', config['com_port'])
    dlg2.addField('Simulation:', config['simulation'])
    dlg2.addField('Emulate scanner:', config['emulate'])
    dlg2.addField('Fullscreen:', config['fullscreen'])
    data2 = dlg2.show()
    if not dlg2.OK:
        print('User cancelled.')
        sys.exit(0)

    # Parse run selection (e.g. 'Run 2' -> index 1)
    selected = data2[0]
    block_num = int(selected.split(' ')[1])
    block_idx = block_num - 1
    selected_block = block_plan[block_idx]
    run_num = f'{block_num:02d}'

    if run_num in completed:
        print(f'NOTE: Run {block_num} (run-{run_num}) was already run. '
              f'Data will be saved with a new timestamp (not overwritten).')

    return {
        'participant_id': participant_id,
        'session': session,
        'run': run_num,
        'block_type': selected_block['block_type'],
        'mask_name': selected_block['mask_name'],
        'warm_first': selected_block['warm_first'],
        'max_delta': float(data2[1]),
        'com_port': data2[2],
        'simulation': data2[3],
        'emulate': data2[4],
        'fullscreen': data2[5],
    }


def create_output_paths(info):
    """Create BIDS output directory and return file paths for one block."""
    base_dir = os.path.join(os.path.dirname(__file__) or '.', 'data',
                            f'sub-{info["participant_id"]}',
                            f'ses-{info["session"]}',
                            'func')
    os.makedirs(base_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
    prefix = (f'sub-{info["participant_id"]}_ses-{info["session"]}'
              f'_task-tprf_run-{info["run"]}')

    paths = {
        'events': os.path.join(
            base_dir, f'{prefix}_events_{timestamp}.tsv'),
        'thermode': os.path.join(
            base_dir, f'{prefix}_thermode_{timestamp}.tsv'),
        'thermode_json': os.path.join(
            base_dir, f'{prefix}_thermode_{timestamp}.json'),
        'qc': os.path.join(
            base_dir, f'{prefix}_qc_{timestamp}.tsv'),
    }
    return paths


def _get_config_source():
    """Return the module name that CONFIG was imported from."""
    # Walk the import that brought CONFIG into this module
    import sys
    for name, mod in sys.modules.items():
        if name == __name__ or mod is None:
            continue
        if hasattr(mod, 'CONFIG') and mod.CONFIG is CONFIG:
            # Return the filename (e.g. 'config_v2.py'), not full path
            src = getattr(mod, '__file__', None)
            if src:
                return os.path.basename(src)
            return name
    return 'unknown'


def write_thermode_json(path, config, info):
    """Write JSON sidecar for the thermode recording."""
    sidecar = {
        'SamplingFrequency': config['update_hz'],
        'StartTime': 0.0,
        'Columns': [
            'onset', 'volume', 'block_index', 'block_type', 'cycle_index',
            'mask_name', 'warm_first', 'delta',
            'zone1_set', 'zone2_set', 'zone3_set', 'zone4_set', 'zone5_set',
            'zone1_actual', 'zone2_actual', 'zone3_actual', 'zone4_actual',
            'zone5_actual',
        ],
        'block_type': info['block_type'],
        'mask_name': info['mask_name'],
        'warm_first': info['warm_first'],
        'baseline_temp': config['baseline_temp'],
        'max_delta': config['max_delta'],
        'cycle_duration': config['cycle_duration'],
        'cycles_per_block': config['cycles_per_block'],
        'ramp_rate': config['ramp_rate'],
        'TR': config['TR'],
        'config_source': _get_config_source(),
        'config': config,
    }
    with open(path, 'w') as f:
        json.dump(sidecar, f, indent=2)


def wait_for_trigger(config, global_clock, win):
    """Wait for scanner trigger or space bar, return trigger time.

    Supports two trigger modes (set via config['trigger_mode']):
        'keyboard'  — PsychoPy keyboard listener (default). Detects a key
                       press even when the window doesn't have focus.
        'parallel'  — Parallel port falling edge on the Acknowledge pin.
                       Used at Leipzig 7T (parallel module required).

    In emulation mode, always uses space bar regardless of trigger_mode.
    """
    if config['emulate']:
        kb = keyboard.Keyboard()
        print('Press space to start...')
        kb.waitKeys(keyList=['space'])

    elif config.get('trigger_mode', 'keyboard') == 'parallel':
        import parallel
        p_sc = parallel.Parallel(port=config.get('parallel_port', 0))
        p_sc.setDataDir(0)
        p_sc.setData(0)
        print('Waiting for scanner trigger (parallel port)...')
        while p_sc.getInAcknowledge():
            pass  # spin until falling edge

    else:
        kb = keyboard.Keyboard()
        print(f'Waiting for scanner trigger (key={config["trigger_key"]!r})...')
        kb.waitKeys(keyList=[config['trigger_key']])

    trigger_time = global_clock.getTime()
    print(f'Trigger received at {trigger_time:.4f}s')

    dummy_wait = config['TR'] * config['dummy_volumes']
    print(f'Waiting {dummy_wait:.1f}s for {config["dummy_volumes"]} dummy volumes...')

    # Show on-screen confirmation during dummy volume wait
    wait_msg = visual.TextStim(
        win,
        text=f'Trigger received.\nWaiting for dummy volumes ({dummy_wait:.0f}s)...',
        pos=(0, 0), height=0.05, color='white')
    wait_msg.draw()
    win.flip()
    core.wait(dummy_wait)

    return trigger_time


def main():
    config = copy.deepcopy(CONFIG)
    info = get_session_info(config)

    # Apply GUI selections to config
    config['max_delta'] = info['max_delta']
    config['com_port'] = info['com_port']
    config['simulation'] = info['simulation']
    config['emulate'] = info['emulate']
    config['fullscreen'] = info['fullscreen']

    # Resolve block parameters
    block_type = info['block_type']
    mask_name = info['mask_name']
    mask_array = get_mask(mask_name)
    warm_first = info['warm_first']
    direction = 'warm-first' if warm_first else 'cool-first'

    print(f'\n=== Block {info["run"]}: {block_type} | {mask_name} | {direction} ===\n')

    # Create BIDS output paths
    paths = create_output_paths(info)
    print(f'Events:   {paths["events"]}')
    print(f'Thermode: {paths["thermode"]}')
    print(f'QC:       {paths["qc"]}')

    # Write thermode JSON sidecar
    write_thermode_json(paths['thermode_json'], config, info)

    # Open events TSV (BIDS: header required)
    events_file = open(paths['events'], 'w', newline='')
    events_writer = csv.writer(events_file, delimiter='\t')
    events_writer.writerow([
        'onset', 'duration', 'trial_type',
        'block_type', 'mask_name', 'warm_first',
        'response_value', 'response_time',
    ])

    # Open thermode TSV (no header, columns in JSON sidecar)
    thermode_file = open(paths['thermode'], 'w', newline='')
    thermode_writer = csv.writer(thermode_file, delimiter='\t')

    # Open QC TSV
    qc_file = open(paths['qc'], 'w', newline='')
    qc_writer = csv.writer(qc_file, delimiter='\t')
    qc_writer.writerow([
        'block_type', 'mask_name', 'warm_first',
        'cycle_index', 'onset_latency_s',
        'mean_ramp_rate', 'std_ramp_rate',
        'mean_warming_rate', 'mean_cooling_rate', 'warming_cooling_diff',
        'mean_temp_error', 'max_temp_error', 'n_ramp_flags',
        'overheat_flagged', 'n_samples',
    ])

    # Initialize thermode
    thermode = ThermodeController(config)
    thermode.set_baseline()

    # Create PsychoPy window
    win = visual.Window(
        size=[800, 600],
        units='height',
        fullscr=config['fullscreen'],
        color=[0, 0, 0],
        screen=config['screen_index'],
    )

    wait_msg = visual.TextStim(win, text='Waiting for scanner trigger...\n'
                               '(Press space in emulation mode)',
                               pos=(0, 0), height=0.05, color='white')
    wait_msg.draw()
    win.flip()

    # Global clock and trigger
    global_clock = core.Clock()
    trigger_time = wait_for_trigger(config, global_clock, win)

    # Run single block
    try:
        block_result = run_block(
            block_idx=0,
            block_type=block_type,
            mask_name=mask_name,
            mask_array=mask_array,
            warm_first=warm_first,
            n_blocks=1,
            thermode=thermode,
            win=win,
            global_clock=global_clock,
            trigger_time=trigger_time,
            physio_writer=thermode_writer,
            config=config,
            physio_file=thermode_file,
        )
        thermode_file.flush()

        # Write QC summaries
        for s in block_result['qc_summaries']:
            qc_writer.writerow([
                block_type,
                mask_name,
                int(warm_first),
                s['cycle_index'],
                f'{s["onset_latency_s"]:.4f}',
                f'{s["mean_ramp_rate"]:.4f}',
                f'{s["std_ramp_rate"]:.4f}',
                f'{s["mean_warming_rate"]:.4f}',
                f'{s["mean_cooling_rate"]:.4f}',
                f'{s["warming_cooling_diff"]:.4f}',
                f'{s["mean_temp_error"]:.4f}',
                f'{s["max_temp_error"]:.4f}',
                s['n_ramp_flags'],
                int(s.get('overheat_flagged', False)),
                s['n_samples'],
            ])
        qc_file.flush()

        # Write block phase events
        for phase in block_result['timings']:
            events_writer.writerow([
                f'{phase["onset"]:.4f}',
                f'{phase["duration"]:.4f}',
                phase['trial_type'],
                block_type,
                mask_name,
                int(warm_first),
                'n/a',
                'n/a',
            ])

        # VAS ratings
        if config['vas_enabled']:
            print('  Collecting VAS ratings...')
            vas_results = collect_vas_ratings(
                win, global_clock, trigger_time, config)
            for r in vas_results:
                rt = r['rt']
                is_valid = rt == rt  # NaN check
                events_writer.writerow([
                    f'{r["onset_from_trigger_s"]:.4f}',
                    f'{rt:.4f}' if is_valid else 'n/a',
                    f'rating_{r["question"]}',
                    block_type,
                    mask_name,
                    int(warm_first),
                    r['rating'] if is_valid else 'n/a',
                    f'{rt:.4f}' if is_valid else 'n/a',
                ])
            events_file.flush()
            print('  Ratings: ' + ', '.join(
                f'{r["question"]}={r["rating"]}' for r in vas_results))

        # Done
        end_msg = visual.TextStim(win, text='Block complete.\nThank you!',
                                  pos=(0, 0), height=0.06, color='white')
        end_msg.draw()
        win.flip()
        core.wait(3.0)

    except KeyboardInterrupt:
        print('\nBlock aborted by user.')

    finally:
        thermode.set_baseline()
        thermode.close()
        events_file.close()
        thermode_file.close()
        qc_file.close()
        win.close()
        print(f'\nEvents:   {paths["events"]}')
        print(f'Thermode: {paths["thermode"]}')
        print(f'QC:       {paths["qc"]}')
        core.quit()


if __name__ == '__main__':
    main()
