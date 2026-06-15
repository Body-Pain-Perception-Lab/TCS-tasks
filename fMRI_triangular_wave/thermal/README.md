# fMRI Thermal pRF (tprf) Experiment

Continuous triangular-wave thermal stimulation delivered via a 5-zone TCS thermode during fMRI scanning. Designed for thermal population receptive field (pRF) mapping, comparing **TGI** (Thermal Grill Illusion) and **Non-TGI** spatial patterns.

Built with **PsychoPy** (Python). Each run is executed as an independent invocation of the script.

> **Note:** The active configuration is `config_v3.py`. Previous versions are archived in `pilots/` and `config_v2.py`.

## Requirements

- Python 3.8+
- [PsychoPy](https://www.psychopy.org/) (with pyglet backend)
- NumPy, SciPy, matplotlib
- `TcsControl_python3` module (only needed when `simulation = False`)

## Quick Start (Simulation Mode)

```bash
python run_experiment.py
```

Set `simulation = True` and `emulate = True` in the GUI, then press **space** to start.

## Experimental Design

### Overview

Each session consists of **4 runs**, each containing **two halves** of 12 cycles with opposite waveform directions, separated by a 30-second mid-run pause at baseline temperature.

**Group A** (`nontgi_warm_first = True`):

| Run | Condition | Half 1 (12 cycles) | Pause | Half 2 (12 cycles) |
|-----|-----------|---------------------|-------|---------------------|
| 1   | NonTGI    | Warm-First          | 30s   | Cool-First          |
| 2   | NonTGI    | Cool-First          | 30s   | Warm-First          |
| 3   | TGI       | Warm-First          | 30s   | Cool-First          |
| 4   | TGI       | Cool-First          | 30s   | Warm-First          |

**Group B** (`nontgi_warm_first = False`): same but cool-first before warm-first in each pair.

### Run Structure

```
[6s dummy] → [6s baseline] → [12 x 28s cycles] → [30s pause] → [12 x 28s cycles] → [6s baseline]
```

- **Baseline**: all 5 zones held at 30 C
- **Stimulation**: triangular waveform with 2.5 C/s ramp rate, 17.5 C amplitude
- **Mid-run pause**: 30 seconds at baseline temperature between the two halves

### Triangular Waveform

Each 28s cycle contains one full bipolar triangle period:

```
delta        /\
(C)         /  \
 17.5      /    \
          /      \
         /        \
  0   --/          \----------
                    \        /
                     \      /
                      \    /
-17.5                  \  /
                        \/
        |--- 14s ---|--- 14s ---|
        |-------- 28s cycle ----|
```

Temperature for a warm (+1) zone: 30 → 47.5 → 30 → 12.5 → 30 C
Ramp rate: constant at 4 × 17.5 / 28 = **2.5 C/s**
Frequency: 1/28 = **0.0357 Hz**

- **Warm-first**: delta starts at 0 and rises (warm zones heat up first)
- **Cool-first**: phase-shifted by half-period (warm zones cool down first)

### Spatial Masks

Each mask defines how the 5 thermode zones respond to the delta waveform:
- `+1` = warm zone: `T = baseline + delta`
- `-1` = cool zone: `T = baseline - delta`
- ` 0` = neutral zone: `T = baseline`

| Mask | Z1  | Z2  | Z3  | Z4  | Z5  | Description |
|------|-----|-----|-----|-----|-----|-------------|
| P1   | +1  | +1  | +1  | +1  |  0  | NonTGI: all 4 zones in phase |
| TGI  | +1  | -1  | +1  | -1  |  0  | TGI: W-C alternating |

## Running the Experiment

### Main Experiment

```bash
python run_experiment.py
```

A single GUI dialog collects all parameters:
- Participant ID, session, run selection
- Body site (Arm / Leg)
- Max delta, serial port (auto-detected for your OS), simulation mode, fullscreen

The run plan is displayed at the top showing all 4 runs with their direction structure.

### Crash Recovery (Single Half)

If a run is interrupted mid-way:

```bash
python run_single_half.py
```

Runs a single half (12 cycles) with pre/post baselines. Choose the condition, direction, and run number manually. The JSON sidecar marks these as `run_type: single_half_recovery`.

### Pre-Check

```bash
python thermode_precheck.py
```

14-second test ramp to verify thermode tracking. Run after overheat events or between sessions.

### QC Monitor

Run in a second terminal while the experiment is running:

```bash
python qc_monitor.py
```

Live matplotlib dashboard showing zone temperatures and tracking error.

## Output Files

All output is saved under `data/sub-{ID}/ses-{session}/func/` in BIDS-compatible format. Each run produces:

| File | Description |
|------|-------------|
| `_events_<ts>.tsv` | Run phase timings and VAS ratings |
| `_thermode_<ts>.tsv` | 10 Hz thermode recording (columns defined in JSON sidecar) |
| `_thermode_<ts>.json` | JSON sidecar with column definitions and full config |
| `_qc_<ts>.tsv` | Per-cycle QC metrics |

## File Structure

```
thermal/
  config_v3.py              — Active configuration
  waveform.py               — Triangle wave generation + phase shifting + mask application
  masks.py                  — Spatial mask definitions (NonTGI and TGI)
  thermode.py               — TCS thermode hardware wrapper (real + simulation)
  thermode_precheck.py      — Pre-run thermode tracking check
  qc.py                     — Real-time QC + overheat detection
  qc_monitor.py             — Live matplotlib QC dashboard
  ratings.py                — VAS rating scales (keyboard-controlled, MRI-compatible)
  run_block.py              — Half execution (cycle loop, 10 Hz updates, logging)
  run_experiment.py         — Main entry point (GUI, trigger, two-half runner)
  run_single_half.py        — Crash recovery (single 12-cycle half)
  generate_design_matrix.py — GLM/pRF design matrices (post-processing)
  fourier_analysis.py       — Fourier analysis
  cluster_fourier/          — Cluster batch scripts for Fourier analysis
  check_setup.sh            — Environment and dependency checker
  docs/                     — TCS hardware manual
  pilots/                   — Archived pilot configs
  data/                     — Output directory (created automatically)
```

## Configuration Reference

All parameters are in `config_v3.py`. Key settings:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `baseline_temp` | 30.0 | Baseline temperature (C) |
| `temp_min` / `temp_max` | 10.0 / 50.0 | Safety clamp bounds (C) |
| `max_delta` | 17.5 | Waveform amplitude (C) |
| `ramp_rate` | 50.0 | TCS hardware ramp speed (C/s) |
| `cycle_duration` | 28.0 | Duration of one cycle (s) |
| `cycles_per_half` | 12 | Cycles per half (24 total per run) |
| `mid_run_pause` | 30.0 | Pause between halves (s) |
| `baseline_buffer` | 6.0 | Baseline duration before/after run (s) |
| `update_hz` | 10 | Thermode command frequency (Hz) |
| `TR` | 1.5 | Scanner repetition time (s) |
| `dummy_volumes` | 4 | Dummy volumes after trigger |
| `nontgi_warm_first` | `True` | Run order counterbalancing |
| `com_port` | `'COM3'` | TCS serial port (auto-detected in GUI) |
| `simulation` | `False` | Simulate thermode (no hardware) |
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
