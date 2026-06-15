"""
Run a single half (12 cycles) for crash recovery.

Use this when a full run was interrupted mid-way and only one half needs
to be rerun. Prompts for condition, direction (warm-first / cool-first),
and run number.

Output uses the same BIDS layout as run_experiment.py. The JSON sidecar
includes 'run_type': 'single_half_recovery' to distinguish from full runs.
Timestamps prevent overwriting existing data.

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
from masks import get_mask
from thermode import ThermodeController
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

    dlg1 = gui.Dlg(title='Single Half Recovery')
    if hasattr(dlg1, 'requiredMsg'):
        dlg1.requiredMsg.hide()
    dlg1.addText(f'Single half: {n_volumes} volumes, {run_min}m {run_sec}s '
                 f'({config["cycles_per_half"]} cycles x '
                 f'{config["cycle_duration"]:.0f}s)')
    dlg1.addField('Participant ID:', '0001')
    dlg1.addField('Session:', '01')
    dlg1.addField('Run number:', '01')
    dlg1.addField('Condition:', choices=['NonTGI', 'TGI'])
    dlg1.addField('Direction:', choices=['warm-first', 'cool-first'])
    dlg1.addField('Body site:', choices=['Arm', 'Leg'])
    dlg1.addField('Max delta (°C):', config['max_delta'])
    dlg1.addField(port_label, default_port)
    dlg1.addField('Simulation:', config['simulation'])
    dlg1.addField('Emulate scanner:', config['emulate'])
    dlg1.addField('Fullscreen:', config['fullscreen'])
    data1 = dlg1.show()
    if not dlg1.OK:
        print('User cancelled.')
        sys.exit(0)

    # Resolve mask from condition
    condition = data1[3]
    mask_name = (config['nontgi_mask'] if condition == 'NonTGI'
                 else config['tgi_mask'])

    return {
        'participant_id': data1[0],
        'session': data1[1],
        'run': data1[2],
        'block_type': condition,
        'mask_name': mask_name,
        'warm_first': data1[4] == 'warm-first',
        'body_site': data1[5],
        'max_delta': float(data1[6]),
        'com_port': data1[7],
        'simulation': data1[8],
        'emulate': data1[9],
        'fullscreen': data1[10],
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
              f'_task-tprf_run-{info["run"]}')

    return {
        'events': os.path.join(
            base_dir, f'{prefix}_events_{timestamp}.tsv'),
        'thermode': os.path.join(
            base_dir, f'{prefix}_thermode_{timestamp}.tsv'),
        'thermode_json': os.path.join(
            base_dir, f'{prefix}_thermode_{timestamp}.json'),
        'qc': os.path.join(
            base_dir, f'{prefix}_qc_{timestamp}.tsv'),
    }


def write_thermode_json(path, config, info):
    """Write JSON sidecar for a single-half recovery run."""
    sidecar = {
        'SamplingFrequency': config['update_hz'],
        'StartTime': 0.0,
        'run_type': 'single_half_recovery',
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
        'body_site': info['body_site'],
        'baseline_temp': config['baseline_temp'],
        'max_delta': config['max_delta'],
        'cycle_duration': config['cycle_duration'],
        'cycles_per_half': config['cycles_per_half'],
        'ramp_rate': config['ramp_rate'],
        'TR': config['TR'],
        'config_source': 'config_v3.py',
        'config': config,
    }
    with open(path, 'w') as f:
        json.dump(sidecar, f, indent=2)


def main():
    config = copy.deepcopy(CONFIG)
    info = get_session_info(config)

    # Apply GUI selections to config
    config['max_delta'] = info['max_delta']
    config['com_port'] = info['com_port']
    config['simulation'] = info['simulation']
    config['emulate'] = info['emulate']
    config['fullscreen'] = info['fullscreen']

    # Resolve parameters
    block_type = info['block_type']
    mask_name = info['mask_name']
    mask_array = get_mask(mask_name)
    warm_first = info['warm_first']
    direction = 'warm-first' if warm_first else 'cool-first'

    print(f'\n=== Single Half Recovery ===')
    print(f'Run {info["run"]}: {block_type} | {mask_name} | {info["body_site"]} | {direction}')
    print(f'{config["cycles_per_half"]} cycles\n')

    # Create BIDS output paths
    paths = create_output_paths(info)
    print(f'Events:   {paths["events"]}')
    print(f'Thermode: {paths["thermode"]}')
    print(f'QC:       {paths["qc"]}')

    # Write thermode JSON sidecar
    write_thermode_json(paths['thermode_json'], config, info)

    # Open events TSV
    events_file = open(paths['events'], 'w', newline='')
    events_writer = csv.writer(events_file, delimiter='\t')
    events_writer.writerow([
        'onset', 'duration', 'trial_type',
        'block_type', 'mask_name', 'warm_first',
        'response_value', 'response_time',
    ])

    # Open thermode TSV
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

        # Write QC summaries
        for s in result['qc_summaries']:
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

        # Write phase events
        for phase in result['timings']:
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
        end_msg = visual.TextStim(win, text='Half complete.\nThank you!',
                                  pos=(0, 0), height=0.06, color='white')
        end_msg.draw()
        win.flip()
        core.wait(3.0)

    except KeyboardInterrupt:
        print('\nHalf aborted by user.')

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
