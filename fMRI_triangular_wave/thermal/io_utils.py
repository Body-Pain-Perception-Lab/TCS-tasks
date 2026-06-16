"""Shared I/O utilities for thermal pRF experiment scripts.

Extracted from run_experiment.py and run_single_half.py to avoid
duplication of BIDS output paths, JSON sidecars, TSV headers, and
row-writing helpers.
"""

import os
import csv
import json
import platform
from datetime import datetime


# ---------------------------------------------------------------------------
# TSV column headers
# ---------------------------------------------------------------------------

EVENTS_HEADER = [
    'onset', 'duration', 'trial_type',
    'block_type', 'mask_name', 'warm_first',
    'response_value', 'response_time',
]

QC_HEADER = [
    'block_type', 'mask_name', 'warm_first',
    'cycle_index', 'onset_latency_s',
    'mean_ramp_rate', 'std_ramp_rate',
    'mean_warming_rate', 'mean_cooling_rate', 'warming_cooling_diff',
    'mean_temp_error', 'max_temp_error', 'n_ramp_flags',
    'overheat_flagged', 'n_samples',
]

THERMODE_COLUMNS = [
    'onset', 'volume', 'block_index', 'block_type', 'cycle_index',
    'mask_name', 'warm_first', 'delta',
    'zone1_set', 'zone2_set', 'zone3_set', 'zone4_set', 'zone5_set',
    'zone1_actual', 'zone2_actual', 'zone3_actual', 'zone4_actual',
    'zone5_actual',
]


# ---------------------------------------------------------------------------
# Serial port detection
# ---------------------------------------------------------------------------

def detect_serial_port():
    """Return (label, default_port) based on the current OS."""
    os_name = platform.system()
    if os_name == 'Linux':
        return 'Serial port (e.g. /dev/ttyACM0):', '/dev/ttyACM0'
    elif os_name == 'Darwin':
        return 'Serial port (e.g. /dev/tty.usbmodem1101):', '/dev/tty.usbmodem1101'
    else:
        return 'COM port (e.g. COM3, COM8):', 'COM3'


# ---------------------------------------------------------------------------
# Output paths and files
# ---------------------------------------------------------------------------

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


def open_output_files(paths):
    """Open BIDS output TSV files and write headers.

    Returns dict with keys: events_file, events_writer, thermode_file,
    thermode_writer, qc_file, qc_writer.
    """
    events_file = open(paths['events'], 'w', newline='')
    events_writer = csv.writer(events_file, delimiter='\t')
    events_writer.writerow(EVENTS_HEADER)

    thermode_file = open(paths['thermode'], 'w', newline='')
    thermode_writer = csv.writer(thermode_file, delimiter='\t')

    qc_file = open(paths['qc'], 'w', newline='')
    qc_writer = csv.writer(qc_file, delimiter='\t')
    qc_writer.writerow(QC_HEADER)

    return {
        'events_file': events_file,
        'events_writer': events_writer,
        'thermode_file': thermode_file,
        'thermode_writer': thermode_writer,
        'qc_file': qc_file,
        'qc_writer': qc_writer,
    }


def close_output_files(out):
    """Close all output TSV files."""
    for key in ('events_file', 'thermode_file', 'qc_file'):
        f = out.get(key)
        if f is not None:
            f.close()


# ---------------------------------------------------------------------------
# JSON sidecar
# ---------------------------------------------------------------------------

def get_config_source():
    """Return the filename that CONFIG was imported from."""
    import sys as _sys
    for name, mod in _sys.modules.items():
        if mod is None:
            continue
        if hasattr(mod, 'CONFIG') and name.startswith('config'):
            src = getattr(mod, '__file__', None)
            if src:
                return os.path.basename(src)
            return name
    return 'unknown'


def write_thermode_json(path, config, info, run_type=None):
    """Write JSON sidecar for the thermode recording.

    Parameters
    ----------
    run_type : str, optional
        If provided (e.g. 'single_half_recovery'), included in sidecar.
    """
    sidecar = {
        'SamplingFrequency': config['update_hz'],
        'StartTime': 0.0,
        'Columns': THERMODE_COLUMNS,
        'block_type': info['block_type'],
        'mask_name': info['mask_name'],
        'warm_first': info['warm_first'],
        'body_site': info['body_site'],
        'baseline_temp': config['baseline_temp'],
        'max_delta': config['max_delta'],
        'cycle_duration': config['cycle_duration'],
        'cycles_per_half': config['cycles_per_half'],
        'mid_run_pause': config['mid_run_pause'],
        'ramp_rate': config['ramp_rate'],
        'TR': config['TR'],
        'config_source': get_config_source(),
        'config': config,
    }
    if run_type is not None:
        sidecar['run_type'] = run_type
    with open(path, 'w') as f:
        json.dump(sidecar, f, indent=2)


# ---------------------------------------------------------------------------
# TSV row writers
# ---------------------------------------------------------------------------

def write_qc_rows(qc_writer, qc_summaries, block_type, mask_name,
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


def write_event_rows(events_writer, timings, block_type, mask_name,
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


def write_vas_rows(events_writer, vas_results, block_type, mask_name,
                   warm_first):
    """Write VAS rating events to the events TSV."""
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
