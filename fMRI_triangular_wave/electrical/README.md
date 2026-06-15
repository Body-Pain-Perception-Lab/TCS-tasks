# fMRI Electrical pRF (eprf) Experiment

Triangular-wave electrical stimulation delivered via a Digitimer DS5 constant current stimulator during fMRI scanning. Designed for electrical population receptive field (pRF) mapping of stimulus intensity.

Built with **PsychoPy** (Python). Same run structure as the thermal experiment.

> **Note:** The active configuration is `config_v3.py`.

## Requirements

- Python 3.8+
- [PsychoPy](https://www.psychopy.org/) (with pyglet backend)
- NumPy, SciPy, matplotlib
- `pyserial` (for DS5 communication when `simulation = False`)

## Quick Start (Simulation Mode)

```bash
python run_experiment.py
```

Set `simulation = True` and `emulate = True` in the GUI, then press **space** to start.

## Hardware

### Digitimer DS5

The DS5 is an isolated bipolar constant current stimulator controlled via USB serial (19200 baud).

This lab's DS5 is configured to:
- Input range: +/-10V -> +/-10mA (1 mA/V scaling)
- `current_mA = millivolts / 1000` (e.g. 500 mV = 0.5 mA)
- Full scale: 10000 mV = 10 mA (do not exceed)

### Thresholding

Before the experiment, use the interactive thresholding tool to determine the participant's perceptual range:

```bash
python test_single_pulse.py --sim        # simulation mode
python test_single_pulse.py --port COM8  # with hardware
```

Controls: `Enter` to deliver a pulse, `+`/`-` to adjust amplitude, `q` to quit. Results are logged to `data/pulse_test_*.tsv`.

## Experimental Design

### Overview

Each session consists of **4 runs**, each containing **two halves** of 12 cycles with opposite waveform directions, separated by a 30-second mid-run pause.

| Run | Half 1 (12 cycles) | Pause | Half 2 (12 cycles) |
|-----|---------------------|-------|---------------------|
| 1   | Ramp-Up             | 30s   | Ramp-Down           |
| 2   | Ramp-Down           | 30s   | Ramp-Up             |
| 3   | Ramp-Up             | 30s   | Ramp-Down           |
| 4   | Ramp-Down           | 30s   | Ramp-Up             |

Counterbalanced with `ramp_up_first = False` to reverse the order.

### Run Structure

```
[6s dummy] -> [6s baseline] -> [12 x 28s cycles] -> [30s pause] -> [12 x 28s cycles] -> [6s baseline]
```

- **Baseline**: no stimulation (0 mV)
- **Stimulation**: unipolar triangular waveform modulating pulse amplitude at 10 Hz
- **Mid-run pause**: 30 seconds with no stimulation between halves

### Triangular Waveform

Each 28s cycle contains one full unipolar triangle:

```
amplitude
(mV)           /\
 max          /  \
             /    \
            /      \
           /        \
  0   ----/          \----
          |--- 14s ---|--- 14s ---|
          |-------- 28s cycle ----|
```

At each 100ms time step (10 Hz), the DS5 amplitude is set and a pulse is triggered.

- **Ramp-up first**: amplitude starts at 0 and rises
- **Ramp-down first**: phase-shifted, starts at max and falls

## Running the Experiment

### Main Experiment

```bash
python run_experiment.py
```

A single GUI dialog collects all parameters:
- Participant ID, session, run selection
- Body site (Arm / Leg)
- Max amplitude (mV), pulse width (ms)
- Serial port (auto-detected for your OS), simulation mode, fullscreen

### Crash Recovery (Single Half)

If a run is interrupted mid-way:

```bash
python run_single_half.py
```

Runs a single half (12 cycles) with pre/post baselines. The JSON sidecar marks these as `run_type: single_half_recovery`.

## Output Files

All output is saved under `data/sub-{ID}/ses-{session}/func/` in BIDS-compatible format (task label: `eprf`). Each run produces:

| File | Description |
|------|-------------|
| `_events_<ts>.tsv` | Run phase timings and VAS ratings |
| `_stim_<ts>.tsv` | 10 Hz stimulation recording (columns defined in JSON sidecar) |
| `_stim_<ts>.json` | JSON sidecar with column definitions and full config |
| `_qc_<ts>.tsv` | Per-cycle QC metrics (timing precision, pulse counts) |

### Stimulation TSV Columns

`onset`, `volume`, `block_index`, `block_type`, `cycle_index`, `warm_first`, `amplitude_mv`, `pulse_width_ms`

### QC TSV Columns

`block_type`, `warm_first`, `cycle_index`, `n_pulses`, `mean_amplitude`, `max_amplitude`, `mean_timing_error_ms`, `max_timing_error_ms`, `n_samples`

## File Structure

```
electrical/
  config_v3.py          — Active configuration
  ds5_controller.py     — DS5 hardware wrapper (serial interface)
  waveform.py           — Unipolar triangle wave generation
  qc.py                 — Real-time QC (timing precision, pulse counts)
  ratings.py            — VAS rating scales (pain, tingling, sharpness)
  run_block.py          — Half execution (10 Hz pulse loop, logging)
  run_experiment.py     — Main entry point (GUI, trigger, two-half runner)
  run_single_half.py    — Crash recovery (single 12-cycle half)
  test_single_pulse.py  — Interactive thresholding / DS5 testing tool
  docs/                 — DS5 reference scripts
  pilots/               — Archived pilot configs
  data/                 — Output directory (created automatically)
```

## Configuration Reference

All parameters are in `config_v3.py`. Key settings:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `baseline_amplitude` | 0.0 | Baseline amplitude in mV (no stimulation) |
| `max_amplitude` | 500.0 | Peak waveform amplitude in mV (set during thresholding) |
| `pulse_width_ms` | 0.5 | Pulse width in milliseconds |
| `amp_min` / `amp_max` | 0.0 / 10000.0 | Safety clamp bounds (mV) |
| `cycle_duration` | 28.0 | Duration of one cycle (s) |
| `cycles_per_half` | 12 | Cycles per half (24 total per run) |
| `mid_run_pause` | 30.0 | Pause between halves (s) |
| `baseline_buffer` | 6.0 | Baseline duration before/after run (s) |
| `update_hz` | 10 | Pulse delivery frequency (Hz) |
| `TR` | 1.5 | Scanner repetition time (s) |
| `dummy_volumes` | 4 | Dummy volumes after trigger |
| `ramp_up_first` | `True` | Run order counterbalancing |
| `com_port` | `'COM8'` | DS5 serial port (auto-detected in GUI) |
| `simulation` | `False` | Simulate DS5 (no hardware) |
| `fullscreen` | `False` | Fullscreen display (`True` for scanner) |

## Timing Summary

| Phase | Duration |
|-------|----------|
| Dummy volumes | 6.0 s (4 x 1.5s TR) |
| Pre-run baseline | 6.0 s |
| Half 1 (12 cycles x 28s) | 336.0 s |
| Mid-run pause | 30.0 s |
| Half 2 (12 cycles x 28s) | 336.0 s |
| Post-run baseline | 6.0 s |
| **Total per run** | **720.0 s (12 min) = 480 volumes** |
| **Total session (4 runs)** | **~48 min** (plus inter-run gaps) |
