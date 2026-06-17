"""
Real-time QC monitor for DS5 electrical stimulation experiment.

Displays a live matplotlib dashboard with two panels:
    1. Commanded amplitude (mV) and current (mA) over time
    2. Timing precision — actual vs expected sample intervals

For now this plots only the commanded waveform (what the code sends
to the DS5). A future version will overlay measured output once
hardware feedback is available.

Usage:
    python qc_monitor.py                     # auto-detect latest stim file
    python qc_monitor.py path/to/stim.tsv    # explicit file
"""

import sys
import os
import json
import glob
import csv

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# ---------------------------------------------------------------------------
# Column indices (must match JSON sidecar "Columns" order)
# ---------------------------------------------------------------------------
COL_ONSET = 0
COL_VOLUME = 1
COL_BLOCK_INDEX = 2
COL_TRIAL_TYPE = 3
COL_CYCLE_INDEX = 4
COL_DIRECTION = 5
COL_AMPLITUDE = 6
COL_CURRENT = 7
COL_PULSE_WIDTH = 8

N_COLUMNS = 9


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_latest_stim_file():
    """Find the most recently modified *_stim_*.tsv under data/."""
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    pattern = os.path.join(data_dir, '**', '*_stim_*.tsv')
    matches = glob.glob(pattern, recursive=True)
    if not matches:
        return None
    return max(matches, key=os.path.getmtime)


def find_json_sidecar(tsv_path):
    """Return the JSON sidecar path for a stim TSV (same name, .json)."""
    base = tsv_path.rsplit('.tsv', 1)[0]
    json_path = base + '.json'
    if os.path.exists(json_path):
        return json_path
    return None


def load_sidecar(json_path):
    """Load experiment metadata from the JSON sidecar."""
    with open(json_path, 'r') as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Data reading
# ---------------------------------------------------------------------------

def read_stim_data(filepath):
    """Read stim TSV, tolerating partial last line.

    Returns a list of rows (each row a list of strings), skipping any
    incomplete trailing line.
    """
    rows = []
    try:
        with open(filepath, 'r', newline='') as f:
            reader = csv.reader(f, delimiter='\t')
            for row in reader:
                if len(row) == N_COLUMNS:
                    rows.append(row)
    except Exception:
        pass
    return rows


def parse_rows(rows):
    """Convert raw string rows to typed numpy arrays.

    Returns dict with keys:
        onset, amplitude, current, cycle_index, block_index, direction
    or None if no data.
    """
    if not rows:
        return None

    n = len(rows)
    onset = np.empty(n)
    amplitude = np.empty(n)
    current = np.empty(n)
    block_index = np.empty(n, dtype=int)
    cycle_index = np.empty(n, dtype=int)

    for i, row in enumerate(rows):
        try:
            onset[i] = float(row[COL_ONSET])
            amplitude[i] = float(row[COL_AMPLITUDE])
            current[i] = float(row[COL_CURRENT])
            block_index[i] = int(row[COL_BLOCK_INDEX])
            cycle_index[i] = int(row[COL_CYCLE_INDEX])
        except (ValueError, IndexError):
            onset = onset[:i]
            amplitude = amplitude[:i]
            current = current[:i]
            block_index = block_index[:i]
            cycle_index = cycle_index[:i]
            break

    return {
        'onset': onset,
        'amplitude': amplitude,
        'current': current,
        'block_index': block_index,
        'cycle_index': cycle_index,
    }


# ---------------------------------------------------------------------------
# Figure setup
# ---------------------------------------------------------------------------

def create_figure(filepath, sidecar):
    """Create the 2-panel figure and return (fig, axes, line_objects)."""
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                             gridspec_kw={'height_ratios': [3, 1]})
    fig.subplots_adjust(hspace=0.25, top=0.92, bottom=0.08, left=0.08,
                        right=0.95)

    # Build title from sidecar metadata
    if sidecar:
        up = sidecar.get('up_first')
        direction = 'Up-first -> Down-first' if up else 'Down-first -> Up-first'
        title = (f"QC Monitor — {sidecar.get('block_type', '?')} | {direction}")
    else:
        title = f"QC Monitor — {os.path.basename(filepath)}"
    fig.suptitle(title, fontsize=12, fontweight='bold')

    # --- Top: Amplitude ---
    ax0 = axes[0]
    ax0.set_ylabel('Amplitude (mV)')
    ax0.set_title('Commanded amplitude', fontsize=10)
    ax0.grid(True, alpha=0.3)

    line_amp, = ax0.plot([], [], color='#377eb8', linewidth=1.0,
                         label='amplitude (mV)')

    # Reference lines
    max_amp = sidecar.get('max_amplitude', 2000) if sidecar else 2000
    ramp_floor = sidecar.get('ramp_floor', 0) if sidecar else 0
    ax0.set_ylim(-100, max_amp + 200)
    ax0.axhline(max_amp, color='red', linestyle='--', linewidth=1, alpha=0.5,
                label=f'peak ({max_amp:.0f} mV)')
    if ramp_floor > 0:
        ax0.axhline(ramp_floor, color='orange', linestyle='--', linewidth=1,
                     alpha=0.5, label=f'floor ({ramp_floor:.0f} mV)')
    ax0.axhline(0, color='grey', linestyle='-', linewidth=0.5, alpha=0.3)

    # Secondary y-axis for current (mA)
    ax0_ma = ax0.twinx()
    ax0_ma.set_ylabel('Current (mA)')
    ax0_ma.set_ylim(-0.1, max_amp / 1000 + 0.2)
    line_cur, = ax0_ma.plot([], [], color='#e41a1c', linewidth=0.8, alpha=0.5,
                            label='current (mA)')

    # --- Bottom: Timing precision ---
    ax1 = axes[1]
    ax1.set_xlabel('Time from trigger (s)')
    ax1.set_ylabel('Sample interval error (ms)')
    ax1.set_title('Timing precision', fontsize=10)
    ax1.set_ylim(-5, 20)
    ax1.grid(True, alpha=0.3)
    ax1.axhline(0, color='grey', linestyle='-', linewidth=0.5, alpha=0.3)
    ax1.axhline(10, color='red', linestyle='--', linewidth=1, alpha=0.5,
                label='warning (10 ms)')

    line_timing, = ax1.plot([], [], color='#4daf4a', linewidth=0.8,
                            label='interval error')

    line_objects = {
        'amplitude': line_amp,
        'current': line_cur,
        'timing': line_timing,
    }

    return fig, axes, ax0_ma, line_objects


