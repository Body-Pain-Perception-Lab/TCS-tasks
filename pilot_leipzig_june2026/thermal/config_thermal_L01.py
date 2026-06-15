"""
Pilot configuration — Leipzig June 2026 — Thermal (TCS thermode).

Two testing setups at Leipzig:
    - Local Windows PC: com_port = 'COM7', tcs_filter = None
    - Scanner Linux:    com_port = '/dev/ttyACM0', tcs_filter = 'medium'

Set SITE below to switch between them.
"""

import platform

# --- Site selection ---
# Set to 'windows' (local PC) or 'scanner' (Linux at 7T)
SITE = 'windows'

# Site-specific serial ports
_SITE_SETTINGS = {
    'windows': {
        'com_port': 'COM7',
        'tcs_filter': None,       # no MRI filter on local PC
    },
    'scanner': {
        'com_port': '/dev/ttyACM0',
        'tcs_filter': 'medium',   # MRI cable filter at 7T
    },
}

# Auto-detect: if on Linux and SITE is 'windows', warn
if platform.system() == 'Linux' and SITE == 'windows':
    print('WARNING: SITE is set to "windows" but running on Linux. '
          'Change SITE to "scanner" in config_thermal_L01.py if needed.')
elif platform.system() == 'Windows' and SITE == 'scanner':
    print('WARNING: SITE is set to "scanner" but running on Windows. '
          'Change SITE to "windows" in config_thermal_L01.py if needed.')

_site = _SITE_SETTINGS[SITE]

CONFIG = {
    # --- Hardware ---
    'com_port': _site['com_port'],
    'tcs_filter': _site['tcs_filter'],
    'simulation': True,           # True = no thermode commands (set False for real)

    # --- Thermal ---
    'baseline_temp': 30.0,        # degrees C
    'temp_min': 0.0,              # degrees C (safety clamp lower bound)
    'temp_max': 50.0,             # degrees C (safety clamp upper bound)

    # --- Thresholding: Method of Limits ---
    'mli_ramp_rate': 2.5,         # degrees C/s ramp for Method of Limits
    'mli_return_rate': 5.0,       # degrees C/s return to baseline
    'mli_trials_practice': 3,     # practice trials per modality
    'mli_trials_test': 3,         # test trials per modality
    'mli_iti': 5.0,               # inter-trial interval (s)
    'mli_iti_hpt': 10.0,          # longer ITI for heat pain
    'mli_cdt_floor': 0.0,         # minimum temperature for CDT
    'mli_wdt_ceiling': 50.0,      # maximum temperature for WDT
    'mli_hpt_ceiling': 50.0,      # maximum temperature for HPT

    # --- Thresholding: Yes/No ---
    'yn_n_trials': 30,            # adaptive trials per modality
    'yn_stim_duration': 2.0,      # stimulus duration (s)
    'yn_iti': 4.0,                # inter-trial interval (s)
    'yn_ramp_rate': 50.0,         # TCS ramp speed for brief stimuli (C/s)
    'yn_return_rate': 50.0,       # TCS return speed (C/s)
    'yn_timeout': 10.0,           # response timeout (s)
    # Starting deltas (degrees from baseline) — adjusted by staircase
    'yn_cdt_start_delta': 5.0,    # starting cooling delta
    'yn_wdt_start_delta': 5.0,    # starting warming delta
    'yn_hpt_start_delta': 10.0,   # starting heat pain delta
    # Step sizes for up-down staircase
    'yn_step_large': 2.0,         # initial step size (degrees C)
    'yn_step_small': 0.5,         # step after first reversal

    # --- Test waveform ---
    'waveform_ramp_rate': 50.0,   # TCS follow-mode ramp speed (C/s)
    'waveform_cycle_duration': 28.0,  # seconds per cycle
    'waveform_n_cycles': 3,       # just 3 cycles for a quick test
    'waveform_baseline_buffer': 6.0,  # seconds baseline before/after
    'waveform_max_delta': 17.5,   # default; can be overridden by thresholds

    # --- Display ---
    'fullscreen': False,          # False for pilot testing
    'screen_index': 0,            # primary screen

    # --- Update rate ---
    'update_hz': 10,              # thermode update frequency
}
