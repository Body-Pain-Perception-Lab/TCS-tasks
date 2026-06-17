# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

fMRI population receptive field (pRF) experiment with two stimulation modalities. Built with Python 3.8+ and PsychoPy.

- **`fMRI_triangular_wave/thermal/`** — Thermal pRF: continuous triangular-wave stimulation via a 5-zone TCS II.1 thermode. Compares TGI and Non-TGI spatial temperature patterns.
- **`fMRI_triangular_wave/electrical/`** — Electrical pRF: triangular-wave amplitude modulation via Digitimer DS5 constant current stimulator.

Shared documentation lives in `docs/` at the repo root.

## Folder Structure

```
PythonHelpers/                  # Shared hardware drivers
│   ├── TcsControl_python3_BPPlab.py  # TCS II.1 thermode driver
│   └── DS5Control_python3_BPPlab.py  # Digitimer DS5 stimulator driver
fMRI_triangular_wave/
├── thermal/                # Thermal stimulation experiment
│   ├── config_thermal_L01.py  # Active config — Leipzig site (CONFIG dict)
│   ├── run_experiment.py   # Main entry point (full run or single half recovery)
│   ├── run_block.py        # 10 Hz control loop (one half)
│   ├── io_utils.py         # Shared BIDS output and I/O helpers
│   ├── waveform.py         # Bipolar triangle wave generation
│   ├── masks.py            # Spatial mask definitions (NonTGI, TGI)
│   ├── thermode.py         # TCS hardware wrapper (imports TcsControl from PythonHelpers)
│   ├── thermode_precheck.py # Pre-run thermode tracking check
│   ├── qc.py               # Real-time QC + overheat detection
│   ├── qc_monitor.py       # Live matplotlib dashboard
│   ├── ratings.py          # Post-block VAS scales
│   ├── analysis/           # Post-processing scripts
│   │   ├── generate_design_matrix.py  # GLM/pRF design matrices
│   │   ├── fourier_analysis.py # Fourier analysis
│   │   └── cluster_fourier/    # Cluster batch scripts for Fourier
│   ├── check_setup.sh      # Environment and dependency checker
│   ├── data/               # BIDS output (per-participant)
│   ├── pilots/             # Archived pilot configs (config.py, config_v1.py, config_v2.py, config_v3.py)
│   ├── docs/               # TCS hardware manual
│   ├── SESSION_GUIDE.md    # Step-by-step session instructions
│   └── README.md
├── electrical/             # Electrical stimulation experiment
│   ├── config_electric_L01.py # Active config — Leipzig site (CONFIG dict)
│   ├── run_experiment.py   # Main entry point (4 runs, 2 halves each)
│   ├── run_block.py        # 8 Hz pulse delivery loop (one half, drift-compensated)
│   ├── waveform.py         # Unipolar triangle wave with ramp_floor
│   ├── qc.py               # Real-time QC (timing precision)
│   ├── qc_monitor.py       # Live matplotlib dashboard
│   ├── ratings.py          # Post-block VAS scales
│   ├── ds5.py              # Leipzig pilot reference script (DO NOT MODIFY)
│   ├── run_single_half.py  # Crash recovery (single 12-cycle half)
│   ├── test_single_pulse.py # Interactive thresholding tool
│   ├── data/               # BIDS output (per-participant)
│   └── README.md
docs/                       # Shared documentation (DS5 manual, etc.)
```

## Running the Experiments

### Thermal

```bash
cd fMRI_triangular_wave/thermal

# Main experiment (run once per run, 4 runs per session)
# GUI offers "Full run" or "Single half recovery" mode
python run_experiment.py

# Pre-check thermode tracking
python thermode_precheck.py

# Live QC dashboard (separate terminal, while experiment runs)
python qc_monitor.py

# Generate GLM/pRF design matrices (post-processing)
python analysis/generate_design_matrix.py --sub 0001 --ses 01
```

### Electrical

```bash
cd fMRI_triangular_wave/electrical

# Main experiment (run once per run, 4 runs per session)
python run_experiment.py

# Live QC dashboard (separate terminal, while experiment runs)
python qc_monitor.py

# Crash recovery (single 12-cycle half)
python run_single_half.py

# Interactive thresholding (before session)
python test_single_pulse.py --sim
```

For testing without hardware, set `simulation = True` and `emulate = True` in the GUI, then press **space** to simulate scanner trigger.

## Shared Architecture

Both modalities share the same run structure and execution flow:

**Run structure** (each of 4 runs — thermal example at 10 Hz):
```
[6s dummy] → [6s baseline] → [12 x 28s cycles] → [30s pause] → [12 x 28s cycles] → [6s baseline]
Total: 714s ≈ 12 min (no extra baselines between halves — pause replaces them)
```