# ---------------------------------------------------------------------------
# Animation update
# ---------------------------------------------------------------------------

def make_update(filepath, axes, ax0_ma, line_objects, state):
    """Return the FuncAnimation update function (closure over state)."""
    expected_interval = state.get('expected_interval', 0.125)  # 1/update_hz

    def update(frame):
        rows = read_stim_data(filepath)
        data = parse_rows(rows)
        if data is None or len(data['onset']) == 0:
            return []

        onset = data['onset']

        # Update x-axis limits
        t_max = onset[-1]
        for ax in axes:
            ax.set_xlim(0, max(t_max + 5, 10))

        # --- Amplitude ---
        line_objects['amplitude'].set_data(onset, data['amplitude'])
        line_objects['current'].set_data(onset, data['current'])

        # Build legend only once
        if not state.get('legend_set'):
            ax_amp = axes[0]
            # Combine legends from both y-axes
            h1, l1 = ax_amp.get_legend_handles_labels()
            h2, l2 = ax0_ma.get_legend_handles_labels()
            ax_amp.legend(h1 + h2, l1 + l2, loc='upper right', fontsize=7)
            axes[1].legend(loc='upper right', fontsize=7)
            state['legend_set'] = True

        # --- Timing precision ---
        if len(onset) > 1:
            dt = np.diff(onset)
            timing_err = (dt - expected_interval) * 1000  # ms
            line_objects['timing'].set_data(onset[1:], timing_err)

        # Update cycle counter in title
        stim_mask = data['cycle_index'] >= 0
        if np.any(stim_mask):
            pairs = set(zip(data['block_index'][stim_mask],
                            data['cycle_index'][stim_mask]))
            if data['cycle_index'][-1] >= 0:
                completed = max(0, len(pairs) - 1)
            else:
                completed = len(pairs)
            total = state.get('total_cycles', '?')
            axes[0].set_title(
                f'Commanded amplitude — cycle {completed} of {total} completed',
                fontsize=10)
        else:
            axes[0].set_title('Commanded amplitude — baseline', fontsize=10)

        return []

    return update


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        filepath = find_latest_stim_file()
        if filepath is None:
            print('ERROR: No stim TSV files found in data/.')
            print('Usage: python qc_monitor.py [path/to/stim.tsv]')
            sys.exit(1)

    filepath = os.path.abspath(filepath)
    print(f'Monitoring: {filepath}')

    if not os.path.exists(filepath):
        print(f'ERROR: File not found: {filepath}')
        sys.exit(1)

    json_path = find_json_sidecar(filepath)
    sidecar = load_sidecar(json_path) if json_path else None
    if sidecar:
        print(f'Sidecar:   {json_path}')
        up = sidecar.get('up_first')
        direction = 'Up-first -> Down-first' if up else 'Down-first -> Up-first'
        print(f'Block:     {sidecar.get("block_type")} | {direction}')
        print(f'Peak:      {sidecar.get("max_amplitude")} mV, '
              f'Floor: {sidecar.get("ramp_floor", 0)} mV, '
              f'Rate: {sidecar.get("update_hz")} Hz')
    else:
        print('WARNING: No JSON sidecar found; using defaults.')

    fig, axes, ax0_ma, line_objects = create_figure(filepath, sidecar)

    # Derive expected interval and total cycles from sidecar
    update_hz = sidecar.get('update_hz', 8) if sidecar else 8
    if sidecar and 'cycles_per_half' in sidecar:
        total_cycles = int(sidecar['cycles_per_half']) * 2
    else:
        total_cycles = '?'

    state = {
        'expected_interval': 1.0 / update_hz,
        'total_cycles': total_cycles,
    }

    update_fn = make_update(filepath, axes, ax0_ma, line_objects, state)
    update_fn(0)

    ani = animation.FuncAnimation(fig, update_fn, interval=2000,
                                  cache_frame_data=False)
    plt.show()


if __name__ == '__main__':
    main()
