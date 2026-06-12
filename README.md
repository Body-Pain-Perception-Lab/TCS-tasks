# TCS Tasks

Experimental paradigms for thermal stimulation using the TCS II thermode during fMRI and behavioural sessions.

## Experiments

### `fMRI_triangular_wave/`
Continuous **triangular-wave** thermal stimulation via a 5-zone TCS thermode during fMRI. Designed for thermal population receptive field (pRF) mapping, comparing TGI (Thermal Grill Illusion) and Non-TGI spatial patterns. See its own [README](fMRI_triangular_wave/README.md) for full details.

### `fMRI_sinusoidal_wave/`
Variant of the triangular-wave experiment using a **sinusoidal waveform** instead. All other parameters, masks, timing, and infrastructure are identical.

### `fMRI_exp1_thermotopy/`
First fMRI thermotopy experiment.

### `fMRI_exp2_thermotopy/`
Second fMRI thermotopy experiment.

### `phs_lifespan/`
Lifespan behavioural study with pressure and heat stimulation.

### `pressureplate_decision/`
Pressure plate decision task.

## Shared Resources

- **`PythonHelpers/`** — Python driver for TCS II thermode (`TcsControl_python3.py`)
- **`docs/`** — TCS hardware manuals and reference documents
- **`requirements.txt`** — Python dependencies

## Requirements

### Python experiments
- Python 3.8+
- [PsychoPy](https://www.psychopy.org/) (with pyglet backend)
- NumPy, SciPy, matplotlib
- `TcsControl_python3` module (only needed for real thermode hardware)

### MATLAB experiments
- MATLAB R2020a or later
- [Psychtoolbox-3](http://psychtoolbox.org/)
