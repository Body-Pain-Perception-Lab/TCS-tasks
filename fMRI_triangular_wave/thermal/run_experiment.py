"""
Run a single combined run of the fMRI tprf thermode experiment.

Run this script once per run. Each run contains two halves (opposite
waveform directions) separated by a mid-run pause at baseline temperature.

Each invocation:
    1. GUI step 1: enter participant ID and session
    2. GUI step 2: see run plan summary (which runs are done),
       select which run to execute
    3. Wait for scanner trigger
    4. Half 1 (baseline + 12 cycles)
    5. Mid-run pause (30s at baseline)
    6. Half 2 (12 cycles + baseline, opposite direction)
    7. Collect VAS ratings (if enabled)
    8. Save data and exit

Output (BIDS, per run):
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
import platform
from datetime import datetime

from psychopy import visual, event, core, gui
from psychopy.hardware import keyboard

from config_v3 import CONFIG
from masks import get_mask
from thermode import ThermodeController
from run_block import run_block
from ratings import collect_vas_ratings


def get_block_plan(config):
    """Return the planned 4-run sequence based on config.

    Each run combines two halves with opposite waveform direction,
    separated by a mid-run pause. NonTGI runs first (1-2), then TGI (3-4).
    'warm_first' indicates the direction of the first half; the second
    half always uses the opposite direction.

    Run order is determined by nontgi_warm_first:
        True  (Group A): first half W-first, then C-first
        False (Group B): first half C-first, then W-first
    """
    nontgi_mask = config['nontgi_mask']
    tgi_mask = config['tgi_mask']

    if config['nontgi_warm_first']:
        return [
            {'block_type': 'NonTGI', 'mask_name': nontgi_mask, 'warm_first': True},
            {'block_type': 'NonTGI', 'mask_name': nontgi_mask, 'warm_first': False},
            {'block_type': 'TGI',    'mask_name': tgi_mask,    'warm_first': True},
            {'block_type': 'TGI',    'mask_name': tgi_mask,    'warm_first': False},
        ]
    else:
        return [
            {'block_type': 'NonTGI', 'mask_name': nontgi_mask, 'warm_first': False},
            {'block_type': 'NonTGI', 'mask_name': nontgi_mask, 'warm_first': True},
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
    half_s = config['cycles_per_half'] * config['cycle_duration']
    total_s = (dummy_s + config['baseline_buffer']
               + half_s + config['mid_run_pause'] + half_s
               + config['baseline_buffer'])
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

    # Build summary text and find next pending run
    summary_lines = [
        f'--- Run Plan (4 runs, 2 halves each) ---',
        f'Per run: {n_volumes} volumes, {run_min}m {run_sec}s '
        f'(2 x {config["cycles_per_half"]} cycles x {config["cycle_duration"]:.0f}s, '
        f'{config["mid_run_pause"]:.0f}s pause)',
        '',
    ]
    n_cyc = config['cycles_per_half']
    next_block_idx = None
    for i, block in enumerate(block_plan):
        run_num = f'{i + 1:02d}'
        cond = block['block_type']
        if block['warm_first']:
            direction = (f'Warm-First ({n_cyc} cycles) --> '
                         f'Cold-First ({n_cyc} cycles)')
        else:
            direction = (f'Cold-First ({n_cyc} cycles) --> '
                         f'Warm-First ({n_cyc} cycles)')
        status = '[DONE]' if run_num in completed else '[--]'
        summary_lines.append(
            f"  Run {i + 1} [{cond}]: {direction}  {status}")
        if run_num not in completed and next_block_idx is None:
            next_block_idx = i

    if next_block_idx is None:
        next_block_idx = 0  # all runs done; default to first

    n_done = len(completed)
    summary_lines.append(f'\n  {n_done}/{len(block_plan)} runs completed')

    summary = '\n'.join(summary_lines)

    # Block choices — next pending block shown first in dropdown
    all_choices = [f'Run {i + 1}' for i in range(len(block_plan))]
    choices = ([all_choices[next_block_idx]]
               + [c for j, c in enumerate(all_choices) if j != next_block_idx])

    # --- Step 2: Block selection with summary ---
    # Auto-detect serial port format from OS
    os_name = platform.system()
    if os_name == 'Linux':
        port_label = 'Serial port (e.g. /dev/ttyACM0):'
        default_port = '/dev/ttyACM0'
    elif os_name == 'Darwin':
        port_label = 'Serial port (e.g. /dev/tty.usbmodem1101):'
        default_port = '/dev/tty.usbmodem1101'
    else:
        port_label = 'COM port (e.g. COM3, COM8):'
        default_port = 'COM3'

    dlg2 = gui.Dlg(title='fMRI Triangular Wave v3 — Run Selection')
    dlg2.addText(summary)
    dlg2.addField('Run:', choices=choices)
    dlg2.addField('Max delta (°C):', config['max_delta'])
    dlg2.addField(port_label, default_port)
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
        'cycles_per_half': config['cycles_per_half'],
        'mid_run_pause': config['mid_run_pause'],
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


def _run_mid_pause(duration, thermode, win, global_clock, trigger_time,
                   config, physio_writer, physio_file, mask_name):
    """Hold baseline temperature during mid-run pause with thermode logging."""
    kb = keyboard.Keyboard()
    update_hz = config['update_hz']
    sample_interval = 1.0 / update_hz
    n_samples = int(duration * update_hz)
    baseline_temps = [config['baseline_temp']] * 5

    thermode.set_baseline()

    fixation = visual.Circle(win, radius=0.01, edges=32,
                             lineColor='white', fillColor='lightGrey',
                             pos=(0, 0))
    pause_text = visual.TextStim(win, text='', pos=(0, -0.35),
                                 height=0.03, color='grey')

    pause_clock = core.Clock()
    for i in range(n_samples):
        target_time = i * sample_interval

        thermode.set_temperatures(baseline_temps)
        actual = thermode.get_temperatures()

        t_now = global_clock.getTime()
        t_from_trigger = t_now - trigger_time
        volume = int(t_from_trigger / config['TR']) + 1

        physio_writer.writerow([
            f'{t_from_trigger:.4f}',
            volume,
            0,
            'mid_run_pause',
            -1,
            mask_name,
            0,
            '0.0000',
            f'{baseline_temps[0]:.2f}', f'{baseline_temps[1]:.2f}',
            f'{baseline_temps[2]:.2f}', f'{baseline_temps[3]:.2f}',
            f'{baseline_temps[4]:.2f}',
            f'{actual[0]}', f'{actual[1]}', f'{actual[2]}',
            f'{actual[3]}', f'{actual[4]}',
        ])

        if physio_file is not None and (i + 1) % 10 == 0:
            physio_file.flush()

        fixation.draw()
        remaining = duration - pause_clock.getTime()
        pause_text.text = f'Mid-run pause ({remaining:.0f}s)'
        pause_text.draw()
        win.flip()

        keys = kb.getKeys(keyList=['escape'])
        if keys:
            raise KeyboardInterrupt("Escape pressed")

        elapsed = pause_clock.getTime() - target_time
        wait_time = sample_interval - elapsed
        if wait_time > 0:
            core.wait(wait_time)


def _write_qc_rows(qc_writer, qc_summaries, block_type, mask_name,
                    warm_first):
    """Write per-cycle QC summaries to the QC TSV."""
    for s in qc_summaries:
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


def _write_event_rows(events_writer, timings, block_type, mask_name,
                      warm_first):
    """Write phase timing events to the events TSV."""
    for phase in timings:
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


def main():
    config = copy.deepcopy(CONFIG)
    info = get_session_info(config)

    # Apply GUI selections to config
    config['max_delta'] = info['max_delta']
    config['com_port'] = info['com_port']
    config['simulation'] = info['simulation']
    config['emulate'] = info['emulate']
    config['fullscreen'] = info['fullscreen']

    # Resolve run parameters
    block_type = info['block_type']
    mask_name = info['mask_name']
    mask_array = get_mask(mask_name)
    warm_first = info['warm_first']  # first half's direction
    dir1 = 'warm-first' if warm_first else 'cool-first'
    dir2 = 'cool-first' if warm_first else 'warm-first'

    print(f'\n=== Run {info["run"]}: {block_type} | {mask_name} | '
          f'Half 1: {dir1}, Half 2: {dir2} ===\n')

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

    try:
        # === Half 1 ===
        print(f'\n--- Half 1: {dir1} ---')
        half1_result = run_block(
            block_idx=0,
            block_type=block_type,
            mask_name=mask_name,
            mask_array=mask_array,
            warm_first=warm_first,
            n_blocks=2,
            thermode=thermode,
            win=win,
            global_clock=global_clock,
            trigger_time=trigger_time,
            physio_writer=thermode_writer,
            config=config,
            physio_file=thermode_file,
            include_post_baseline=False,
        )
        thermode_file.flush()
        _write_qc_rows(qc_writer, half1_result['qc_summaries'],
                        block_type, mask_name, warm_first)
        _write_event_rows(events_writer, half1_result['timings'],
                          block_type, mask_name, warm_first)
        qc_file.flush()

        # === Mid-run pause ===
        print(f'\n--- Mid-run pause ({config["mid_run_pause"]:.0f}s) ---')
        pause_onset = global_clock.getTime() - trigger_time
        _run_mid_pause(
            config['mid_run_pause'], thermode, win,
            global_clock, trigger_time, config,
            thermode_writer, thermode_file, mask_name,
        )
        pause_end = global_clock.getTime() - trigger_time
        events_writer.writerow([
            f'{pause_onset:.4f}',
            f'{pause_end - pause_onset:.4f}',
            'mid_run_pause',
            block_type,
            mask_name,
            'n/a',
            'n/a',
            'n/a',
        ])

        # === Half 2 (opposite direction) ===
        half2_warm_first = not warm_first
        print(f'\n--- Half 2: {dir2} ---')
        half2_result = run_block(
            block_idx=1,
            block_type=block_type,
            mask_name=mask_name,
            mask_array=mask_array,
            warm_first=half2_warm_first,
            n_blocks=2,
            thermode=thermode,
            win=win,
            global_clock=global_clock,
            trigger_time=trigger_time,
            physio_writer=thermode_writer,
            config=config,
            physio_file=thermode_file,
            include_pre_baseline=False,
        )
        thermode_file.flush()
        _write_qc_rows(qc_writer, half2_result['qc_summaries'],
                        block_type, mask_name, half2_warm_first)
        _write_event_rows(events_writer, half2_result['timings'],
                          block_type, mask_name, half2_warm_first)
        qc_file.flush()

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
        end_msg = visual.TextStim(win, text='Run complete.\nThank you!',
                                  pos=(0, 0), height=0.06, color='white')
        end_msg.draw()
        win.flip()
        core.wait(3.0)

    except KeyboardInterrupt:
        print('\nRun aborted by user.')

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
