"""
Core block execution: cycle loop with DS5 pulse delivery and logging.

DS5 stimulation parameters (from Leipzig pilot ds5.py):
    Pulse rate:      8 Hz (pulses/second — temporal summation)
    Peak amplitude:  2000 mV (= 2.0 mA on the DS5 ±10V:±10mA range)
    Ramp floor:      250 mV (skip imperceptible sub-threshold levels)
    Pulse width:     20 ms
    Waveform:        unipolar triangle with floor
                     0 → floor..peak..floor → 0 per cycle
    DS5 current:     current_mA = millivolts / 1000

Each half uses a single waveform direction. At each time step the DS5
amplitude is set, a pulse is triggered, and the commanded amplitude is
logged. Timing is drift-compensated against the block start time (not
per-cycle) to prevent accumulated drift across cycles.

Output columns match the thermal thermode TSV for consistency:
    time, volume, block_idx, trial_type, cycle_idx, direction,
    amplitude_mV, current_mA, pulse_width_ms
"""

from psychopy import core, event, visual

from waveform import generate_amplitude_waveform, phase_shift_waveform, clamp_amplitude
from qc import ElectricalQC


def run_block(block_idx, block_type, up_first,
              n_blocks, ds5, win, global_clock, trigger_time,
              physio_writer, config, physio_file=None,
              include_pre_baseline=True, include_post_baseline=True):
    """Run one stimulation half (cycles_per_half cycles).

    Parameters
    ----------
    block_idx : int
        Half index (0 or 1).
    block_type : str
        Condition label (e.g. 'electrical').
    up_first : bool
        If True, waveform starts ramping up; if False, starts ramping down.
    n_blocks : int
        Total number of halves in the run (usually 2).
    ds5 : DS5Controller
        Hardware controller (or simulation stub).
    win : psychopy.visual.Window
        Display window.
    global_clock : psychopy.core.Clock
        Clock started at experiment launch.
    trigger_time : float
        Time of scanner trigger on global_clock.
    physio_writer : csv.writer
        Writer for the stimulation TSV file.
    config : dict
        Experiment configuration.
    physio_file : file, optional
        File handle for flushing.
    include_pre_baseline : bool
        If True, run baseline period before stimulation.
    include_post_baseline : bool
        If True, run baseline period after stimulation.

    Returns
    -------
    dict with keys:
        timings : list of dict
            Phase timings for the BIDS events file.
        qc_summaries : list of dict
            Per-cycle QC metrics.
    """
    import math

    cycles_total = config['cycles_per_half']
    n_full_cycles = int(cycles_total)
    frac = cycles_total - n_full_cycles
    update_hz = config['update_hz']
    cycle_duration = config['cycle_duration']
    sample_interval = 1.0 / update_hz
    samples_per_cycle = int(cycle_duration * update_hz)
    extra_samples = int(round(frac * samples_per_cycle))
    pulse_width_ms = config['pulse_width_ms']

    # Generate one seamless cycle (floor→peak→floor, no zeros between cycles)
    waveform = generate_amplitude_waveform(cycle_duration, update_hz,
                                           config['max_amplitude'],
                                           config.get('ramp_floor', 0.0))
    if not up_first:
        waveform = phase_shift_waveform(waveform)

    # First sample of first cycle and last sample of last cycle are forced
    # to 0 (silence bookends for the half). Inter-cycle samples stay at
    # floor..peak for a continuous stimulus.
    first_sample_zero = True
    last_sample_zero = True

    # Fixation point
    fixation = visual.Circle(win, radius=0.01, edges=32,
                             lineColor='white', fillColor='lightGrey',
                             pos=(0, 0))

    status_text = visual.TextStim(win, text='', pos=(0, -0.35), height=0.03,
                                  color='grey', wrapWidth=1.8)
    direction = 'ramp-up' if up_first else 'ramp-down'

    # QC tracker
    qc = ElectricalQC(config)
    timings = []

    # Clear stale key events
    event.clearEvents()

    # --- Pre-block baseline ---
    if include_pre_baseline:
        pre_onset = global_clock.getTime() - trigger_time
        _run_baseline_period(config['baseline_buffer'], ds5, win, fixation,
                             status_text, global_clock, trigger_time, config,
                             physio_writer, block_idx, block_type,
                             up_first, n_blocks, physio_file=physio_file)
        pre_end = global_clock.getTime() - trigger_time
        timings.append({
            'onset': pre_onset,
            'duration': pre_end - pre_onset,
            'trial_type': 'baseline',
        })

    # --- Stimulation cycles ---
    stim_onset = global_clock.getTime() - trigger_time
    flush_counter = 0
    total_cycle_count = math.ceil(cycles_total)

    # Block start time for drift-compensated scheduling
    t_block_start = global_clock.getTime()
    global_sample_idx = 0

    for cycle_idx in range(total_cycle_count):
        qc.start_cycle(cycle_idx)

        if cycle_idx == n_full_cycles and extra_samples > 0:
            n_samples_this_cycle = extra_samples
        else:
            n_samples_this_cycle = samples_per_cycle

        for sample_idx in range(n_samples_this_cycle):
            amplitude = float(waveform[sample_idx])

            # Silence bookends: first sample of half → 0, last sample of half → 0
            is_first = (cycle_idx == 0 and sample_idx == 0)
            is_last = (cycle_idx == total_cycle_count - 1
                       and sample_idx == n_samples_this_cycle - 1)
            if (is_first and first_sample_zero) or (is_last and last_sample_zero):
                amplitude = 0.0

            amplitude = clamp_amplitude(amplitude,
                                        config['amp_min'], config['amp_max'])
            current_mA = amplitude / 1000.0

            # Deliver pulse
            ds5.set_amplitude(amplitude)
            ds5.trigger()

            t_now = global_clock.getTime()
            t_from_trigger = t_now - trigger_time
            volume = int(t_from_trigger / config['TR']) + 1

            # Trial type label
            if amplitude > 0:
                trial_label = 'stimulation'
            else:
                trial_label = 'baseline'

            qc.update(t_from_trigger, amplitude)

            # Write data row (columns match thermal thermode TSV style)
            physio_writer.writerow([
                f'{t_from_trigger:.4f}',
                volume,
                block_idx,
                trial_label,
                cycle_idx,
                direction,
                f'{amplitude:.2f}',
                f'{current_mA:.4f}',
                f'{pulse_width_ms:.1f}',
            ])

            flush_counter += 1
            if physio_file is not None and flush_counter % 10 == 0:
                physio_file.flush()

            # Display
            fixation.draw()
            cycle_label = (f'{cycle_idx + 1}/{cycles_total}'
                           if cycle_idx < n_full_cycles
                           else f'{cycles_total}/{cycles_total}')
            status_text.text = (
                f"Half {block_idx + 1}/{n_blocks} [{block_type}] "
                f"({direction}) | "
                f"Cycle {cycle_label} | "
                f"Amp={amplitude:.0f} mV ({current_mA:.2f} mA)"
            )
            status_text.draw()
            win.flip()

            keys = event.getKeys(keyList=['escape'])
            if keys:
                raise KeyboardInterrupt("Escape pressed")

            # Drift-compensated wait against block start
            global_sample_idx += 1
            next_time = t_block_start + global_sample_idx * sample_interval
            wait_time = next_time - global_clock.getTime()
            if wait_time > 0:
                core.wait(wait_time)

        # End-of-cycle QC
        cycle_summary = qc.end_cycle()
        partial_tag = ' (partial)' if cycle_idx == n_full_cycles else ''
        print(f'  Cycle {cycle_idx + 1}/{total_cycle_count}{partial_tag} QC: '
              f'pulses={cycle_summary["n_pulses"]}, '
              f'mean_amp={cycle_summary["mean_amplitude"]:.1f} mV '
              f'({cycle_summary["mean_amplitude"] / 1000:.2f} mA), '
              f'timing_err={cycle_summary["mean_timing_error_ms"]:.2f} ms')

    stim_end = global_clock.getTime() - trigger_time
    timings.append({
        'onset': stim_onset,
        'duration': stim_end - stim_onset,
        'trial_type': 'stimulation',
    })

    # --- Post-block baseline ---
    if include_post_baseline:
        post_onset = global_clock.getTime() - trigger_time
        _run_baseline_period(config['baseline_buffer'], ds5, win, fixation,
                             status_text, global_clock, trigger_time, config,
                             physio_writer, block_idx, block_type,
                             up_first, n_blocks, label='Post-block baseline',
                             physio_file=physio_file)
        post_end = global_clock.getTime() - trigger_time
        timings.append({
            'onset': post_onset,
            'duration': post_end - post_onset,
            'trial_type': 'baseline',
        })

    return {
        'timings': timings,
        'qc_summaries': qc.get_block_summaries(),
    }


