"""Shared I/O utilities for electrical pRF experiment scripts.

BIDS output paths, JSON sidecars, TSV headers, and row-writing helpers
used by run_experiment.py.
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
    'block_type', 'up_first',
    'response_value', 'response_time',
]

QC_HEADER = [
    'block_type', 'up_first',
    'cycle_index', 'n_pulses',
    'mean_amplitude', 'max_amplitude',
    'mean_timing_error_ms', 'max_timing_error_ms',
    'n_samples',
]

STIM_COLUMNS = [
    'onset', 'volume', 'block_index', 'trial_type', 'cycle_index',
    'direction', 'amplitude_mv', 'current_ma', 'pulse_width_ms',
]


# ---------------------------------------------------------------------------
# Serial port detection
# ---------------------------------------------------------------------------

def detect_serial_port():
    """Return (label, default_port) for the DS5 based on the current OS.

    DS5 uses a Silicon Labs CP210x USB-to-UART bridge:
        Linux   -> /dev/ttyUSB0
        macOS   -> /dev/tty.usbmodem1101
        Windows -> COM8
    """
    os_name = platform.system()
    if os_name == 'Linux':
        return 'Serial port (e.g. /dev/ttyUSB0):', '/dev/ttyUSB0'
    elif os_name == 'Darwin':
        return 'Serial port (e.g. /dev/tty.usbmodem1101):', '/dev/tty.usbmodem1101'
    else:
        return 'COM port (e.g. COM8):', 'COM8'


# ---------------------------------------------------------------------------
# Output paths and files
# ---------------------------------------------------------------------------

def create_output_paths(info):
    """Create BIDS output directory and return file paths for one run."""
    base_dir = os.path.join(os.path.dirname(__file__) or '.', 'data',
                            f'sub-{info["participant_id"]}',
                            f'ses-{info["session"]}',
                            'func')
    os.makedirs(base_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
    prefix = (f'sub-{info["participant_id"]}_ses-{info["session"]}'
              f'_task-eprf_run-{info["run"]}')

    return {
        'events': os.path.join(
            base_dir, f'{prefix}_events_{timestamp}.tsv'),
        'stim': os.path.join(
            base_dir, f'{prefix}_stim_{timestamp}.tsv'),
        'stim_json': os.path.join(
            base_dir, f'{prefix}_stim_{timestamp}.json'),
        'qc': os.path.join(
            base_dir, f'{prefix}_qc_{timestamp}.tsv'),
    }


def open_output_files(paths):
    """Open BIDS output TSV files and write headers.

    Returns dict with keys: events_file, events_writer, stim_file,
    stim_writer, qc_file, qc_writer.
    """
    events_file = open(paths['events'], 'w', newline='')
    events_writer = csv.writer(events_file, delimiter='\t')
    events_writer.writerow(EVENTS_HEADER)

    stim_file = open(paths['stim'], 'w', newline='')
    stim_writer = csv.writer(stim_file, delimiter='\t')

    qc_file = open(paths['qc'], 'w', newline='')
    qc_writer = csv.writer(qc_file, delimiter='\t')
    qc_writer.writerow(QC_HEADER)

    return {
        'events_file': events_file,
        'events_writer': events_writer,
        'stim_file': stim_file,
        'stim_writer': stim_writer,
        'qc_file': qc_file,
        'qc_writer': qc_writer,
    }


def close_output_files(out):
    """Close all output TSV files."""
    for key in ('events_file', 'stim_file', 'qc_file'):
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


def write_stim_json(path, config, info, run_type=None):
    """Write JSON sidecar for the stimulation recording.

    Parameters
    ----------
    run_type : str, optional
        If provided (e.g. 'single_half_recovery'), included in sidecar.
    """
    sidecar = {
        'SamplingFrequency': config['update_hz'],
        'StartTime': 0.0,
        'Columns': STIM_COLUMNS,
        'block_type': info['block_type'],
        'up_first': info['up_first'],
        'body_site': info['body_site'],
        'max_amplitude': config['max_amplitude'],
        'ramp_floor': config.get('ramp_floor', 0.0),
        'pulse_width_ms': config['pulse_width_ms'],
        'update_hz': config['update_hz'],
        'cycle_duration': config['cycle_duration'],
        'cycles_per_half': config['cycles_per_half'],
        'mid_run_pause': config['mid_run_pause'],
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

def write_qc_rows(qc_writer, qc_summaries, block_type, up_first):
    """Write per-cycle QC summaries to the QC TSV."""
    for s in qc_summaries:
        qc_writer.writerow([
            block_type,
            int(up_first),
            s['cycle_index'],
            s['n_pulses'],
            f'{s["mean_amplitude"]:.2f}',
            f'{s["max_amplitude"]:.2f}',
            f'{s["mean_timing_error_ms"]:.4f}',
            f'{s["max_timing_error_ms"]:.4f}',
            s['n_samples'],
        ])


def write_event_rows(events_writer, timings, block_type, up_first):
    """Write phase timing events to the events TSV."""
    for phase in timings:
        events_writer.writerow([
            f'{phase["onset"]:.4f}',
            f'{phase["duration"]:.4f}',
            phase['trial_type'],
            block_type,
            int(up_first),
            'n/a',
            'n/a',
        ])


def write_vas_rows(events_writer, vas_results, block_type, up_first):
    """Write VAS rating events to the events TSV."""
    for r in vas_results:
        rt = r['rt']
        is_valid = rt == rt  # NaN check
        events_writer.writerow([
            f'{r["onset_from_trigger_s"]:.4f}',
            f'{rt:.4f}' if is_valid else 'n/a',
            f'rating_{r["question"]}',
            block_type,
            int(up_first),
            r['rating'] if is_valid else 'n/a',
            f'{rt:.4f}' if is_valid else 'n/a',
        ])
