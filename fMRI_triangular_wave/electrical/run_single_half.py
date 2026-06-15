"""
Run a single half (12 cycles) for crash recovery — electrical stimulation.

Usage:
    python run_single_half.py
"""

import os
import sys
import csv
import copy
import json
import platform
from datetime import datetime

from psychopy import visual, event, core, gui

from config_v3 import CONFIG
from ds5_controller import DS5Controller
from run_block import run_block
from ratings import collect_vas_ratings
from run_experiment import wait_for_trigger


def get_session_info(config):
    """GUI for single-half recovery run."""
    import math
    dummy_s = config['dummy_volumes'] * config['TR']
    half_s = config['cycles_per_half'] * config['cycle_duration']
    total_s = dummy_s + config['baseline_buffer'] + half_s + config['baseline_buffer']
    n_volumes = int(math.ceil(total_s / config['TR']))
    run_min = int(total_s // 60)
    run_sec = int(total_s % 60)

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

    dlg1 = gui.Dlg(title='Single Half Recovery — Electrical')
    if hasattr(dlg1, 'requiredMsg'):
        dlg1.requiredMsg.hide()
    dlg1.addText(f'Single half: {n_volumes} volumes, {run_min}m {run_sec}s '
                 f'({config["cycles_per_half"]} cycles x '
                 f'{config["cycle_duration"]:.0f}s)')
    dlg1.addField('Participant ID:', '0001')
    dlg1.addField('Session:', '01')
    dlg1.addField('Run number:', '01')
    dlg1.addField('Direction:', choices=['ramp-up', 'ramp-down'])
    dlg1.addField('Body site:', choices=['Arm', 'Leg'])
    dlg1.addField('Max amplitude (mV):', config['max_amplitude'])
    dlg1.addField('Pulse width (ms):', config['pulse_width_ms'])
    dlg1.addField(port_label, default_port)
    dlg1.addField('Simulation:', config['simulation'])
    dlg1.addField('Emulate scanner:', config['emulate'])
    dlg1.addField('Fullscreen:', config['fullscreen'])
    data1 = dlg1.show()
    if not dlg1.OK:
        print('User cancelled.')
        sys.exit(0)

    return {
        'participant_id': data1[0],
        'session': data1[1],
        'run': data1[2],
        'block_type': 'electrical',
        'warm_first': data1[3] == 'ramp-up',
        'body_site': data1[4],
        'max_amplitude': float(data1[5]),
        'pulse_width_ms': float(data1[6]),
        'com_port': data1[7],
        'simulation': data1[8],
        'emulate': data1[9],
        'fullscreen': data1[10],
    }


def create_output_paths(info):
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
    sidecar = {
        'SamplingFrequency': config['update_hz'],
        'StartTime': 0.0,
        'run_type': 'single_half_recovery',
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
        'TR': config['TR'],
        'config_source': 'config_v3.py',
        'config': config,
    }
    with open(path, 'w') as f:
        json.dump(sidecar, f, indent=2)


def main():
    config = copy.deepcopy(CONFIG)
    info = get_session_info(config)

    config['max_amplitude'] = info['max_amplitude']
    config['pulse_width_ms'] = info['pulse_width_ms']
    config['com_port'] = info['com_port']
    config['simulation'] = info['simulation']
    config['emulate'] = info['emulate']
    config['fullscreen'] = info['fullscreen']

    block_type = info['block_type']
    warm_first = info['warm_first']
    direction = 'ramp-up' if warm_first else 'ramp-down'

    print(f'\n=== Single Half Recovery ===')
    print(f'Run {info["run"]}: {block_type} | {info["body_site"]} | {direction}')
    print(f'{config["cycles_per_half"]} cycles\n')

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
        result = run_block(
            block_idx=0,
            block_type=block_type,
            warm_first=warm_first,
            n_blocks=1,
            ds5=ds5,
            win=win,
            global_clock=global_clock,
            trigger_time=trigger_time,
            physio_writer=stim_writer,
            config=config,
            physio_file=stim_file,
        )
        stim_file.flush()

        for s in result['qc_summaries']:
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
        qc_file.flush()

        for phase in result['timings']:
            events_writer.writerow([
                f'{phase["onset"]:.4f}',
                f'{phase["duration"]:.4f}',
                phase['trial_type'],
                block_type,
                int(warm_first),
                'n/a',
                'n/a',
            ])

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

        end_msg = visual.TextStim(win, text='Half complete.\nThank you!',
                                  pos=(0, 0), height=0.06, color='white')
        end_msg.draw()
        win.flip()
        core.wait(3.0)

    except KeyboardInterrupt:
        print('\nHalf aborted by user.')

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