def _run_baseline_period(duration, ds5, win, fixation, status_text,
                         global_clock, trigger_time, config, physio_writer,
                         block_idx, block_type, up_first,
                         n_blocks, label='Baseline', physio_file=None):
    """Hold zero amplitude for a specified duration (no pulses delivered)."""
    ds5.set_amplitude(0)
    update_hz = config['update_hz']
    sample_interval = 1.0 / update_hz
    n_samples = int(duration * update_hz)
    direction = 'ramp-up' if up_first else 'ramp-down'
    pulse_width_ms = config['pulse_width_ms']

    t_baseline_start = global_clock.getTime()

    for i in range(n_samples):
        t_now = global_clock.getTime()
        t_from_trigger = t_now - trigger_time
        volume = int(t_from_trigger / config['TR']) + 1

        physio_writer.writerow([
            f'{t_from_trigger:.4f}',
            volume,
            block_idx,
            'baseline',
            -1,
            direction,
            '0.00',
            '0.0000',
            f'{pulse_width_ms:.1f}',
        ])

        if physio_file is not None and (i + 1) % 10 == 0:
            physio_file.flush()

        fixation.draw()
        status_text.text = (
            f"Half {block_idx + 1}/{n_blocks} [{block_type}] | {label}"
        )
        status_text.draw()
        win.flip()

        keys = event.getKeys(keyList=['escape'])
        if keys:
            raise KeyboardInterrupt("Escape pressed")

        # Drift-compensated wait against baseline start
        next_time = t_baseline_start + (i + 1) * sample_interval
        wait_time = next_time - global_clock.getTime()
        if wait_time > 0:
            core.wait(wait_time)
