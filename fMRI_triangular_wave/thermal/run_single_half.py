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

import sys
import copy

from psychopy import visual, event, core, gui

from config_v3 import CONFIG
from masks import get_mask
from thermode import ThermodeController
from run_block import run_block
from ratings import collect_vas_ratings
from run_experiment import wait_for_trigger
from io_utils import (detect_serial_port, create_output_paths,
                      write_thermode_json, open_output_files,
                      close_output_files, write_qc_rows, write_event_rows,
                      write_vas_rows)


def get_session_info(config):
    """GUI for single-half recovery run."""
    import math
    dummy_s = config['dummy_volumes'] * config['TR']
    half_s = config['cycles_per_half'] * config['cycle_duration']
    total_s = dummy_s + config['baseline_buffer'] + half_s + config['baseline_buffer']
    n_volumes = int(math.ceil(total_s / config['TR']))
    run_min = int(total_s // 60)
    run_sec = int(total_s % 60)

    port_label, default_port = detect_serial_port()

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
    dlg1.addField('Trigger mode:', choices=['keyboard', 'parallel'])
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
        'trigger_mode': data1[8],
        'simulation': data1[9],
        'emulate': data1[10],
        'fullscreen': data1[11],
    }


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
    write_thermode_json(paths['thermode_json'], config, info,
                        run_type='single_half_recovery')

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
        write_qc_rows(qc_writer, result['qc_summaries'],
                       block_type, mask_name, warm_first)
        out['qc_file'].flush()

        # Write phase events
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
        close_output_files(out)
        win.close()
        print(f'\nEvents:   {paths["events"]}')
        print(f'Thermode: {paths["thermode"]}')
        print(f'QC:       {paths["qc"]}')
        core.quit()


if __name__ == '__main__':
    main()
