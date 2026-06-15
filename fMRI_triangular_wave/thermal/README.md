# fMRI Thermal pRF (tprf) Experiment

Continuous triangular-wave thermal stimulation delivered via a 5-zone TCS thermode during fMRI scanning. Designed for thermal population receptive field (pRF) mapping, comparing **TGI** (Thermal Grill Illusion) and **Non-TGI** spatial patterns.

Built with **PsychoPy** (Python). Each run is executed as an independent invocation of the script, giving the experimenter full control over inter-run timing.

> **Note:** The active configuration is `config_v3.py`. Previous versions are archived in `pilots/` (`config.py`, `config_v1.py`) and `config_v2.py`.

## Requirements

- Python 3.8+
- [PsychoPy](https://www.psychopy.org/) (with pyglet backend)
- NumPy
- `TcsControl_python3` module (only needed when `simulation = False`)

## Quick Start (Simulation Mode)

```bash
python run_experiment.py
```

Default settings in `config_v3.py` have `simulation = False` and `emulate = False`. For testing without hardware, set `simulation = True` and `emulate = True`, then press **space** to start after the trigger prompt.

## Experimental Design

### Overview

Each session consists of **8 runs**, run one at a time. Each unique condition × direction is presented **twice** for reproducibility and SNR.

**Group A** (`nontgi_warm_first = True`):

| Run | Condition | Sweep direction |
|-----|-----------|-----------------|
| 1   | NonTGI    | warm-first      |
| 2   | NonTGI    | cool-first      |
| 3   | NonTGI    | warm-first      |
| 4   | NonTGI    | cool-first      |
| 5   | TGI       | warm-first      |
| 6   | TGI       | cool-first      |
| 7   | TGI       | warm-first      |
| 8   | TGI       | cool-first      |

**Group B** (`nontgi_warm_first = False`): same but cool-first before warm-first in each pair.

### Run Structure

```
[6s baseline] → [12 x 28s stimulation cycles] → [6s baseline]
```

- **Baseline**: all 5 zones held at 30 C
- **Stimulation**: triangular waveform with 2.5 C/s ramp rate, 17.5 C amplitude (temperature range: 12.5–47.5 C)

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
- **Cool-first**: phase-shifted by half-period (warm zones cool down first). Both directions are needed within-subject to cancel HRF delay in phase-encoding analysis.

### Spatial Masks

Each mask defines how the 5 thermode zones respond to the delta waveform:
- `+1` = warm zone: `T = baseline + delta`
- `-1` = cool zone: `T = baseline - delta`
- ` 0` = neutral zone: `T = baseline`

**Non-TGI mask** (uniform polarity, all 4 active zones; same for all participants):

| Mask | Z1  | Z2  | Z3  | Z4  | Z5  | Description |
|------|-----|-----|-----|-----|-----|-------------|
| P1   | +1  | +1  | +1  | +1  |  0  | All 4 zones in phase |

**TGI mask** (alternating warm/cool; same for all participants):

| Mask | Z1  | Z2  | Z3  | Z4  | Z5  | Description |
|------|-----|-----|-----|-----|-----|-------------|
| TGI  | +1  | -1  | +1  | -1  |  0  | W-C alternating |

Polarity reversal is handled by the warm-first/cool-first waveform direction, so no separate _W/_C mask variants are needed.

## Running the Experiment

### Step-by-Step

1. **Edit `config_v3.py`** before the session to set participant-specific parameters:
   - `nontgi_mask`: `'P1'` (all 4 zones, same for all participants)
   - `tgi_mask`: `'TGI'` (same for all participants)
   - `nontgi_warm_first`: `True` (Group A) or `False` (Group B)
   - `com_port`: serial port for the TCS thermode
   - `simulation`: set to `False` for real thermode control

2. **Run the script**:
   ```bash
   python run_experiment.py
   ```

3. **Dialog 1 — Participant Info**: enter participant ID (e.g. `0001`) and session number (e.g. `01`).

4. **Dialog 2 — Run Selection**: the GUI displays the 8-run plan with per-run timing (236 volumes, 5m 54s) and completion status:
   ```
   --- Block Plan (8 runs) ---
   Per run: 236 volumes, 5m 54s (12 cycles x 28s, 6s baseline)

     Run 1 (run-01): NonTGI  P1  W-first  [DONE]
     Run 2 (run-02): NonTGI  P1  C-first  [--]
     ...
     Run 8 (run-08): TGI  TGI  C-first  [--]

     1/8 runs completed
   ```
   Select the run (defaults to the next pending one). Confirm hardware settings (COM port, simulation mode, emulate scanner, fullscreen).

5. **Scanner trigger**: the PsychoPy window shows "Waiting for scanner trigger...". In emulation mode, press **space**. In scanner mode, the script waits for the configured trigger key (`t` by default). After the trigger, it waits for dummy volumes (4 x 1.5s = 6s).

6. **Stimulation runs** with a fixation circle at screen centre. Experimenter status is shown at the bottom of the screen. Press **Escape** to abort.

7. **VAS ratings** (if enabled): 3 questions presented sequentially. Use **left/right arrows** to move the cursor, **up arrow** to confirm. 8s timeout per question.

8. **Run complete**: data is saved and the script exits. Run the script again for the next run.

### Between Runs

Take as much time as needed between runs. The script is designed to be invoked once per run — simply run `python run_experiment.py` again when ready. The run plan summary will show which runs are already done.

### Re-running a Run

If you need to re-run a completed run, select it from the dropdown. A warning will be printed but the run will proceed. Data is saved with a unique timestamp, so previous data is never overwritten.

## Output Files

All output is saved under `data/sub-{ID}/ses-{session}/func/` in BIDS-compatible format. Each run produces 4 files:

### `_events_<timestamp>.tsv`

BIDS events file with run phase timings and VAS ratings.

| Column | Description |
|--------|-------------|
| onset | Seconds from scanner trigger |
| duration | Event duration in seconds |
| trial_type | `baseline`, `stimulation`, or `rating_{question}` |
| block_type | `NonTGI` or `TGI` |
| mask_name | Mask used (e.g. `P1`, `TGI`) |
| warm_first | `1` (warm-first) or `0` (cool-first) |
| response_value | VAS rating (0-100) or `n/a` |
| response_time | Reaction time in seconds or `n/a` |

### `_thermode_<timestamp>.tsv`

10 Hz thermode recording (no header; columns defined in the JSON sidecar).

Columns: `onset`, `volume`, `block_index`, `block_type`, `cycle_index`, `mask_name`, `warm_first`, `delta`, `zone1_set` ... `zone5_set`, `zone1_actual` ... `zone5_actual`

### `_thermode_<timestamp>.json`

JSON sidecar for the thermode TSV. Contains column definitions and all experiment parameters (sampling frequency, temperatures, timing, mask, etc.).

### `_qc_<timestamp>.tsv`

Per-cycle quality control metrics.

| Column | Description |
|--------|-------------|
| onset_latency_s | Delay between commanded and actual temperature change |
| mean_ramp_rate | Mean actual ramp rate (target: 2.5 C/s) |
| std_ramp_rate | Ramp rate variability |
| mean_warming_rate | Mean ramp rate during warming phases |
| mean_cooling_rate | Mean ramp rate during cooling phases |
| warming_cooling_diff | Asymmetry between warming and cooling rates |
| mean_temp_error | Mean absolute error between commanded and actual temps |
| max_temp_error | Maximum temperature error in the cycle |
| n_ramp_flags | Number of samples where ramp rate deviated > 0.3 C/s from target |
| n_samples | Total samples in the cycle |

## Real-Time QC Monitor

A live matplotlib dashboard for monitoring thermode performance during the experiment. Run it in a **second terminal** while the experiment is running.

### Usage

```bash
# Auto-detect the latest thermode file in data/
python qc_monitor.py

# Or specify a file explicitly
python qc_monitor.py data/sub-0001/ses-01/func/sub-0001_ses-01_task-tprf_run-01_thermode_20260227T140000.tsv
```

### Dashboard Panels

1. **Zone temperatures** — actual thermode readings (prominent) with commanded temperatures as faint reference lines, per active zone
2. **Temperature error** — |commanded - actual| per active zone, with 2°C warning threshold

The dashboard updates every 2 seconds by re-reading the TSV file. Thermode data is flushed to disk every ~1 second (every 10 samples at 10 Hz) so the monitor stays current.

### Requirements

- matplotlib (included with PsychoPy)
- numpy

## File Structure

```
thermal/
  config_v3.py           — Active configuration (v3: 4-zone NonTGI mask)
  config_v2.py           — Previous config (2-zone NonTGI mask)
  pilots/                — Archived pilot configs (config.py, config_v1.py)
  waveform.py            — Triangle wave generation + phase shifting + mask application
  masks.py               — Spatial mask definitions (NonTGI and TGI)
  thermode.py            — TCS thermode hardware wrapper (real + simulation mode)
  thermode_precheck.py   — Pre-run thermode tracking check
  qc.py                  — Real-time quality control + overheat detection
  qc_monitor.py          — Live matplotlib QC dashboard (run in second terminal)
  ratings.py             — VAS rating scales (keyboard-controlled, MRI-compatible)
  run_block.py           — Single block execution (cycle loop, 10Hz updates, logging)
  run_experiment.py      — Main entry point (GUI, trigger, block runner)
  generate_design_matrix.py — GLM/pRF design matrices (post-processing)
  fourier_analysis.py    — Fourier analysis
  cluster_fourier/       — Cluster batch scripts for Fourier analysis
  docs/                  — TCS hardware manual
  data/                  — Output directory (created automatically)
  README.md              — This file
```

## Configuration Reference

All parameters are in `config_v3.py`. Key settings:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `baseline_temp` | 30.0 | Baseline temperature (C) |
| `temp_min` / `temp_max` | 10.0 / 50.0 | Safety clamp bounds (C) |
| `max_delta` | 17.5 | Waveform amplitude (C) |
| `ramp_rate` | 50.0 | TCS hardware ramp speed in follow mode (C/s) |
| `cycle_duration` | 28.0 | Duration of one stimulation cycle (s) |
| `cycles_per_block` | 12 | Number of cycles per run |
| `baseline_buffer` | 6.0 | Baseline duration before/after stimulation (s) |
| `update_hz` | 10 | Thermode command update frequency (Hz) |
| `TR` | 1.5 | Scanner repetition time (s) |
| `dummy_volumes` | 4 | Dummy volumes to discard after trigger |
| `trigger_key` | `'t'` | Scanner trigger key |
| `nontgi_mask` | `'P1'` | NonTGI mask (all 4 zones) |
| `tgi_mask` | `'TGI'` | TGI mask (same for all participants) |
| `nontgi_warm_first` | `True` | Run order counterbalancing |
| `com_port` | `'COM3'` | TCS thermode serial port |
| `simulation` | `False` | Simulate thermode (no hardware) |
| `vas_enabled` | `False` | Show VAS ratings after each run |
| `fullscreen` | `True` | Fullscreen display (set `True` for scanner) |

## Counterbalancing

Counterbalancing across participants:

- **Run order** (between-subjects): `nontgi_warm_first = True` (Group A) runs warm-first before cool-first in each pair; `False` (Group B) reverses the order. NonTGI runs always precede TGI runs.

Both sweep directions (warm-first and cool-first) are run within-subject to enable cancellation of HRF delay in phase-encoding analysis.

## Timing Summary

| Phase | Duration |
|-------|----------|
| Dummy volumes | 6.0 s (4 x 1.5s TR) |
| Pre-run baseline | 6.0 s |
| Stimulation (12 cycles x 28s) | 336.0 s |
| Post-run baseline | 6.0 s |
| **Total per run** | **354.0 s (5 min 54s) = 236 volumes** |
| **Total session (8 runs)** | **~47 min** (plus inter-run gaps) |
