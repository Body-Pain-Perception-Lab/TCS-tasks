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
import copy
import json
import glob as _glob

from psychopy import visual, event, core, gui

from config_v3 import CONFIG
from masks import get_mask
from thermode import ThermodeController
from run_block import run_block
from ratings import collect_vas_ratings
from io_utils import (detect_serial_port, create_output_paths,
                      write_thermode_json, open_output_files,
                      close_output_files, write_qc_rows, write_event_rows,
                      write_vas_rows)


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
    """Single GUI dialog for run selection and experiment parameters."""
    import math
    dummy_s = config['dummy_volumes'] * config['TR']
    half_s = config['cycles_per_half'] * config['cycle_duration']
    total_s = (dummy_s + config['baseline_buffer']
               + half_s + config['mid_run_pause'] + half_s
               + config['baseline_buffer'])
    n_volumes = int(math.ceil(total_s / config['TR']))
    run_min = int(total_s // 60)
    run_sec = int(total_s % 60)

    # Build run plan summary (without completion status — checked after)
    block_plan = get_block_plan(config)
    n_cyc = config['cycles_per_half']
    summary_lines = [
        f'--- Run Plan (4 runs, 2 halves each) ---',
        f'Per run: {n_volumes} volumes, {run_min}m {run_sec}s '
        f'(2 x {n_cyc} cycles x {config["cycle_duration"]:.0f}s, '
        f'{config["mid_run_pause"]:.0f}s pause)',
        '',
    ]
    for i, block in enumerate(block_plan):
        cond = block['block_type']
        if block['warm_first']:
            direction = (f'Warm-First ({n_cyc} cycles) --> '
                         f'Cold-First ({n_cyc} cycles)')
        else:
            direction = (f'Cold-First ({n_cyc} cycles) --> '
                         f'Warm-First ({n_cyc} cycles)')
        summary_lines.append(f"  Run {i + 1} [{cond}]: {direction}")
    summary = '\n'.join(summary_lines)

    port_label, default_port = detect_serial_port()

    all_choices = [f'Run {i + 1}' for i in range(len(block_plan))]

    dlg = gui.Dlg(title='fMRI Triangular Wave v3')
    if hasattr(dlg, 'requiredMsg'):
        dlg.requiredMsg.hide()
    dlg.addText(summary)
    dlg.addField('Participant ID:', '0001')
    dlg.addField('Session:', '01')
    dlg.addField('Run:', choices=all_choices)
    dlg.addField('Body site:', choices=['Arm', 'Leg'])
    dlg.addField('Max delta (°C):', config['max_delta'])
    dlg.addField(port_label, default_port)
    dlg.addField('Trigger mode:', choices=['keyboard', 'parallel'])
    dlg.addField('Simulation:', config['simulation'])
    dlg.addField('Emulate scanner:', config['emulate'])
    dlg.addField('Fullscreen:', config['fullscreen'])
    data = dlg.show()
    if not dlg.OK:
        print('User cancelled.')
        sys.exit(0)

    participant_id = data[0]
    session = data[1]

    # Parse run selection (e.g. 'Run 2' -> index 1)
    selected = data[2]
    block_num = int(selected.split(' ')[1])
    block_idx = block_num - 1
    selected_block = block_plan[block_idx]
    run_num = f'{block_num:02d}'

    # Check for already-completed runs
    completed = scan_completed_runs(participant_id, session)
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
        'body_site': data[3],
        'max_delta': float(data[4]),
        'com_port': data[5],
        'trigger_mode': data[6],
        'simulation': data[7],
        'emulate': data[8],
        'fullscreen': data[9],
    }


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
        print('Press space to start...')
        event.waitKeys(keyList=['space'])

    elif config.get('trigger_mode', 'keyboard') == 'parallel':
        import parallel
        p_sc = parallel.Parallel(port=config.get('parallel_port', 0))
        p_sc.setDataDir(0)
        p_sc.setData(0)
        print('Waiting for scanner trigger (parallel port)...')
        while p_sc.getInAcknowledge():
            pass  # spin until falling edge

    else:
        print(f'Waiting for scanner trigger (key={config["trigger_key"]!r})...')
        event.waitKeys(keyList=[config['trigger_key']])

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

        keys = event.getKeys(keyList=['escape'])
        if keys:
            raise KeyboardInterrupt("Escape pressed")

        elapsed = pause_clock.getTime() - target_time
        wait_time = sample_interval - elapsed
        if wait_time > 0:
            core.wait(wait_time)


def main():
    config = copy.deepcopy(CONFIG)
    info = get_session_info(config)

    # Apply GUI selections to config
    config['max_delta'] = info['max_delta']
    config['com_port'] = info['com_port']
    config['trigger_mode'] = info['trigger_mode']
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

    print(f'\n=== Run {info["run"]}: {block_type} | {mask_name} | {info["body_site"]} | '
          f'Half 1: {dir1}, Half 2: {dir2} ===\n')

    # Create BIDS output paths
    paths = create_output_paths(info)
    print(f'Events:   {paths["events"]}')
    print(f'Thermode: {paths["thermode"]}')
    print(f'QC:       {paths["qc"]}')

    # Write thermode JSON sidecar
    write_thermode_json(paths['thermode_json'], config, info)

    # Open output TSV files
    out = open_output_files(paths)
    events_writer = out['events_writer']
    thermode_writer = out['thermode_writer']
    thermode_file = out['thermode_file']
    qc_writer = out['qc_writer']

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
        write_qc_rows(qc_writer, half1_result['qc_summaries'],
                       block_type, mask_name, warm_first)
        write_event_rows(events_writer, half1_result['timings'],
                         block_type, mask_name, warm_first)
        out['qc_file'].flush()

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
        write_qc_rows(qc_writer, half2_result['qc_summaries'],
                       block_type, mask_name, half2_warm_first)
        write_event_rows(events_writer, half2_result['timings'],
                         block_type, mask_name, half2_warm_first)
        out['qc_file'].flush()

        # VAS ratings
        if config['vas_enabled']:
            print('  Collecting VAS ratings...')
            vas_results = collect_vas_ratings(
                win, global_clock, trigger_time, config)
            write_vas_rows(events_writer, vas_results,
                           block_type, mask_name, warm_first)
            out['events_file'].flush()
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
        close_output_files(out)
        win.close()
        print(f'\nEvents:   {paths["events"]}')
        print(f'Thermode: {paths["thermode"]}')
        print(f'QC:       {paths["qc"]}')
        core.quit()


if __name__ == '__main__':
    main()
