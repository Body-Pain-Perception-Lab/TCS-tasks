"""
Run a single combined run of the fMRI electrical pRF experiment.

Run this script once per run. Each run contains two halves (opposite
waveform directions) separated by a mid-run pause.

Each invocation:
    1. GUI: participant, session, run, body site, settings
    2. Wait for scanner trigger
    3. Half 1 (baseline + 12 cycles)
    4. Mid-run pause (30s, no stimulation)
    5. Half 2 (12 cycles + baseline, opposite direction)
    6. Collect VAS ratings (if enabled)
    7. Save data and exit

Usage:
    python run_experiment.py
"""

import os
import sys
import csv
import copy
import json
import platform
from datetime import datetime

from psychopy import visual, event, core, gui

from config_electric_L01 import CONFIG
# DS5Control_python3_BPPlab lives in the repo-level PythonHelpers/ dir
# (../../PythonHelpers relative to this file).
_helpers = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'PythonHelpers'))
if _helpers not in sys.path:
    sys.path.insert(0, _helpers)
from DS5Control_python3_BPPlab import DS5Controller
from run_block import run_block
from ratings import collect_vas_ratings


def get_block_plan(config):
    """Return the planned 4-run sequence.

    Each run combines two halves with opposite waveform direction.
    'warm_first' indicates the first half ramps up; second half ramps down.
    """
    if config['ramp_up_first']:
        return [
            {'block_type': 'electrical', 'warm_first': True},
            {'block_type': 'electrical', 'warm_first': False},
            {'block_type': 'electrical', 'warm_first': True},
            {'block_type': 'electrical', 'warm_first': False},
        ]
    else:
        return [
            {'block_type': 'electrical', 'warm_first': False},
            {'block_type': 'electrical', 'warm_first': True},
            {'block_type': 'electrical', 'warm_first': False},
            {'block_type': 'electrical', 'warm_first': True},
        ]


def scan_completed_runs(participant_id, session):
    """Check which runs already have data files."""
    import glob as _glob
    base_dir = os.path.join(os.path.dirname(__file__) or '.', 'data',
                            f'sub-{participant_id}',
                            f'ses-{session}',
                            'func')
    completed = {}
    if not os.path.exists(base_dir):
        return completed

    json_files = _glob.glob(os.path.join(base_dir, '*_stim_*.json'))
    for jf in json_files:
        fname = os.path.basename(jf)
        for part in fname.split('_'):
            if part.startswith('run-'):
                run_num = part[4:]
                with open(jf, 'r') as f:
                    completed[run_num] = json.load(f)
                break
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
        if block['warm_first']:
            direction = (f'Ramp-Up ({n_cyc} cycles) --> '
                         f'Ramp-Down ({n_cyc} cycles)')
        else:
            direction = (f'Ramp-Down ({n_cyc} cycles) --> '
                         f'Ramp-Up ({n_cyc} cycles)')
        summary_lines.append(f"  Run {i + 1}: {direction}")
    summary = '\n'.join(summary_lines)

    # Auto-detect serial port
    os_name = platform.system()
    if os_name == 'Linux':
        port_label = 'Serial port (e.g. /dev/ttyACM0):'
        default_port = '/dev/ttyACM0'
    elif os_name == 'Darwin':
        port_label = 'Serial port (e.g. /dev/tty.usbmodem1101):'
        default_port = '/dev/tty.usbmodem1101'
    else:
        port_label = 'COM port (e.g. COM8):'
        default_port = 'COM8'

    all_choices = [f'Run {i + 1}' for i in range(len(block_plan))]

    dlg = gui.Dlg(title='fMRI Electrical Stimulation v3')
    if hasattr(dlg, 'requiredMsg'):
        dlg.requiredMsg.hide()
    dlg.addText(summary)
    dlg.addField('Participant ID:', '0001')
    dlg.addField('Session:', '01')
    dlg.addField('Run:', choices=all_choices)
    dlg.addField('Body site:', choices=['Arm', 'Leg'])
    dlg.addField('Max amplitude (mV):', config['max_amplitude'])
    dlg.addField('Pulse width (ms):', config['pulse_width_ms'])
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

    selected = data[2]
    block_num = int(selected.split(' ')[1])
    block_idx = block_num - 1
    selected_block = block_plan[block_idx]
    run_num = f'{block_num:02d}'

    completed = scan_completed_runs(participant_id, session)
    if run_num in completed:
        print(f'NOTE: Run {block_num} (run-{run_num}) was already run. '
              f'Data will be saved with a new timestamp (not overwritten).')

    return {
        'participant_id': participant_id,
        'session': session,
        'run': run_num,
        'block_type': selected_block['block_type'],
        'warm_first': selected_block['warm_first'],
        'body_site': data[3],
        'max_amplitude': float(data[4]),
        'pulse_width_ms': float(data[5]),
        'com_port': data[6],
        'trigger_mode': data[7],
        'simulation': data[8],
        'emulate': data[9],
        'fullscreen': data[10],
    }


