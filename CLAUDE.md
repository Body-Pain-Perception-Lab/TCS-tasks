# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

fMRI population receptive field (pRF) experiment with two stimulation modalities. Built with Python 3.8+ and PsychoPy.

- **`fMRI_triangular_wave/thermal/`** — Thermal pRF: continuous triangular-wave stimulation via a 5-zone TCS II.1 thermode. Compares TGI and Non-TGI spatial temperature patterns.
- **`fMRI_triangular_wave/electrical/`** — Electrical pRF: triangular-wave amplitude modulation via Digitimer DS5 constant current stimulator.

Shared documentation lives in `docs/` at the repo root.

## Folder Structure

```
fMRI_triangular_wave/
├── thermal/                # Thermal stimulation experiment
│   ├── config_v3.py        # Active config (CONFIG dict)
│   ├── run_experiment.py   # Main entry point (full run or single half recovery)
│   ├── run_block.py        # 10 Hz control loop (one half)
│   ├── io_utils.py         # Shared BIDS output and I/O helpers
│   ├── waveform.py         # Bipolar triangle wave generation
│   ├── masks.py            # Spatial mask definitions (NonTGI, TGI)
│   ├── thermode.py         # TCS hardware wrapper
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
│   ├── pilots/             # Archived pilot configs (config.py, config_v1.py)
│   ├── docs/               # TCS hardware manual
│   ├── SESSION_GUIDE.md    # Step-by-step session instructions
│   └── README.md
├── electrical/             # Electrical stimulation experiment
│   ├── config_v3.py        # Active config (CONFIG dict)
│   ├── run_experiment.py   # Main entry point (4 runs, 2 halves each)
│   ├── run_single_half.py  # Crash recovery (single 12-cycle half)
│   ├── run_block.py        # 10 Hz pulse delivery loop (one half)
│   ├── waveform.py         # Unipolar triangle wave generation
│   ├── ds5_controller.py   # Digitimer DS5 hardware wrapper
│   ├── qc.py               # Real-time QC (timing precision)
│   ├── ratings.py          # Post-block VAS scales
│   ├── test_single_pulse.py # Interactive thresholding tool
│   ├── data/               # BIDS output (per-participant)
│   ├── docs/               # DS5 reference scripts
│   ├── pilots/             # Archived pilot configs
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

# Crash recovery (single 12-cycle half)
python run_single_half.py

# Interactive thresholding (before session)
python test_single_pulse.py --sim
```

For testing without hardware, set `simulation = True` and `emulate = True` in the GUI, then press **space** to simulate scanner trigger.

## Shared Architecture

Both modalities share the same run structure and execution flow:

**Run structure** (each of 4 runs):
```
[6s dummy] → [6s baseline] → [12 x 28s cycles] → [30s pause] → [12 x 28s cycles] → [6s baseline]
Total: 720s = 12 min = 480 volumes
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
- **config_v3.py** — Single `CONFIG` dict with all parameters (thermal, timing, scanner, masks, hardware, display)
- **run_experiment.py** — Main entry point: single GUI with run mode selector (full run or single half recovery), block plan, trigger wait, orchestrates halves + mid-run pause + ratings + file saving
- **run_block.py** — Real-time 10 Hz loop: applies waveform to thermode zones, logs thermode data (TSV), tracks QC per cycle. Supports `include_pre_baseline` / `include_post_baseline` for half-level control.
- **waveform.py** — Pure numpy functions: `generate_delta_waveform()`, `phase_shift_waveform()`, `apply_mask()`
- **masks.py** — Static dict of spatial masks defining zone polarity (+1 warm, -1 cool, 0 neutral)
- **thermode.py** — `ThermodeController` class wrapping TCS II.1 hardware with simulation fallback
- **qc.py** — `ThermalQC` class: per-sample metrics, per-cycle summaries, sustained overheat detection (rolling 5s window)
- **qc_monitor.py** — Standalone matplotlib dashboard: polls thermode TSV every 2s, plots zone temps + error. Handles both old (single-block) and new (two-half) data formats.
- **ratings.py** — `collect_vas_ratings()`: post-block VAS scales using pyglet keyboard handler (8s timeout). Questions: cold, warm, burning intensity.

**Module dependency graph:**
```
config_v3 → waveform → run_block → run_experiment
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
- **config_v3.py** — Single `CONFIG` dict (amplitude, pulse width, DS5 settings, timing)
- **run_experiment.py** — Same structure as thermal but for DS5
- **run_block.py** — 10 Hz loop: set DS5 amplitude → trigger pulse → log data
- **waveform.py** — Unipolar triangle wave: `generate_amplitude_waveform()` (0 → max → 0)
- **ds5_controller.py** — `DS5Controller` class: serial interface to Digitimer DS5 (19200 baud). Methods: `set_pulse_width()`, `set_amplitude()`, `trigger()`, `close()`
- **qc.py** — `ElectricalQC` class: per-cycle timing precision, pulse counts
- **ratings.py** — VAS questions: pain, tingling, sharpness intensity
- **test_single_pulse.py** — Interactive tool for determining perceptual threshold

