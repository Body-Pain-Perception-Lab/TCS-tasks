"""
Run the fMRI tprf thermode experiment.

Supports two run modes (selected in the GUI):

    Full run (default):
        Two halves (opposite waveform directions) separated by a mid-run
        pause at baseline temperature. Select which run from the 4-run plan.

    Single half recovery:
        One half only (12 cycles). Use when a full run was interrupted and
        only one half needs to be rerun. Manually specify condition and
        direction.

Each invocation:
    1. GUI: choose run mode, participant ID, session, parameters
    2. Wait for scanner trigger
    3. Execute stimulation (full run or single half)
    4. Collect VAS ratings (if enabled)
    5. Save data and exit

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

from config_thermal_L01 import CONFIG
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
    """Single GUI dialog for run mode selection and experiment parameters.

    Supports two run modes:
        'Full run'              — select from the 4-run plan (2 halves each)
        'Single half recovery'  — manually specify condition/direction
    """
    import math
    block_plan = get_block_plan(config)
    n_cyc = config['cycles_per_half']
    dummy_s = config['dummy_volumes'] * config['TR']
    half_s = n_cyc * config['cycle_duration']

    # Full run timing
    full_s = (dummy_s + config['baseline_buffer']
              + half_s + config['mid_run_pause'] + half_s
              + config['baseline_buffer'])
    full_vols = int(math.ceil(full_s / config['TR']))
    full_min = int(full_s // 60)
    full_sec = int(full_s % 60)

    # Single half timing
    single_s = (dummy_s + config['baseline_buffer']
                + half_s + config['baseline_buffer'])
    single_vols = int(math.ceil(single_s / config['TR']))
    single_min = int(single_s // 60)
    single_sec = int(single_s % 60)

    # Build run plan summary
    summary_lines = [
        f'--- Run Plan (4 runs, 2 halves each) ---',
        f'Full run: {full_vols} volumes, {full_min}m {full_sec}s '
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
    summary_lines.append('')
    summary_lines.append(
        f'Recovery: {single_vols} volumes, {single_min}m {single_sec}s '
        f'({n_cyc} cycles x {config["cycle_duration"]:.0f}s)')
    summary = '\n'.join(summary_lines)

    port_label, default_port = detect_serial_port()
    all_choices = [f'Run {i + 1}' for i in range(len(block_plan))]

    dlg = gui.Dlg(title='fMRI Triangular Wave v3')
    if hasattr(dlg, 'requiredMsg'):
        dlg.requiredMsg.hide()
    dlg.addText(summary)
    dlg.addField('Run mode:', choices=['Full run', 'Single half recovery'])
    dlg.addField('Participant ID:', '0001')
    dlg.addField('Session:', '01')
    # Full run field
    dlg.addField('Run (full run):', choices=all_choices)
    # Recovery fields
    dlg.addField('Condition (recovery):', choices=['NonTGI', 'TGI'])
    dlg.addField('Direction (recovery):', choices=['warm-first', 'cool-first'])
    dlg.addField('Run number (recovery):', '01')
    # Common fields
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

    run_mode = data[0]
    participant_id = data[1]
    session = data[2]

    if run_mode == 'Full run':
        # Parse run selection (e.g. 'Run 2' -> index 1)
        selected = data[3]
        block_num = int(selected.split(' ')[1])
        selected_block = block_plan[block_num - 1]
        run_num = f'{block_num:02d}'

        # Check for already-completed runs
        completed = scan_completed_runs(participant_id, session)
        if run_num in completed:
            print(f'NOTE: Run {block_num} (run-{run_num}) was already run. '
                  f'Data will be saved with a new timestamp (not overwritten).')

        info = {
            'run_mode': 'full',
            'block_type': selected_block['block_type'],
            'mask_name': selected_block['mask_name'],
            'warm_first': selected_block['warm_first'],
        }
    else:
        # Recovery mode — use condition/direction/run number fields
        condition = data[4]
        mask_name = (config['nontgi_mask'] if condition == 'NonTGI'
                     else config['tgi_mask'])
        run_num = data[6]

        info = {
            'run_mode': 'recovery',
            'block_type': condition,
            'mask_name': mask_name,
            'warm_first': data[5] == 'warm-first',
        }

    info.update({
        'participant_id': participant_id,
        'session': session,
        'run': run_num,
        'body_site': data[7],
        'max_delta': float(data[8]),
        'com_port': data[9],
        'trigger_mode': data[10],
        'simulation': data[11],
        'emulate': data[12],
        'fullscreen': data[13],
    })

    return info


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
        input('Press Enter to start...')
        # event.waitKeys(keyList=['space'])

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
    run_mode = info['run_mode']
    block_type = info['block_type']
    mask_name = info['mask_name']
    mask_array = get_mask(mask_name)
    warm_first = info['warm_first']

    if run_mode == 'full':
        dir1 = 'warm-first' if warm_first else 'cool-first'
        dir2 = 'cool-first' if warm_first else 'warm-first'
        print(f'\n=== Run {info["run"]}: {block_type} | {mask_name} | '
              f'{info["body_site"]} | Half 1: {dir1}, Half 2: {dir2} ===\n')
    else:
        direction = 'warm-first' if warm_first else 'cool-first'
        print(f'\n=== Single Half Recovery ===')
        print(f'Run {info["run"]}: {block_type} | {mask_name} | '
              f'{info["body_site"]} | {direction}')
        print(f'{config["cycles_per_half"]} cycles\n')

    # Create BIDS output paths
    paths = create_output_paths(info)
    print(f'Events:   {paths["events"]}')
    print(f'Thermode: {paths["thermode"]}')
    print(f'QC:       {paths["qc"]}')

    # Write thermode JSON sidecar
    run_type = 'single_half_recovery' if run_mode == 'recovery' else None
    write_thermode_json(paths['thermode_json'], config, info, run_type=run_type)

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
        if run_mode == 'full':
            # === Full run: two halves with mid-run pause ===

            # Half 1
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

            # Mid-run pause
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

            # Half 2 (opposite direction)
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

        else:
            # === Single half recovery ===
            result = run_block(
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
            write_qc_rows(qc_writer, result['qc_summaries'],
                           block_type, mask_name, warm_first)
            out['qc_file'].flush()
            write_event_rows(events_writer, result['timings'],
                             block_type, mask_name, warm_first)

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
        done_label = 'Run' if run_mode == 'full' else 'Half'
        end_msg = visual.TextStim(win, text=f'{done_label} complete.\nThank you!',
                                  pos=(0, 0), height=0.06, color='white')
        end_msg.draw()
        win.flip()
        core.wait(3.0)

    except KeyboardInterrupt:
        label = 'Run' if run_mode == 'full' else 'Half'
        print(f'\n{label} aborted by user.')

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
