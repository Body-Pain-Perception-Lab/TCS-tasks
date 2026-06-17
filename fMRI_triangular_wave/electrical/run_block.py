"""
Core block execution: cycle loop with 10Hz DS5 pulse delivery and logging.

Each half uses a single waveform direction. At each 100ms time step,
the DS5 amplitude is set and a pulse is triggered.
"""

from psychopy import core, event, visual

from waveform import generate_amplitude_waveform, phase_shift_waveform, clamp_amplitude
from qc import ElectricalQC


def run_block(block_idx, block_type, warm_first,
              n_blocks, ds5, win, global_clock, trigger_time,
              physio_writer, config, physio_file=None,
              include_pre_baseline=True, include_post_baseline=True):
    """Run one stimulation half (cycles_per_half cycles).

    Parameters
    ----------
    block_type : str
        Condition label (e.g. 'electrical').
    warm_first : bool
        If True, waveform starts ramping up; if False, starts ramping down.
    include_pre_baseline : bool
        If True, run baseline period before stimulation.
    include_post_baseline : bool
        If True, run baseline period after stimulation.

    Returns
    -------
    dict with keys:
        timings : list of dict
        qc_summaries : list of dict
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

    # Generate waveform
    waveform = generate_amplitude_waveform(cycle_duration, update_hz,
                                           config['max_amplitude'],
                                           config.get('ramp_floor', 0.0))
    if not warm_first:
        waveform = phase_shift_waveform(waveform)

    # Fixation point
    fixation = visual.Circle(win, radius=0.01, edges=32,
                             lineColor='white', fillColor='lightGrey',
                             pos=(0, 0))

    status_text = visual.TextStim(win, text='', pos=(0, -0.35), height=0.03,
                                  color='grey', wrapWidth=1.8)
    direction = 'ramp-up' if warm_first else 'ramp-down'

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
                             warm_first, n_blocks, physio_file=physio_file)
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

    for cycle_idx in range(total_cycle_count):
        cycle_clock = core.Clock()
        qc.start_cycle(cycle_idx)

        if cycle_idx == n_full_cycles and extra_samples > 0:
            n_samples_this_cycle = extra_samples
        else:
            n_samples_this_cycle = samples_per_cycle

        for sample_idx in range(n_samples_this_cycle):
            target_time = sample_idx * sample_interval

            amplitude = float(waveform[sample_idx])
            amplitude = clamp_amplitude(amplitude,
                                        config['amp_min'], config['amp_max'])

            # Deliver pulse
            ds5.set_amplitude(amplitude)
            ds5.trigger()

            t_now = global_clock.getTime()
            t_from_trigger = t_now - trigger_time
            volume = int(t_from_trigger / config['TR']) + 1

            qc.update(t_from_trigger, amplitude)

            # Write data row
            physio_writer.writerow([
                f'{t_from_trigger:.4f}',
                volume,
                block_idx,
                block_type,
                cycle_idx,
                int(warm_first),
                f'{amplitude:.2f}',
                f'{config["pulse_width_ms"]:.1f}',
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
                f"Amp={amplitude:.0f} mV"
            )
            status_text.draw()
            win.flip()

            keys = event.getKeys(keyList=['escape'])
            if keys:
                raise KeyboardInterrupt("Escape pressed")

            elapsed = cycle_clock.getTime() - target_time
            wait_time = sample_interval - elapsed
            if wait_time > 0:
                core.wait(wait_time)

        # End-of-cycle QC
        cycle_summary = qc.end_cycle()
        partial_tag = ' (partial)' if cycle_idx == n_full_cycles else ''
        print(f'  Cycle {cycle_idx + 1}/{total_cycle_count}{partial_tag} QC: '
              f'pulses={cycle_summary["n_pulses"]}, '
              f'mean_amp={cycle_summary["mean_amplitude"]:.1f} mV, '
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
                             warm_first, n_blocks, label='Post-block baseline',
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
                         block_idx, block_type, warm_first,
                         n_blocks, label='Baseline', physio_file=None):
    """Hold zero amplitude for a specified duration (no pulses delivered)."""
    update_hz = config['update_hz']
    sample_interval = 1.0 / update_hz
    n_samples = int(duration * update_hz)

    baseline_clock = core.Clock()

    for i in range(n_samples):
        target_time = i * sample_interval

        t_now = global_clock.getTime()
        t_from_trigger = t_now - trigger_time
        volume = int(t_from_trigger / config['TR']) + 1

        physio_writer.writerow([
            f'{t_from_trigger:.4f}',
            volume,
            block_idx,
            'baseline',
            -1,
            int(warm_first),
            '0.00',
            f'{config["pulse_width_ms"]:.1f}',
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

        elapsed = baseline_clock.getTime() - target_time
        wait_time = sample_interval - elapsed
        if wait_time > 0:
            core.wait(wait_time)