**DS5 hardware**: ±10V input → ±10mA output (1 mA/V). `current_mA = millivolts / 1000`. Full scale = 10000 mV = 10 mA.

**Run plan** (4 runs, counterbalanced by `ramp_up_first`):
- All runs: electrical condition (single channel, no spatial masks)
- Ramp-up first = amplitude starts rising; ramp-down first = starts falling

## Multi-Site Configuration

Both experiments support multiple sites. Serial port is auto-detected from the OS in the GUI dialog.

Thermal-specific multi-site settings in `config_v3.py`:

| Setting | Home site (Windows) | Leipzig 7T (Linux) |
|---------|--------------------|--------------------|
| `com_port` | `'COM3'` | `'/dev/ttyACM0'` |
| `trigger_mode` | `'keyboard'` | `'parallel'` |
| `trigger_key` | `'t'` | (not used) |
| `parallel_port` | (not used) | `0` |
| `tcs_filter` | `None` | `'medium'` |

- **Scanner trigger**: `'keyboard'` mode uses `event.waitKeys()`. `'parallel'` mode waits for a falling edge on the parallel port Acknowledge pin (requires `parallel` module). In emulation mode, both fall back to space bar.
- **TCS MRI filter**: Set `tcs_filter` to `'medium'` at Leipzig. `set_filter()` is included in `TcsControl_python3_BPPlab`.

## Key Design Constraints

- **Real-time control loop** in `run_block.py` runs at 10 Hz. Changes must preserve timing precision.
- **Safety clamping**: thermal temps clamped to 10–50 C in `waveform.apply_mask()`. Electrical amplitude clamped to 0–10000 mV in `waveform.clamp_amplitude()`.
- **One invocation per run**: the script exits after each run. Completion is tracked by scanning for existing output files.
- **Data is never overwritten**: each output file includes a timestamp.
- **Hardware abstraction**: `ThermodeController` and `DS5Controller` both support simulation mode via the same interface pattern.
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
- `_stim_<timestamp>.tsv` — 10 Hz stimulation recording (no header; see JSON sidecar)
- `_stim_<timestamp>.json` — column definitions + full experiment config + body_site
- `_qc_<timestamp>.tsv` — per-cycle QC metrics (timing precision, pulse counts)

## Dependencies

- PsychoPy (with pyglet backend), NumPy, matplotlib, scipy
- `pyserial` — needed for both TCS thermode and DS5 stimulator (when `simulation = False`)
- `TcsControl_python3_BPPlab` — thermal only, when `simulation = False`
- `parallel` — only needed when `trigger_mode = 'parallel'` (Leipzig 7T)
- Requirements listed in `requirements.txt` at repo root
