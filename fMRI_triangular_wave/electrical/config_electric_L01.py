"""
Configuration for fMRI electrical pRF experiment — v3.
Triangular-wave amplitude modulation via Digitimer DS5 stimulator.

Run timing (each run = two halves with mid-run pause):
    Dummy volumes:   4 x 1.5s =   6.0s
    Pre-baseline:                  6.0s
    Half 1:         12 x  28s = 336.0s
    Mid-run pause:                30.0s  (no stimulation)
    Half 2:         12 x  28s = 336.0s
    Post-baseline:                 6.0s
    ─────────────────────────────────────
    Total:                       720.0s = 12 min 0s = 480 volumes

4 runs per session:
    Run 1: Ramp-Up first (12 cycles) → pause → Ramp-Down first (12 cycles)
    Run 2: Ramp-Down first (12 cycles) → pause → Ramp-Up first (12 cycles)
    Run 3: Ramp-Up first (12 cycles) → pause → Ramp-Down first (12 cycles)
    Run 4: Ramp-Down first (12 cycles) → pause → Ramp-Up first (12 cycles)

Total scanning time: 4 x 720s = 2880s = 48 min (plus inter-run gaps)
"""

CONFIG = {
    # Electrical stimulation
    'baseline_amplitude': 0.0,   # mV (no stimulation during baseline)
    'max_amplitude': 2000.0,     # mV peak amplitude (set during thresholding)
    'ramp_floor': 250.0,         # mV floor — skip sub-threshold range below this
    'pulse_width_ms': 20.0,      # pulse width in milliseconds
    'amp_min': 0.0,              # mV (safety clamp lower bound)
    'amp_max': 10000.0,          # mV (safety clamp upper bound = DS5 full scale)

    # Waveform
    'cycle_duration': 28.0,      # seconds per full triangle cycle
    'cycles_per_half': 12,       # 12 full cycles per half (24 total per run)
    'mid_run_pause': 30.0,       # seconds at baseline between the two halves
    'baseline_buffer': 6.0,      # seconds of baseline before/after run

    # Update rate
    'update_hz': 8,              # pulse delivery frequency (8 pulses/second)

    # MR
    'trigger_mode': 'keyboard',  # 'keyboard' (key press) or 'parallel' (parallel port)
    'trigger_key': 't',          # scanner trigger key (keyboard mode)
    'parallel_port': 0,          # parallel port address (parallel mode)
    'TR': 1.5,                   # seconds
    'dummy_volumes': 4,
    'emulate': False,            # True = use space instead of trigger

    # Block order counterbalancing
    # True  = Run 1 starts ramp-up first
    # False = Run 1 starts ramp-down first
    'ramp_up_first': True,

    # DS5 hardware
    'com_port': '/dev/ttyUSB0',   # serial port (Windows: 'COM8', Linux: '/dev/ttyUSB0')
    'simulation': False,         # True = no DS5 commands

    # VAS ratings
    'vas_enabled': False,
    'vas_max_duration': 8.0,
    'vas_labels': ['Not at all', 'Extremely'],

    # Display
    'fullscreen': False,         # True for scanner
    'screen_index': 0,           # 0 = primary, 1 = extended display
}