**Execution flow:** `run_experiment.py` → single GUI dialog (choose full run or single half recovery) → init hardware → wait for scanner trigger → `run_block.py` (Half 1) → [full run only: mid-run pause → `run_block.py` (Half 2)] → VAS ratings → save BIDS output.

**GUI** (identical layout for both modalities):
- Participant ID, session, run selection
- Body site (Arm / Leg)
- Modality-specific parameters (max delta / max amplitude, serial port)
- Simulation, emulate scanner, fullscreen
- Serial port auto-detected from OS (Windows/Linux/macOS)

## Thermal-Specific Details

Key modules:
- **config_thermal_L01.py** — Single `CONFIG` dict with all parameters (thermal, timing, scanner, masks, hardware, display)
- **run_experiment.py** — Main entry point: single GUI with run mode selector (full run or single half recovery), block plan, trigger wait, orchestrates halves + mid-run pause + ratings + file saving
- **run_block.py** — Real-time 10 Hz loop: applies waveform to thermode zones, logs thermode data (TSV), tracks QC per cycle. Supports `include_pre_baseline` / `include_post_baseline` for half-level control.
- **waveform.py** — Pure numpy functions: `generate_delta_waveform()`, `phase_shift_waveform()`, `apply_mask()`
- **masks.py** — Static dict of spatial masks defining zone polarity (+1 warm, -1 cool, 0 neutral)
- **thermode.py** — `ThermodeController` class wrapping TCS II.1 hardware with simulation fallback. Imports `TcsControl_python3_BPPlab` from `PythonHelpers/`.
- **qc.py** — `ThermalQC` class: per-sample metrics, per-cycle summaries, sustained overheat detection (rolling 5s window)
- **qc_monitor.py** — Standalone matplotlib dashboard: polls thermode TSV every 2s, plots zone temps + error. Handles both old (single-block) and new (two-half) data formats.
- **ratings.py** — `collect_vas_ratings()`: post-block VAS scales using pyglet keyboard handler (8s timeout). Questions: cold, warm, burning intensity.

**Module dependency graph:**
```
config_thermal_L01 → waveform → run_block → run_experiment
                     masks ──────────────→ run_experiment
                     thermode ──→ run_block, run_experiment
                     qc ────────→ run_block
                     ratings ──────────────→ run_experiment
```

**Waveform**: bipolar triangle (0 → +max_delta → 0 → -max_delta → 0). Applied to 5 zones via spatial masks.

**Run plan** (4 runs, counterbalanced by `nontgi_warm_first`):
- Runs 1-2: NonTGI (mask P1: all 4 zones in phase)
- Runs 3-4: TGI (mask TGI: alternating warm/cool)
- Each run: Half 1 in one direction → 30s pause → Half 2 in opposite direction

## Electrical-Specific Details

Key modules:
- **config_electric_L01.py** — Single `CONFIG` dict (amplitude, pulse width, DS5 settings, timing)
- **run_experiment.py** — Same structure as thermal but for DS5. Imports `DS5Controller` from `PythonHelpers/DS5Control_python3_BPPlab.py`.
- **run_block.py** — 8 Hz loop: set DS5 amplitude → trigger pulse → log data. Drift-compensated timing against block start. Zeros DS5 amplitude during baseline for safety.
- **waveform.py** — Unipolar triangle wave: `generate_amplitude_waveform()` with `ramp_floor` support. Waveform tiles seamlessly (floor→peak→floor) with 0 bookends only at the start/end of each half.
- **qc.py** — `ElectricalQC` class: per-cycle timing precision, pulse counts
- **qc_monitor.py** — Standalone matplotlib dashboard: polls stim TSV every 2s, plots commanded amplitude (mV) + current (mA) + timing error.
- **ratings.py** — VAS questions: pain, tingling, sharpness intensity
- **ds5.py** — Leipzig pilot reference script (**read-only, do not modify**)
- **test_single_pulse.py** — Interactive tool for determining perceptual threshold

**DS5 stimulation parameters** (from Leipzig pilot):
- Pulse rate: 8 Hz, Peak: 2000 mV (2.0 mA), Floor: 250 mV, Pulse width: 20 ms
- Waveform per cycle: floor → peak → floor (seamless tiling, no inter-cycle zeros)
- DS5 range: ±10V input → ±10mA output (1 mA/V). `current_mA = millivolts / 1000`. Full scale = 10000 mV = 10 mA.

**Module dependency graph:**
```
config_electric_L01 → waveform → run_block → run_experiment
                      DS5Control (PythonHelpers) → run_experiment
                      qc ────────→ run_block
                      ratings ──────────────→ run_experiment
```

**Output columns** (stim TSV, 9 columns — no header, defined in JSON sidecar):
`onset, volume, block_index, trial_type, cycle_index, direction, amplitude_mv, current_ma, pulse_width_ms`

