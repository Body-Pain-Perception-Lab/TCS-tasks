# Leipzig Pilot — June 2026

Self-contained pilot testing folder for thermal (TCS thermode) and electrical (DS5 stimulator) modalities. Copy this entire folder to the testing computer.

## Setup

### Requirements

- Python 3.8+
- PsychoPy (thermal tasks with display)
- pyserial (`pip install pyserial`)

### Site selection

Both modalities can be tested on two setups at Leipzig. Edit the `SITE` variable at the top of each config file:

**`thermal/config_thermal_L01.py`**

| `SITE` | Serial port | MRI filter | Use case |
|--------|------------|------------|----------|
| `'windows'` | `COM7` | None | Local Windows PC |
| `'scanner'` | `/dev/ttyACM0` | `medium` | Scanner Linux (7T) |

**`electrical/config_electric_L01.py`**

| `SITE` | Serial port | Use case |
|--------|------------|----------|
| `'windows'` | `COM4` | Local Windows PC |
| `'scanner'` | `/dev/ttyUSB0` | Scanner Linux (7T) |

Both configs auto-detect OS mismatches and print a warning.

Before running on real hardware, set `simulation = False` in the config.

## Thermal

```bash
cd thermal
```

### Full session (all 3 steps)

```bash
python run_pilot.py
```

Runs the three steps in order with prompts between each. Use `--step 2` or `--step 3` to skip ahead.

### Step 1: Yes/No thresholding (CDT, WDT, HPT)

```bash
python run_yes_no.py                # all three modalities
python run_yes_no.py --modality CDT # single modality
python run_yes_no.py --no-display   # console only (no PsychoPy)
```

Adaptive 1-up/1-down staircase. Delivers a 2s thermal stimulus, participant responds Yes/No (left/right arrow). 30 trials per modality. Step size halves after the first reversal. Threshold estimated from the mean of the last 6 reversal points.

Output:
- `data/yn_cdt_<timestamp>.tsv` — per-trial data
- `data/yn_wdt_<timestamp>.tsv`
- `data/yn_hpt_<timestamp>.tsv`
- `data/yn_summary_<timestamp>.json` — threshold estimates + config

### Step 2: Method of Limits (CDT, WDT)

```bash
python run_method_of_limits.py
python run_method_of_limits.py --no-display
```

Temperature ramps from baseline at 2.5°C/s. Participant presses up arrow when they detect the change. 3 practice + 3 test trials per modality (CDT and WDT). 10s wait between practice and test.

Output:
- `data/mli_<timestamp>.tsv` — all trials (practice + test)
- `data/mli_summary_<timestamp>.json` — mean thresholds from test trials

### Step 3: Test waveform

```bash
python run_test_waveform.py                  # default ±17.5°C delta
python run_test_waveform.py --delta 12.0     # custom delta from thresholds
python run_test_waveform.py --cycles 5       # more cycles
python run_test_waveform.py --mask P1        # specific mask
python run_test_waveform.py --cool-first     # start with cooling
```

Runs 3 cycles of the triangular waveform (28s/cycle) to verify the thermode tracks setpoints and temperatures are comfortable. When launched via `run_pilot.py`, it reads the Yes/No thresholds and suggests a max_delta.

Output:
- `data/test_waveform_<timestamp>.tsv` — 10 Hz thermode recording (commanded + actual temps)

## Electrical

```bash
cd electrical
```

### Interactive single-pulse testing

```bash
python test_single_pulse.py           # uses config defaults
python test_single_pulse.py --sim     # simulation (no hardware)
```

Controls:
- **Enter** — deliver pulse at current amplitude
- **+ / -** — increase/decrease amplitude by step
- **type a number** — set amplitude directly (e.g. `250`)
- **s 25** — change step size to 25 mV
- **w 1.0** — change pulse width to 1.0 ms
- **q** — quit

Amplitude values are DS5 input voltage in mV. Actual output current depends on the DS5 front panel range setting. Document which range you use in `config_electric_L01.py`.

Output:
- `data/pulse_test_<timestamp>.tsv` — log of every pulse delivered

## Folder Structure

```
pilot_leipzig_june2026/
├── thermal/
│   ├── config_thermal_L01.py       # Config (site toggle, thresholds, timing)
│   ├── run_pilot.py                # Launcher (all 3 steps)
│   ├── run_yes_no.py               # Yes/No adaptive staircase
│   ├── run_method_of_limits.py     # Method of Limits (2.5°C/s)
│   ├── run_test_waveform.py        # Triangular waveform test
│   ├── thermode.py                 # TCS hardware wrapper
│   ├── waveform.py                 # Triangle wave generation
│   ├── masks.py                    # Spatial mask definitions
│   ├── qc.py                       # QC module
│   └── data/                       # Output
├── electrical/
│   ├── config_electric_L01.py      # Config (site toggle, DS5 defaults)
│   ├── ds5_controller.py           # DS5 hardware wrapper
│   ├── test_single_pulse.py        # Interactive pulse testing
│   └── data/                       # Output
└── README.md
```