def create_output_paths(info):
    """Create BIDS output directory and return file paths."""
    base_dir = os.path.join(os.path.dirname(__file__) or '.', 'data',
                            f'sub-{info["participant_id"]}',
                            f'ses-{info["session"]}',
                            'func')
    os.makedirs(base_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
    prefix = (f'sub-{info["participant_id"]}_ses-{info["session"]}'
              f'_task-eprf_run-{info["run"]}')

    return {
        'events': os.path.join(base_dir, f'{prefix}_events_{timestamp}.tsv'),
        'stim': os.path.join(base_dir, f'{prefix}_stim_{timestamp}.tsv'),
        'stim_json': os.path.join(base_dir, f'{prefix}_stim_{timestamp}.json'),
        'qc': os.path.join(base_dir, f'{prefix}_qc_{timestamp}.tsv'),
    }


def write_stim_json(path, config, info):
    """Write JSON sidecar for the stimulation recording."""
    sidecar = {
        'SamplingFrequency': config['update_hz'],
        'StartTime': 0.0,
        'Columns': [
            'onset', 'volume', 'block_index', 'block_type', 'cycle_index',
            'warm_first', 'amplitude_mv', 'pulse_width_ms',
        ],
        'block_type': info['block_type'],
        'warm_first': info['warm_first'],
        'body_site': info['body_site'],
        'max_amplitude': config['max_amplitude'],
        'pulse_width_ms': config['pulse_width_ms'],
        'cycle_duration': config['cycle_duration'],
        'cycles_per_half': config['cycles_per_half'],
        'mid_run_pause': config['mid_run_pause'],
        'TR': config['TR'],
        'config_source': 'config_electric_L01.py',
        'config': config,
    }
    with open(path, 'w') as f:
        json.dump(sidecar, f, indent=2)


def wait_for_trigger(config, global_clock, win):
    """Wait for scanner trigger or space bar, return trigger time."""
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
            pass
    else:
        print(f'Waiting for scanner trigger (key={config["trigger_key"]!r})...')
        event.waitKeys(keyList=[config['trigger_key']])

    trigger_time = global_clock.getTime()
    print(f'Trigger received at {trigger_time:.4f}s')

    dummy_wait = config['TR'] * config['dummy_volumes']
    print(f'Waiting {dummy_wait:.1f}s for {config["dummy_volumes"]} dummy volumes...')

    wait_msg = visual.TextStim(
        win,
        text=f'Trigger received.\nWaiting for dummy volumes ({dummy_wait:.0f}s)...',
        pos=(0, 0), height=0.05, color='white')
    wait_msg.draw()
    win.flip()
    core.wait(dummy_wait)
    return trigger_time


def _run_mid_pause(duration, ds5, win, global_clock, trigger_time,
                   config, physio_writer, physio_file):
    """Hold zero amplitude during mid-run pause with logging."""
    update_hz = config['update_hz']
    sample_interval = 1.0 / update_hz
    n_samples = int(duration * update_hz)

    fixation = visual.Circle(win, radius=0.01, edges=32,
                             lineColor='white', fillColor='lightGrey',
                             pos=(0, 0))
    pause_text = visual.TextStim(win, text='', pos=(0, -0.35),
                                 height=0.03, color='grey')

    pause_clock = core.Clock()
    for i in range(n_samples):
        target_time = i * sample_interval

        t_now = global_clock.getTime()
        t_from_trigger = t_now - trigger_time
        volume = int(t_from_trigger / config['TR']) + 1

        physio_writer.writerow([
            f'{t_from_trigger:.4f}',
            volume,
            0,
            'mid_run_pause',
            -1,
            0,
            '0.00',
            f'{config["pulse_width_ms"]:.1f}',
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


def _write_qc_rows(qc_writer, qc_summaries, block_type, warm_first):
    for s in qc_summaries:
        qc_writer.writerow([
            block_type,
            int(warm_first),
            s['cycle_index'],
            s['n_pulses'],
            f'{s["mean_amplitude"]:.2f}',
            f'{s["max_amplitude"]:.2f}',
            f'{s["mean_timing_error_ms"]:.4f}',
            f'{s["max_timing_error_ms"]:.4f}',
            s['n_samples'],
        ])


def _write_event_rows(events_writer, timings, block_type, warm_first):
    for phase in timings:
        events_writer.writerow([
            f'{phase["onset"]:.4f}',
            f'{phase["duration"]:.4f}',
            phase['trial_type'],
            block_type,
            int(warm_first),
            'n/a',
            'n/a',
        ])


def main():
    config = copy.deepcopy(CONFIG)
    info = get_session_info(config)

    config['max_amplitude'] = info['max_amplitude']
    config['pulse_width_ms'] = info['pulse_width_ms']
    config['com_port'] = info['com_port']
    config['trigger_mode'] = info['trigger_mode']
    config['simulation'] = info['simulation']
    config['emulate'] = info['emulate']
    config['fullscreen'] = info['fullscreen']

    block_type = info['block_type']
    warm_first = info['warm_first']
    dir1 = 'ramp-up' if warm_first else 'ramp-down'
    dir2 = 'ramp-down' if warm_first else 'ramp-up'

    print(f'\n=== Run {info["run"]}: {block_type} | {info["body_site"]} | '
          f'Half 1: {dir1}, Half 2: {dir2} ===\n')

    paths = create_output_paths(info)
    print(f'Events: {paths["events"]}')
    print(f'Stim:   {paths["stim"]}')
    print(f'QC:     {paths["qc"]}')

    write_stim_json(paths['stim_json'], config, info)

    events_file = open(paths['events'], 'w', newline='')
    events_writer = csv.writer(events_file, delimiter='\t')
    events_writer.writerow([
        'onset', 'duration', 'trial_type',
        'block_type', 'warm_first',
        'response_value', 'response_time',
    ])

    stim_file = open(paths['stim'], 'w', newline='')
    stim_writer = csv.writer(stim_file, delimiter='\t')

    qc_file = open(paths['qc'], 'w', newline='')
    qc_writer = csv.writer(qc_file, delimiter='\t')
    qc_writer.writerow([
        'block_type', 'warm_first',
        'cycle_index', 'n_pulses',
        'mean_amplitude', 'max_amplitude',
        'mean_timing_error_ms', 'max_timing_error_ms',
        'n_samples',
    ])

    # Initialize DS5
    ds5 = DS5Controller(port=config['com_port'],
                        simulation=config['simulation'])
    ds5.set_pulse_width(config['pulse_width_ms'])

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

    global_clock = core.Clock()
    trigger_time = wait_for_trigger(config, global_clock, win)

    try:
        # === Half 1 ===
        print(f'\n--- Half 1: {dir1} ---')
        half1_result = run_block(
            block_idx=0,
            block_type=block_type,
            warm_first=warm_first,
            n_blocks=2,
            ds5=ds5,
            win=win,
            global_clock=global_clock,
            trigger_time=trigger_time,
            physio_writer=stim_writer,
            config=config,
            physio_file=stim_file,
            include_post_baseline=False,
        )
        stim_file.flush()
        _write_qc_rows(qc_writer, half1_result['qc_summaries'],
                        block_type, warm_first)
        _write_event_rows(events_writer, half1_result['timings'],
                          block_type, warm_first)
        qc_file.flush()

        # === Mid-run pause ===
        print(f'\n--- Mid-run pause ({config["mid_run_pause"]:.0f}s) ---')
        pause_onset = global_clock.getTime() - trigger_time
        _run_mid_pause(
            config['mid_run_pause'], ds5, win,
            global_clock, trigger_time, config,
            stim_writer, stim_file,
        )
        pause_end = global_clock.getTime() - trigger_time
        events_writer.writerow([
            f'{pause_onset:.4f}',
            f'{pause_end - pause_onset:.4f}',
            'mid_run_pause',
            block_type,
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
            warm_first=half2_warm_first,
            n_blocks=2,
            ds5=ds5,
            win=win,
            global_clock=global_clock,
            trigger_time=trigger_time,
            physio_writer=stim_writer,
            config=config,
            physio_file=stim_file,
            include_pre_baseline=False,
        )
        stim_file.flush()
        _write_qc_rows(qc_writer, half2_result['qc_summaries'],
                        block_type, half2_warm_first)
        _write_event_rows(events_writer, half2_result['timings'],
                          block_type, half2_warm_first)
        qc_file.flush()

        # VAS ratings
        if config['vas_enabled']:
            print('  Collecting VAS ratings...')
            vas_results = collect_vas_ratings(
                win, global_clock, trigger_time, config)
            for r in vas_results:
                rt = r['rt']
                is_valid = rt == rt
                events_writer.writerow([
                    f'{r["onset_from_trigger_s"]:.4f}',
                    f'{rt:.4f}' if is_valid else 'n/a',
                    f'rating_{r["question"]}',
                    block_type,
                    int(warm_first),
                    r['rating'] if is_valid else 'n/a',
                    f'{rt:.4f}' if is_valid else 'n/a',
                ])
            events_file.flush()
            print('  Ratings: ' + ', '.join(
                f'{r["question"]}={r["rating"]}' for r in vas_results))

        end_msg = visual.TextStim(win, text='Run complete.\nThank you!',
                                  pos=(0, 0), height=0.06, color='white')
        end_msg.draw()
        win.flip()
        core.wait(3.0)

    except KeyboardInterrupt:
        print('\nRun aborted by user.')

    finally:
        ds5.set_amplitude(0)
        ds5.close()
        events_file.close()
        stim_file.close()
        qc_file.close()
        win.close()
        print(f'\nEvents: {paths["events"]}')
        print(f'Stim:   {paths["stim"]}')
        print(f'QC:     {paths["qc"]}')
        core.quit()


if __name__ == '__main__':
    main()