**Run plan** (4 runs, counterbalanced by `ramp_up_first`):
- All runs: electrical condition (single channel, no spatial masks)
- `up_first=True`: Half 1 ramps up, Half 2 ramps down
- `up_first=False`: Half 1 ramps down, Half 2 ramps up
- Runs alternate: Run 1 up-down, Run 2 down-up, Run 3 up-down, Run 4 down-up

## Multi-Site Configuration

Both experiments support multiple sites. Serial port is auto-detected from the OS in the GUI dialog.

Thermal-specific multi-site settings in `config_thermal_L01.py`:

| Setting | Home site (Windows) | Leipzig 7T (Linux) |
|---------|--------------------|--------------------|
| `com_port` | `'COM3'` | `'/dev/ttyACM0'` |
| `trigger_mode` | `'keyboard'` | `'parallel'` |
| `trigger_key` | `'t'` | (not used) |
| `parallel_port` | (not used) | `0` |
| `tcs_filter` | `None` | `'medium'` |

Electrical-specific multi-site settings in `config_electric_L01.py`:

| Setting | Home site (Windows) | Leipzig (Linux) |
|---------|--------------------|--------------------|
| `com_port` | `'COM8'` | `'/dev/ttyUSB0'` |
| `trigger_mode` | `'keyboard'` | `'parallel'` |
| `parallel_port` | (not used) | `0` |

- **Scanner trigger**: `'keyboard'` mode uses `event.waitKeys()`. `'parallel'` mode waits for a falling edge on the parallel port Acknowledge pin (requires `parallel` module). In emulation mode, both fall back to space bar.
- **TCS MRI filter**: Set `tcs_filter` to `'medium'` at Leipzig. `set_filter()` is included in `TcsControl_python3_BPPlab`.
- **Hardware drivers**: Both `TcsControl_python3_BPPlab.py` and `DS5Control_python3_BPPlab.py` live in `PythonHelpers/` at the repo root. Experiment scripts add this directory to `sys.path` at import time.

## Key Design Constraints

- **Real-time control loop** in `run_block.py` runs at 10 Hz (thermal) or 8 Hz (electrical). Changes must preserve timing precision. Electrical uses drift-compensated timing against block start.
- **Safety clamping**: thermal temps clamped to 10–50 C in `waveform.apply_mask()`. Electrical amplitude clamped to 0–10000 mV in `waveform.clamp_amplitude()`.
- **One invocation per run**: the script exits after each run. Completion is tracked by scanning for existing output files.
- **Data is never overwritten**: each output file includes a timestamp.
- **Hardware abstraction**: `ThermodeController` and `DS5Controller` both support simulation mode via the same interface pattern. Both hardware drivers live in `PythonHelpers/`.
- **Config traceability**: the JSON sidecar saves the full `config` dict as used at runtime.
- **Keyboard handling**: uses `psychopy.event.waitKeys()` / `event.getKeys()` (not `psychopy.hardware.keyboard`) to avoid psychtoolbox dependency issues on macOS.

## Output Format

### Thermal
BIDS-compatible files in `thermal/data/sub-{ID}/ses-{session}/func/` (task: `tprf`):
- `_events_<timestamp>.tsv` — run phases + VAS ratings
- `_thermode_<timestamp>.tsv` — 10 Hz thermode recording (no header; see JSON sidecar)
- `_thermode_<timestamp>.json` — column definitions + full experiment config + body_site
- `_qc_<timestamp>.tsv` — per-cycle QC metrics (includes `overheat_flagged` column)

### Electrical
BIDS-compatible files in `electrical/data/sub-{ID}/ses-{session}/func/` (task: `eprf`):
- `_events_<timestamp>.tsv` — run phases + VAS ratings
- `_stim_<timestamp>.tsv` — 8 Hz stimulation recording (no header; 9 columns defined in JSON sidecar: onset, volume, block_index, trial_type, cycle_index, direction, amplitude_mv, current_ma, pulse_width_ms)
- `_stim_<timestamp>.json` — column definitions + full experiment config + body_site + ramp_floor + update_hz
- `_qc_<timestamp>.tsv` — per-cycle QC metrics (timing precision, pulse counts)

## Dependencies

- PsychoPy (with pyglet backend), NumPy, matplotlib, scipy
- `pyserial` — needed for both TCS thermode and DS5 stimulator (when `simulation = False`)
- `TcsControl_python3_BPPlab` (in `PythonHelpers/`) — thermal only, when `simulation = False`
- `DS5Control_python3_BPPlab` (in `PythonHelpers/`) — electrical only, when `simulation = False`
- `parallel` — only needed when `trigger_mode = 'parallel'` (Leipzig 7T)
- Requirements listed in `requirements.txt` at repo root
