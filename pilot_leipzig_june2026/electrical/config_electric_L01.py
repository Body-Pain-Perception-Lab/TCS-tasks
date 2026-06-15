"""
Pilot configuration — Leipzig June 2026 — Electrical (DS5 stimulator).

Two testing setups at Leipzig:
    - Local Windows PC: com_port = 'COM4', baud = 19200
    - Scanner Linux:    com_port = '/dev/ttyUSB0', baud = 19200

Set SITE below to switch between them.
"""

import platform

# --- Site selection ---
# Set to 'windows' (local PC) or 'scanner' (Linux at 7T)
SITE = 'windows'

_SITE_SETTINGS = {
    'windows': {
        'com_port': 'COM4',
    },
    'scanner': {
        'com_port': '/dev/ttyUSB0',
    },
}

# Auto-detect mismatch warning
if platform.system() == 'Linux' and SITE == 'windows':
    print('WARNING: SITE is set to "windows" but running on Linux. '
          'Change SITE to "scanner" in config_electric_L01.py if needed.')
elif platform.system() == 'Windows' and SITE == 'scanner':
    print('WARNING: SITE is set to "scanner" but running on Windows. '
          'Change SITE to "windows" in config_electric_L01.py if needed.')

_site = _SITE_SETTINGS[SITE]

CONFIG = {
    # --- Hardware ---
    'com_port': _site['com_port'],
    'simulation': True,           # True = no DS5 commands (set False for real)

    # --- DS5 defaults ---
    'pulse_width_ms': 0.5,        # default pulse width (ms)
    'start_amplitude_mv': 100,    # starting amplitude (mV input to DS5)
    'step_mv': 50,                # default step size (mV)

    # DS5 front panel range (informational — set manually on device):
    #   ±1V  / ±10mA
    #   ±2.5V / ±25mA
    #   ±5V  / ±25mA
    #   ±10V / ±50mA
    'ds5_range_note': '±10V / ±50mA',  # document which range you're using
}
