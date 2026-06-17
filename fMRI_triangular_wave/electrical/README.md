# fMRI Electrical pRF (eprf) Experiment

Triangular-wave electrical stimulation delivered via a Digitimer DS5 constant current stimulator during fMRI scanning. Designed for electrical population receptive field (pRF) mapping of stimulus intensity.

Built with **PsychoPy** (Python). Same run structure as the thermal experiment.

> **Note:** The active configuration is `config_electric_L01.py`.

## Requirements

- Python 3.8+
- [PsychoPy](https://www.psychopy.org/) (with pyglet backend)
- NumPy, SciPy, matplotlib
- `pyserial` (for DS5 communication when `simulation = False`)
- `DS5Control_python3_BPPlab` (in `PythonHelpers/` at repo root)

## Quick Start (Simulation Mode)

```bash
python run_experiment.py
```

Set `simulation = True` and `emulate = True` in the GUI, then press **space** to start.

## Hardware

### Digitimer DS5

The DS5 is an isolated bipolar constant current stimulator controlled via USB serial (19200 baud). The hardware driver lives in `PythonHelpers/DS5Control_python3_BPPlab.py`.

This lab's DS5 is configured to:
- Input range: +/-10V -> +/-10mA (1 mA/V scaling)
- `current_mA = millivolts / 1000` (e.g. 2000 mV = 2.0 mA)
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
Total: 714s ~ 12 min (no extra baselines between halves — pause replaces them)
```

- **Baseline**: no stimulation (0 mV), DS5 amplitude zeroed for safety
- **Stimulation**: unipolar triangular waveform modulating pulse amplitude at 8 Hz
- **Mid-run pause**: 30 seconds with no stimulation between halves

### Triangular Waveform

Each 28s cycle contains one full unipolar triangle with a ramp floor (250 mV) to skip sub-threshold amplitudes. The waveform tiles seamlessly between cycles with 0 only at the very first and last sample of each half:

```
amplitude
(mV)           /\          /\          /\
 2000 (peak)  /  \        /  \        /  \
             /    \      /    \      /    \
            /      \    /      \    /      \
 250 (floor)        \  /        \  /        \
  0          |       --          --          |
             |<-- 28s -->|<-- 28s -->|<-- 28s -->|
             |  cycle 1  |  cycle 2  |  cycle 3  |
```

At each 125ms time step (8 Hz), the DS5 amplitude is set and a pulse is triggered. Timing is drift-compensated against block start.

- **Ramp-up first** (`up_first=True`): amplitude starts at floor and rises
- **Ramp-down first** (`up_first=False`): phase-shifted, starts at peak and falls

## Running the Experiment

### Main Experiment

```bash
python run_experiment.py
```

A single GUI dialog collects all parameters:
- Participant ID, session, run selection
- Body site (Arm / Leg)
- Max amplitude (mV), pulse width (ms)
- Serial port (auto-detected for your OS), trigger mode (parallel/keyboard)
- Simulation mode, emulate scanner, fullscreen

### Live QC Monitor

In a separate terminal while the experiment runs:

```bash
python qc_monitor.py                     # auto-detect latest stim file
python qc_monitor.py path/to/stim.tsv    # explicit file
```

Shows commanded amplitude (mV/mA) and timing precision in real time.

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
| `_stim_<ts>.tsv` | 8 Hz stimulation recording (9 columns, no header; defined in JSON sidecar) |
| `_stim_<ts>.json` | JSON sidecar with column definitions, ramp_floor, update_hz, full config |
| `_qc_<ts>.tsv` | Per-cycle QC metrics (timing precision, pulse counts) |

### Stimulation TSV Columns

`onset`, `volume`, `block_index`, `trial_type`, `cycle_index`, `direction`, `amplitude_mv`, `current_ma`, `pulse_width_ms`

### QC TSV Columns

`block_type`, `up_first`, `cycle_index`, `n_pulses`, `mean_amplitude`, `max_amplitude`, `mean_timing_error_ms`, `max_timing_error_ms`, `n_samples`

## File Structure

```
electrical/
  config_electric_L01.py  — Active configuration (Leipzig site)
  run_experiment.py       — Main entry point (GUI, trigger, two-half runner)
  run_block.py            — Half execution (8 Hz pulse loop, drift-compensated, logging)
  waveform.py             — Unipolar triangle wave with ramp_floor
  qc.py                   — Real-time QC (timing precision, pulse counts)
  qc_monitor.py           — Live matplotlib dashboard (amplitude + timing)
  ratings.py              — VAS rating scales (pain, tingling, sharpness)
  ds5.py                  — Leipzig pilot reference script (read-only)
  run_single_half.py      — Crash recovery (single 12-cycle half)
  test_single_pulse.py    — Interactive thresholding / DS5 testing tool
  data/                   — Output directory (created automatically)
```

DS5 hardware driver: `PythonHelpers/DS5Control_python3_BPPlab.py` (at repo root).

## Configuration Reference

All parameters are in `config_electric_L01.py`. Key settings:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `baseline_amplitude` | 0.0 | Baseline amplitude in mV (no stimulation) |
| `max_amplitude` | 2000.0 | Peak waveform amplitude in mV (set during thresholding) |
| `ramp_floor` | 250.0 | Minimum non-zero amplitude in mV (skip sub-threshold) |
| `pulse_width_ms` | 20.0 | Pulse width in milliseconds |
| `amp_min` / `amp_max` | 0.0 / 10000.0 | Safety clamp bounds (mV) |
| `cycle_duration` | 28.0 | Duration of one cycle (s) |
| `cycles_per_half` | 12 | Cycles per half (24 total per run) |
| `mid_run_pause` | 30.0 | Pause between halves (s) |
| `baseline_buffer` | 6.0 | Baseline duration before/after run (s) |
| `update_hz` | 8 | Pulse delivery frequency (Hz) |
| `TR` | 1.5 | Scanner repetition time (s) |
| `dummy_volumes` | 4 | Dummy volumes after trigger |
| `ramp_up_first` | `True` | Run order counterbalancing |
| `com_port` | `'/dev/ttyUSB0'` | DS5 serial port (Linux; auto-detected in GUI) |
| `trigger_mode` | `'keyboard'` | Scanner trigger (`'parallel'` at Leipzig) |
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
| **Total per run** | **714.0 s (~12 min) = 476 volumes** |
| **Total session (4 runs)** | **~48 min** (plus inter-run gaps) |
